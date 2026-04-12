import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
import sentry_sdk
from fastapi import WebSocket, WebSocketDisconnect, Query
from jose import JWTError

from sqlalchemy import select, update as sa_update

from app.auth.utils import decode_token
from app.core.config import settings
from app.core.database import async_session
from app.models.session import Comment, LiveSession, Suggestion
from app.models.tenant import Shop
from app.services import sessions as session_svc
from app.services import moderation as moderation_svc
from app.services.comment_classifier import classify as classify_comment
from app.services.auto_reply import (
    should_auto_reply,
    record_undo,
    disable_auto_reply,
    _get_redis as get_auto_reply_redis,
)
from app.services.embed_client import enqueue_suggestion_task

logger = logging.getLogger(__name__)

_redis = aioredis.from_url(settings.redis_url)


_WS_COMMENT_RATE_LIMIT = 30  # max comments per minute per shop
_WS_COMMENT_RATE_WINDOW = 60  # seconds


async def _check_ws_rate_limit(shop_id: int) -> bool:
    """Return True if within rate limit, False if exceeded."""
    key = f"ws_rate:{shop_id}:{int(time.time()) // _WS_COMMENT_RATE_WINDOW}"
    count = await _redis.incr(key)
    if count == 1:
        await _redis.expire(key, _WS_COMMENT_RATE_WINDOW + 5)
    return count <= _WS_COMMENT_RATE_LIMIT


# Heuristic prefixes for AI/host bot replies. Used as a fallback when the
# upstream client doesn't tag is_from_host explicitly. Keep this list narrow —
# real viewer questions should never start with these phrases.
_HOST_REPLY_PREFIXES = (
    "dạ, chị/em ơi",
    "dạ shop",
    "dạ vâng",
    "cảm ơn bạn",
    "cảm ơn anh chị",
)


def _looks_like_host_reply(text: str) -> bool:
    if not text:
        return False
    head = text.strip().lower()[:40]
    return any(head.startswith(p) for p in _HOST_REPLY_PREFIXES)


# ---------------------------------------------------------------------------
# Host-loop self-reply detection
# ---------------------------------------------------------------------------
#
# When the AI generates a suggestion and the host actually sends it to
# Facebook chat, the live chat panel shows the message back as a normal
# comment. The Chrome extension then re-scrapes that message and pushes it
# to the backend as a fresh `comment.new`. Without intervention the bot's
# own reply gets:
#   * counted as a viewer comment in the analytics rollups,
#   * fed back into the suggestion pipeline (cost & latency waste),
#   * surfaced inside "Top questions" on the dashboard (visible to users).
#
# This is exactly what we caught in session 17 during the 2026-04-12 UAT.
# The narrow ``_HOST_REPLY_PREFIXES`` allowlist can't cover every persona
# voice, so we add a content-equality fallback against the shop's own
# recently-sent suggestions.

# How long after a suggestion is sent we still consider an incoming
# comment to be a possible self-reply re-scrape. 5 minutes is comfortably
# above the FB-chat lag + extension polling cycle (~5–10s) without bloating
# the per-query result set under the 30 cmts/min rate limit.
_SELF_REPLY_WINDOW_MINUTES = 5

# Prefix length for "fuzzy" match. Handles cases where FB truncates long
# messages, the host edits a trailing word, or the scraper trims emojis.
# 30 chars is enough to be uniquely identifying for any non-trivial reply.
_SELF_REPLY_PREFIX_LEN = 30

# Skip very short comments to avoid false positives on common viewer
# replies like "?", "ok", "có ạ" — these are too short to fingerprint and
# would also be too short to ever be a meaningful AI suggestion.
_SELF_REPLY_MIN_LEN = 3


def _normalize_for_dedup(text: str | None) -> str:
    """Lower + strip for case/whitespace-insensitive comparison."""
    return (text or "").strip().lower()


