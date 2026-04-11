"""Auto-reply service with strict whitelist/blacklist safety controls.

Design principle: SAFE BY DEFAULT. If any check is uncertain, the answer is NO.

Whitelist (ONLY these can auto-reply):
  - greeting (confidence >= 0.8)
  - thanks (confidence >= 0.8)
  - FAQ match with confidence >= threshold (default 0.9)

Blacklist (NEVER auto-reply):
  - complaint intent
  - pricing intent
  - comment contains 3+ digit numbers (prices, phone numbers, order IDs)
  - comment longer than 100 characters
  - confidence below threshold

Rate limits:
  - Max 5 auto-replies per minute per session
  - Max 30 auto-replies per hour per session
  - Exceeding rate limit auto-disables auto-reply for the session

Safety monitor:
  - 2+ undos in 10 minutes auto-disables auto-reply
"""

import logging
import re

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.session import Comment, LiveSession, Suggestion
from app.models.tenant import Shop
from app.schemas.auto_reply import AutoReplyDecision

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None

# Plans that support auto-reply
AUTO_REPLY_PLANS = {"pro", "enterprise"}

# Intents that are NEVER auto-replied (hard blacklist)
BLACKLISTED_INTENTS = frozenset({"complaint", "pricing"})

# Intents that CAN be auto-replied (whitelist)
WHITELISTED_INTENTS = frozenset({"greeting", "thanks"})

# FAQ-eligible intents (need high confidence + FAQ match)
FAQ_ELIGIBLE_INTENTS = frozenset({"question", "shipping"})

# Minimum confidence for whitelist intents
WHITELIST_MIN_CONFIDENCE = 0.8

# Default confidence threshold for FAQ matches
DEFAULT_FAQ_THRESHOLD = 0.9

# Rate limits
RATE_LIMIT_PER_MINUTE = 5
RATE_LIMIT_PER_HOUR = 30

# Comment length limit for auto-reply
MAX_COMMENT_LENGTH = 100

# Pattern: 3+ consecutive digits (prices, phone numbers, order IDs)
NUMBERS_PATTERN = re.compile(r"\d{3,}")

# Undo threshold for auto-disable
UNDO_THRESHOLD = 2
UNDO_WINDOW_SECONDS = 600  # 10 minutes


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url)
    return _redis


async def should_auto_reply(
    comment: Comment,
    suggestion: Suggestion,
    session: LiveSession,
    shop_plan: str,
) -> AutoReplyDecision:
    """Decide whether a suggestion should be auto-replied.

    Returns AutoReplyDecision with allowed=True/False and reason.
    """
    # 1. Check if auto-reply is enabled for this session
    session_meta = session.metadata_ or {}
    if not session_meta.get("auto_reply_enabled", False):
        return AutoReplyDecision(allowed=False, reason="Auto-reply chưa bật")

    # 2. Check plan supports auto-reply
    if shop_plan not in AUTO_REPLY_PLANS:
        return AutoReplyDecision(allowed=False, reason="Gói hiện tại không hỗ trợ auto-reply")

    # 3. Check rate limit
    r = await _get_redis()
    rate_ok = await check_rate_limit(r, session.id)
    if not rate_ok:
        # Auto-disable when rate exceeded
        await disable_auto_reply(session, r, "Đã vượt giới hạn auto-reply")
        return AutoReplyDecision(allowed=False, reason="Vượt giới hạn tần suất auto-reply")

    # 4. BLACKLIST CHECK (hard reject — checked before whitelist)
    comment_text = comment.text_
    comment_intent = comment.intent

    if comment_intent in BLACKLISTED_INTENTS:
        reason_map = {
            "complaint": "Khiếu nại — cần host trả lời trực tiếp",
            "pricing": "Giá cả — cần host xác nhận",
        }
        return AutoReplyDecision(
            allowed=False,
            reason=reason_map.get(comment_intent, f"Intent '{comment_intent}' nằm trong blacklist"),
        )

    # Check for numbers (3+ digits: prices, phone numbers, order codes)
    if NUMBERS_PATTERN.search(comment_text):
        return AutoReplyDecision(
            allowed=False,
            reason="Comment chứa số — cần host kiểm tra",
        )

    # Check comment length
    if len(comment_text) > MAX_COMMENT_LENGTH:
        return AutoReplyDecision(
            allowed=False,
            reason="Comment dài — có thể là câu hỏi phức tạp",
        )

    # 5. WHITELIST CHECK
    suggestion_confidence = comment.confidence or 0.0

    # Greeting
    if comment_intent == "greeting" and suggestion_confidence >= WHITELIST_MIN_CONFIDENCE:
        return AutoReplyDecision(allowed=True, reason="Greeting auto-reply")

    # Thanks
    if comment_intent == "thanks" and suggestion_confidence >= WHITELIST_MIN_CONFIDENCE:
        return AutoReplyDecision(allowed=True, reason="Thanks auto-reply")

    # FAQ exact match (above threshold)
    threshold = session_meta.get("auto_reply_threshold", DEFAULT_FAQ_THRESHOLD)
    if (
        comment_intent in FAQ_ELIGIBLE_INTENTS
        and suggestion_confidence >= threshold
        and suggestion.rag_faq_ids  # must have FAQ match
    ):
        return AutoReplyDecision(allowed=True, reason="FAQ match above threshold")

    # 6. DEFAULT: NO auto-reply
    return AutoReplyDecision(
        allowed=False,
        reason=f"Không đủ điều kiện auto-reply (confidence {suggestion_confidence:.0%})",
    )


