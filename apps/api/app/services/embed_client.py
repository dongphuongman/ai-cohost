"""Enqueue embedding tasks by pushing Celery-compatible messages to Redis.

We avoid importing the celery package (which isn't in API's deps) by
publishing task messages directly to the Redis broker using kombu's
JSON protocol format. Uses redis.asyncio to avoid blocking the event loop.
"""

import json
import logging
import uuid

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis = aioredis.from_url(settings.redis_url)


async def _send_task(task_name: str, args: list, queue: str = "embed_queue") -> None:
    """Push a Celery-compatible task message onto a Redis queue."""
    task_id = str(uuid.uuid4())
    body = json.dumps({
        "id": task_id,
        "task": task_name,
        "args": args,
        "kwargs": {},
        "retries": 0,
    })
    message = json.dumps({
        "body": body,
        "content-encoding": "utf-8",
        "content-type": "application/json",
        "headers": {
            "id": task_id,
            "task": task_name,
            "lang": "py",
            "root_id": task_id,
        },
        "properties": {
            "delivery_mode": 2,
            "delivery_tag": task_id,
            "body_encoding": "utf-8",
            "delivery_info": {"exchange": "", "routing_key": queue},
        },
    })
    await _redis.lpush(queue, message)


async def enqueue_product_embedding(product_id: int) -> None:
    try:
        await _send_task("tasks.embed.embed_product", [product_id])
    except Exception:
        logger.exception("Failed to enqueue embed_product for %s", product_id)


async def enqueue_faq_embedding(faq_id: int) -> None:
    try:
        await _send_task("tasks.embed.embed_faq", [faq_id])
    except Exception:
        logger.exception("Failed to enqueue embed_faq for %s", faq_id)


async def enqueue_script_task(
    shop_id: int,
    user_id: int,
    config: dict,
    products: list[dict],
    persona: dict | None,
) -> str:
    """Enqueue script generation on the script_queue. Returns task_id."""
    task_id = str(uuid.uuid4())
    body = json.dumps({
        "id": task_id,
        "task": "tasks.script.generate_script",
        "args": [],
        "kwargs": {
            "shop_id": shop_id,
            "user_id": user_id,
            "config": config,
            "products": products,
            "persona": persona,
        },
        "retries": 0,
    })
    message = json.dumps({
        "body": body,
        "content-encoding": "utf-8",
        "content-type": "application/json",
        "headers": {
            "id": task_id,
            "task": "tasks.script.generate_script",
            "lang": "py",
            "root_id": task_id,
        },
        "properties": {
            "delivery_mode": 2,
            "delivery_tag": task_id,
            "body_encoding": "utf-8",
            "delivery_info": {"exchange": "", "routing_key": "script_queue"},
        },
    })
    try:
        await _redis.lpush("script_queue", message)
    except Exception:
        logger.exception("Failed to enqueue script generation for shop %s", shop_id)
        raise
    return task_id


async def get_job_status(job_id: str) -> dict | None:
    """Get job status from Redis. Returns None if not found."""
    data = await _redis.get(f"job:{job_id}")
    if data is None:
        return None
    return json.loads(data)


async def enqueue_suggestion_task(
    comment_id: int, session_id: int, shop_id: int
) -> None:
    """Enqueue LLM suggestion generation on the llm_queue (high priority)."""
    try:
        await _send_task(
            "tasks.llm.generate_suggestion",
            [comment_id, session_id, shop_id],
            queue="llm_queue",
        )
    except Exception:
        logger.exception("Failed to enqueue suggestion for comment %s", comment_id)
