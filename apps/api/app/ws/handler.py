import asyncio
import hashlib
import json
import logging
import time

import redis.asyncio as aioredis
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