async def check_rate_limit(r: aioredis.Redis, session_id: int) -> bool:
    """Check rate limits: 5/minute, 30/hour. Returns True if within limits."""
    key_min = f"auto_reply_rate:{session_id}:min"
    key_hour = f"auto_reply_rate:{session_id}:hour"

    pipe = r.pipeline()
    pipe.incr(key_min)
    pipe.incr(key_hour)
    min_count, hour_count = await pipe.execute()

    # Set expiry on first increment
    if min_count == 1:
        await r.expire(key_min, 60)
    if hour_count == 1:
        await r.expire(key_hour, 3600)

    return min_count <= RATE_LIMIT_PER_MINUTE and hour_count <= RATE_LIMIT_PER_HOUR


async def record_undo(r: aioredis.Redis, session_id: int) -> bool:
    """Record an undo event. Returns True if auto-reply should be auto-disabled."""
    key = f"auto_reply_undo:{session_id}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, UNDO_WINDOW_SECONDS)
    return count >= UNDO_THRESHOLD


async def disable_auto_reply(
    session: LiveSession,
    r: aioredis.Redis,
    reason: str,
) -> None:
    """Disable auto-reply for a session and publish notification."""
    session.metadata_ = {**(session.metadata_ or {}), "auto_reply_enabled": False}
    logger.info("Auto-reply disabled for session %d: %s", session.id, reason)

    await r.publish(
        f"notifications:{session.shop_id}",
        f'{{"type":"auto_reply.disabled","session_id":{session.id},"reason":"{reason}"}}',
    )


async def toggle_auto_reply(
    db: AsyncSession,
    session_uuid: str,
    shop_id: int,
    enabled: bool,
    threshold: float = DEFAULT_FAQ_THRESHOLD,
) -> LiveSession:
    """Toggle auto-reply for a session. Validates plan eligibility."""
    result = await db.execute(
        select(LiveSession).where(
            LiveSession.uuid == session_uuid,
            LiveSession.shop_id == shop_id,
            LiveSession.status == "running",
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise ValueError("Session không tìm thấy hoặc đã kết thúc")

    if enabled:
        # Check plan
        plan_result = await db.execute(select(Shop.plan).where(Shop.id == shop_id))
        plan = plan_result.scalar_one()
        if plan not in AUTO_REPLY_PLANS:
            raise ValueError("Gói hiện tại không hỗ trợ auto-reply. Nâng cấp lên Pro.")

    meta = dict(session.metadata_ or {})
    meta["auto_reply_enabled"] = enabled
    meta["auto_reply_threshold"] = threshold
    session.metadata_ = meta

    await db.commit()
    await db.refresh(session)

    logger.info(
        "Auto-reply %s for session %s (threshold=%.2f)",
        "enabled" if enabled else "disabled",
        session_uuid,
        threshold,
    )

    return session