def _is_self_reply_match(comment_text: str, suggestion_texts: list[str]) -> bool:
    """Pure-logic half of host-loop detection.

    Given an incoming comment and a list of suggestion texts that this
    shop sent inside the recent window, return True if the comment looks
    like a re-scrape of one of those suggestions.

    Match policy (in order):
      1. exact equality on normalized text
      2. 30-char prefix in either direction (handles FB UI truncation,
         host appending a word, or trailing emoji loss during scrape)

    Pure function — no DB, no network. Direct unit-test target.
    """
    norm_comment = _normalize_for_dedup(comment_text)
    if len(norm_comment) < _SELF_REPLY_MIN_LEN:
        return False

    for sug in suggestion_texts:
        norm_sug = _normalize_for_dedup(sug)
        if len(norm_sug) < _SELF_REPLY_MIN_LEN:
            continue

        if norm_comment == norm_sug:
            return True

        if (
            len(norm_comment) >= _SELF_REPLY_PREFIX_LEN
            and norm_sug.startswith(norm_comment[:_SELF_REPLY_PREFIX_LEN])
        ):
            return True

        if (
            len(norm_sug) >= _SELF_REPLY_PREFIX_LEN
            and norm_comment.startswith(norm_sug[:_SELF_REPLY_PREFIX_LEN])
        ):
            return True

    return False


