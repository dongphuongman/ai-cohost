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
