import asyncio
import hashlib
import json
import logging

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect, Query
from jose import JWTError

from app.auth.utils import decode_token
from app.core.config import settings
from app.core.database import async_session
from app.services import sessions as session_svc
from app.services.embed_client import enqueue_suggestion_task

logger = logging.getLogger(__name__)

_redis = aioredis.from_url(settings.redis_url)


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

            elif msg_type == "comment.new":
                if not state.session_id or not state.shop_id:
                    await websocket.send_json({
                        "type": "error",
                        "code": "no_session",
                        "message": "Chưa có session đang chạy",
                    })
                    continue

                comment_data = data.get("comment", {})
                comment_text = comment_data.get("text", "")
                async with async_session() as db:
                    comment = await session_svc.ingest_comment(
                        db,
                        session_id=state.session_id,
                        shop_id=state.shop_id,
                        external_user_name=comment_data.get("externalUserName", ""),
                        text=comment_text,
                        external_user_id=comment_data.get("externalUserId"),
                    )
                    await db.commit()

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
                _ALLOWED_ACTIONS = {"sent", "pasted_not_sent", "read", "dismissed", "edited"}
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
                    suggestion = data.get("suggestion", {})
                    comment_id = data.get("comment_id")
                    # Enrich with comment metadata from state
                    meta = state.comment_meta.pop(comment_id, {})
                    if meta:
                        suggestion["originalComment"] = {
                            "externalUserName": meta.get("externalUserName", ""),
                            "text": meta.get("text", ""),
                            "receivedAt": meta.get("receivedAt", ""),
                        }
                    await websocket.send_json({
                        "type": "suggestion.new",
                        "suggestion": suggestion,
                    })

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