async def _fetch_recent_suggestion_texts(
    db, session_id: int, *, window_minutes: int = _SELF_REPLY_WINDOW_MINUTES
) -> list[str]:
    """Return texts of every suggestion in this session within the recent window.

    No status filter on purpose. The earlier version of this query
    restricted to ``status='sent'`` on the assumption that other states
    (``pasted_not_sent``, ``suggested``) could not have been delivered to
    Facebook chat and therefore could not be re-scraped. That assumption
    turned out to be wrong:

    * ``pasted_not_sent`` is set when the extension's Quick Paste action
      drops the suggestion text into the FB chat input. The extension
      has no reliable signal for whether the host then clicks Send in
      FB's own UI — so this status is really *pasted-and-maybe-sent*.
      Verified on the 2026-04-12 dataset: 50 viewer comments exact-text
      matched suggestions whose status was ``pasted_not_sent`` (e.g.
      session 15, suggestion #267 → comment #460).
    * ``suggested`` matches happen on a race: the comment re-scrape can
      arrive over the WS before the extension PATCHes the suggestion's
      status to ``sent``/``pasted_not_sent``. 11 such matches existed
      in the same dataset.

    Status is an extension UI state, not a "delivered to Facebook"
    signal, so we don't gate detection on it. The 5-minute time window
    plus same-session scope is the actual safety rail: the probability
    that a viewer types one of the shop's AI suggestions verbatim, in
    the same session, within 5 minutes of generation, is effectively
    zero.

    Bounded by both the time window and a hard row limit so a runaway
    session can't blow up the per-comment query latency.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    result = await db.execute(
        select(Suggestion.text_)
        .where(
            Suggestion.session_id == session_id,
            Suggestion.created_at >= cutoff,
        )
        .order_by(Suggestion.created_at.desc())
        .limit(50)
    )
    return [row[0] for row in result.all() if row[0]]


async def is_likely_self_reply(db, session_id: int, comment_text: str) -> bool:
    """Detect host-loop self-reply: AI suggestion → host sent → re-scrape.

    Thin DB wrapper around ``_is_self_reply_match`` so the matching logic
    stays pure and unit-testable. Cheap fast-path for empty/short text
    avoids touching the DB at all in the common viewer-comment case.
    """
    if not comment_text or len(comment_text.strip()) < _SELF_REPLY_MIN_LEN:
        return False
    recent = await _fetch_recent_suggestion_texts(db, session_id)
    if not recent:
        return False
    return _is_self_reply_match(comment_text, recent)


def _cache_key(shop_id: int, comment_text: str) -> str:
    normalized = comment_text.strip().lower()[:100]
    h = hashlib.md5(normalized.encode()).hexdigest()
    return f"suggestion_cache:{shop_id}:{h}"


class WSConnectionState:
    """Track state for a single WebSocket connection."""

    def __init__(self, user_id: int, shop_ids: list[int]):
        self.user_id = user_id
        self.shop_ids = shop_ids
        self.session_id: int | None = None
        self.session_uuid: str | None = None
        self.shop_id: int | None = None
        self.pubsub_task: asyncio.Task | None = None
        # Track comment metadata so worker doesn't need to re-fetch
        self.comment_meta: dict[int, dict] = {}


def verify_ws_token(token: str) -> dict | None:
    """Verify JWT from WebSocket query parameter. Returns payload or None."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    # 1. Verify JWT
    payload = verify_ws_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    user_id = int(payload["sub"])
    shop_ids = payload.get("shop_ids", [])
    state = WSConnectionState(user_id, shop_ids)

    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "session.start":
                if state.session_id is not None:
                    await websocket.send_json({
                        "type": "error",
                        "code": "session_active",
                        "message": "Đã có session đang chạy. Kết thúc session hiện tại trước.",
                    })
                    continue

                shop_id = data.get("shop_id")
                if shop_id not in state.shop_ids:
                    await websocket.send_json({
                        "type": "error",
                        "code": "forbidden",
                        "message": "Không có quyền truy cập shop này",
                    })
                    continue

                async with async_session() as db:
                    session = await session_svc.start_session(
                        db,
                        shop_id=shop_id,
                        user_id=state.user_id,
                        platform=data.get("platform", "unknown"),
                        product_ids=data.get("products"),
                        persona_id=data.get("persona_id"),
                    )
                    await db.commit()

                    state.session_id = session.id
                    state.session_uuid = session.uuid
                    state.shop_id = shop_id

                    await websocket.send_json({
                        "type": "session.started",
                        "session_id": session.uuid,
                    })

                    # Start Redis pub/sub listener for suggestion streaming
                    state.pubsub_task = asyncio.create_task(
                        _listen_suggestions(websocket, state)
                    )

            elif msg_type == "session.rejoin":
                # Reconnect to an existing session (after WS drop / service worker restart)
                session_uuid = data.get("session_id")
                if not session_uuid:
                    await websocket.send_json({
                        "type": "error",
                        "code": "missing_session_id",
                        "message": "session_id is required",
                    })
                    continue

                async with async_session() as db:
                    result = await db.execute(
                        select(LiveSession).where(
                            LiveSession.uuid == session_uuid,
                            LiveSession.status.in_(["running", "interrupted"]),
                        )
                    )
                    session = result.scalar_one_or_none()

                if not session or session.shop_id not in state.shop_ids:
                    await websocket.send_json({
                        "type": "error",
                        "code": "session_not_found",
                        "message": "Session không tồn tại hoặc đã kết thúc",
                    })
                    continue

                state.session_id = session.id
                state.session_uuid = session.uuid
                state.shop_id = session.shop_id

                # Restart pub/sub listener
                if state.pubsub_task:
                    state.pubsub_task.cancel()
                state.pubsub_task = asyncio.create_task(
                    _listen_suggestions(websocket, state)
                )

                # Mark session active again if it was interrupted
                if session.status == "interrupted":
                    async with async_session() as db:
                        await db.execute(
                            sa_update(LiveSession)
                            .where(LiveSession.id == session.id)
                            .values(status="running")
                        )
                        await db.commit()

                await websocket.send_json({
                    "type": "session.rejoined",
                    "session_id": session.uuid,
                })
                logger.info("WS rejoined session %s for user %s", session.uuid, state.user_id)

            elif msg_type == "comment.new":
                if not state.session_id or not state.shop_id:
                    await websocket.send_json({
                        "type": "error",
                        "code": "no_session",
                        "message": "Chưa có session đang chạy",
                    })
                    continue

                # Rate limit: max 30 comments/min per shop
                if not await _check_ws_rate_limit(state.shop_id):
                    await websocket.send_json({
                        "type": "error",
                        "code": "RATE_LIMITED",
                        "message": "Quá nhiều comment. Tối đa 30 gợi ý/phút.",
                    })
                    continue

                comment_data = data.get("comment", {})
                comment_text = comment_data.get("text", "")
                external_user_id = comment_data.get("externalUserId")
                # Upstream client (extension/scraper) marks the host's own
                # messages so we don't classify them or generate AI replies
                # against them. Heuristic fallback catches obvious bot prefixes
                # if the client doesn't set the flag.
                is_from_host = bool(
                    comment_data.get("isFromHost")
                    or comment_data.get("is_from_host")
                    or _looks_like_host_reply(comment_text)
                )

                # Host-loop self-reply detection. Only run when the cheaper
                # checks above haven't already classified the comment as host
                # (saves a DB roundtrip on the common viewer-comment path).
                # See _is_self_reply_match for the matching contract.
                if not is_from_host:
                    async with async_session() as db:
                        if await is_likely_self_reply(
                            db, state.session_id, comment_text
                        ):
                            is_from_host = True
                            logger.info(
                                "WS host-loop detected: session=%s shop=%s "
                                "text=%r",
                                state.session_uuid,
                                state.shop_id,
                                comment_text[:80],
                            )

                if is_from_host:
                    # Host/bot comment — persist for the timeline but skip
                    # classification, suggestion generation, and analytics.
                    async with async_session() as db:
                        comment = await session_svc.ingest_comment(
                            db,
                            session_id=state.session_id,
                            shop_id=state.shop_id,
                            external_user_name=comment_data.get("externalUserName", ""),
                            text=comment_text,
                            external_user_id=external_user_id,
                            intent=None,
                            confidence=None,
                            is_spam=False,
                            is_from_host=True,
                        )
                        await db.commit()
                    await websocket.send_json({
                        "type": "comment.received",
                        "comment_id": comment.id,
                        "comment": comment_data,
                        "intent": None,
                        "skipped_reason": "Host comment — không xử lý AI",
                    })
                    continue

                # 1. Load shop moderation rules & classify
                async with async_session() as db:
                    shop_rules = await moderation_svc.get_shop_rules(db, state.shop_id)

                classify_result = await classify_comment(
                    comment_text, state.shop_id, shop_rules, external_user_id
                )

                # 2. Save comment with classification metadata
                async with async_session() as db:
                    comment = await session_svc.ingest_comment(
                        db,
                        session_id=state.session_id,
                        shop_id=state.shop_id,
                        external_user_name=comment_data.get("externalUserName", ""),
                        text=comment_text,
                        external_user_id=external_user_id,
                        intent=classify_result.intent,
                        confidence=classify_result.confidence,
                        is_spam=(classify_result.action == "hide"),
                        is_from_host=False,
                    )
                    await db.commit()

                # 3. Act based on classification
                if classify_result.action == "hide":
                    await websocket.send_json({
                        "type": "comment.hidden",
                        "comment_id": comment.id,
                        "reason": classify_result.reason or "Spam detected",
                    })
                    continue

                if classify_result.action == "flag":
                    async with async_session() as db:
                        await moderation_svc.flag_comment(
                            db, comment.id, state.shop_id, classify_result.reason
                        )
                        await db.commit()
                    await websocket.send_json({
                        "type": "comment.flagged",
                        "comment_id": comment.id,
                        "comment": comment_data,
                        "reason": classify_result.reason or "Nội dung cần kiểm duyệt",
                    })
                    continue

                if classify_result.action == "skip_ai":
                    await websocket.send_json({
                        "type": "comment.received",
                        "comment_id": comment.id,
                        "comment": comment_data,
                        "intent": classify_result.intent,
                        "skipped_reason": "Không cần gợi ý AI",
                    })
                    continue

                # action == "generate_ai" — proceed with LLM suggestion
                # Store comment metadata for enriching worker responses
                state.comment_meta[comment.id] = {
                    "externalUserName": comment_data.get("externalUserName", ""),
                    "text": comment_text,
                    "receivedAt": comment_data.get("receivedAt", ""),
                }

                # Check cache first (fast path)
                cached = await _redis.get(_cache_key(state.shop_id, comment_text))
                if cached:
                    try:
                        cached_data = json.loads(cached)
                        await websocket.send_json({
                            "type": "suggestion.new",
                            "suggestion": {
                                "id": cached_data["id"],
                                "replyText": cached_data["replyText"],
                                "originalComment": {
                                    "externalUserName": comment_data.get("externalUserName", ""),
                                    "text": comment_text,
                                    "receivedAt": comment_data.get("receivedAt", ""),
                                },
                                "confidence": cached_data.get("confidence", 0.8),
                                "createdAt": comment.created_at.isoformat(),
                            },
                        })
                        continue
                    except (json.JSONDecodeError, KeyError):
                        pass

                # Cache miss — enqueue LLM task
                await enqueue_suggestion_task(
                    comment.id, state.session_id, state.shop_id
                )

            elif msg_type == "suggestion.action":
                suggestion_id = data.get("suggestion_id")
                action = data.get("action")
                edited_text = data.get("edited_text")
                _ALLOWED_ACTIONS = {"sent", "pasted_not_sent", "read", "dismissed", "edited", "auto_sent", "auto_cancelled"}
                if suggestion_id and action and action in _ALLOWED_ACTIONS:
                    try:
                        async with async_session() as db:
                            await session_svc.update_suggestion_action(
                                db,
                                suggestion_id=int(suggestion_id),
                                shop_id=state.shop_id,
                                action=action,
                                edited_text=edited_text,
                            )
                            await db.commit()

                            # Track undo for safety monitor
                            if action == "auto_cancelled" and state.session_id:
                                r = await get_auto_reply_redis()
                                should_disable = await record_undo(r, state.session_id)
                                if should_disable:
                                    session_result = await db.execute(
                                        select(LiveSession).where(
                                            LiveSession.id == state.session_id
                                        )
                                    )
                                    sess = session_result.scalar_one_or_none()
                                    if sess:
                                        await disable_auto_reply(
                                            sess, r,
                                            "Tự động tắt: bạn đã hủy nhiều auto-reply gần đây",
                                        )
                                        await db.commit()
                                        await websocket.send_json({
                                            "type": "auto_reply.disabled",
                                            "reason": "Tự động tắt: bạn đã hủy nhiều auto-reply gần đây",
                                        })
                    except Exception:
                        logger.debug(
                            "suggestion.action failed for %s", suggestion_id, exc_info=True
                        )

            elif msg_type == "session.end":
                if state.pubsub_task:
                    state.pubsub_task.cancel()
                    state.pubsub_task = None
                session_uuid = data.get("session_id") or state.session_uuid
                if session_uuid:
                    async with async_session() as db:
                        await session_svc.end_session(db, session_uuid, shop_id=state.shop_id)
                        await db.commit()
                state.session_id = None
                state.session_uuid = None
                state.shop_id = None
                state.comment_meta.clear()

            else:
                await websocket.send_json({
                    "type": "error",
                    "code": "unknown_type",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        # Cancel pub/sub listener
        if state.pubsub_task:
            state.pubsub_task.cancel()
        # Cleanup: mark running session as interrupted
        if state.session_uuid:
            try:
                async with async_session() as db:
                    await session_svc.mark_session_interrupted(db, state.session_uuid)
                    await db.commit()
            except Exception:
                pass
    except Exception as exc:
        # Catch-all for ANY uncaught error inside the message-processing
        # loop. Without this, exceptions silently kill the WS connection
        # and never reach Sentry — that's exactly how the 2026-04-12
        # is_from_host migration drift went undetected (every comment.new
        # raised UndefinedColumnError, the connection died, the extension's
        # optimistic UI counter still ticked up, and nobody saw the alert).
        #
        # Tag the event so it's easy to filter in Sentry, then re-raise
        # WebSocketDisconnect-style cleanup so the session is marked
        # interrupted instead of left as "running" forever.
        logger.exception("WS handler raised uncaught exception")
        sentry_sdk.set_tag("ws.user_id", state.user_id)
        sentry_sdk.set_tag("ws.shop_id", state.shop_id)
        sentry_sdk.set_tag("ws.session_uuid", state.session_uuid)
        sentry_sdk.capture_exception(exc)

        if state.pubsub_task:
            state.pubsub_task.cancel()
        if state.session_uuid:
            try:
                async with async_session() as db:
                    await session_svc.mark_session_interrupted(db, state.session_uuid)
                    await db.commit()
            except Exception:
                pass
        # Try to close the socket cleanly so the client gets a real close
        # frame instead of a TCP RST. Best-effort.
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass


async def _listen_suggestions(websocket: WebSocket, state: WSConnectionState) -> None:
    """Subscribe to Redis pub/sub for suggestion streaming from Celery worker."""
    pubsub = _redis.pubsub()
    channel = f"suggestion_stream:{state.session_id}"
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
                msg_type = data.get("type")

                if msg_type == "suggestion.stream":
                    await websocket.send_json({
                        "type": "suggestion.stream",
                        "suggestion_id": str(data.get("comment_id", "")),
                        "chunk": data.get("chunk", ""),
                    })

                elif msg_type == "suggestion.complete":
                    suggestion_data = data.get("suggestion", {})
                    comment_id = data.get("comment_id")
                    suggestion_id = suggestion_data.get("id")
                    # Enrich with comment metadata from state
                    meta = state.comment_meta.pop(comment_id, {})
                    if meta:
                        suggestion_data["originalComment"] = {
                            "externalUserName": meta.get("externalUserName", ""),
                            "text": meta.get("text", ""),
                            "receivedAt": meta.get("receivedAt", ""),
                        }

                    # Check auto-reply eligibility
                    auto_reply_decision = None
                    if state.session_id and state.shop_id and comment_id and suggestion_id:
                        try:
                            async with async_session() as db:
                                comment_row = await db.execute(
                                    select(Comment).where(Comment.id == comment_id)
                                )
                                comment_obj = comment_row.scalar_one_or_none()

                                suggestion_row = await db.execute(
                                    select(Suggestion).where(Suggestion.id == suggestion_id)
                                )
                                suggestion_obj = suggestion_row.scalar_one_or_none()

                                session_row = await db.execute(
                                    select(LiveSession).where(LiveSession.id == state.session_id)
                                )
                                session_obj = session_row.scalar_one_or_none()

                                plan_row = await db.execute(
                                    select(Shop.plan).where(Shop.id == state.shop_id)
                                )
                                shop_plan = plan_row.scalar_one_or_none() or "trial"

                                if comment_obj and suggestion_obj and session_obj:
                                    auto_reply_decision = await should_auto_reply(
                                        comment_obj, suggestion_obj, session_obj, shop_plan,
                                        db=db,
                                    )
                        except Exception:
                            logger.debug("Auto-reply check failed", exc_info=True)

                    if auto_reply_decision and auto_reply_decision.allowed:
                        from datetime import datetime, timedelta, timezone
                        undo_deadline = datetime.now(timezone.utc) + timedelta(seconds=15)
                        await websocket.send_json({
                            "type": "suggestion.auto_reply",
                            "suggestion_id": suggestion_id,
                            "text": suggestion_data.get("replyText", ""),
                            "suggestion": suggestion_data,
                            "reason": auto_reply_decision.reason,
                            "undo_deadline": undo_deadline.isoformat(),
                        })
                    else:
                        msg = {
                            "type": "suggestion.new",
                            "suggestion": suggestion_data,
                        }
                        if auto_reply_decision and not auto_reply_decision.allowed:
                            msg["auto_reply_blocked_reason"] = auto_reply_decision.reason
                        await websocket.send_json(msg)

                elif msg_type == "suggestion.error":
                    await websocket.send_json({
                        "type": "error",
                        "code": "suggestion_failed",
                        "message": "Không thể tạo gợi ý. Thử lại sau.",
                    })

            except (json.JSONDecodeError, KeyError):
                continue
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
