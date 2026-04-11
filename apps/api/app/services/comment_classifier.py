"""Two-tier comment classifier for livestream moderation.

Tier 1: Rule-based (fast, 0 cost, <1ms) — handles obvious spam, toxic, greetings, praise.
Tier 2: LLM-based (slower, costs tokens) — only for low-confidence cases from Tier 1.
"""

import re
import time
from dataclasses import dataclass, field

import redis.asyncio as aioredis

from app.core.config import settings

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url)
    return _redis


@dataclass
class ClassifyResult:
    intent: str        # question, pricing, shipping, complaint, praise, greeting, spam, toxic, noise, blocked
    confidence: float  # 0-1
    action: str        # generate_ai, skip_ai, hide, flag, ignore
    reason: str | None = None


@dataclass
class ShopRules:
    blocked_keywords: list[str] = field(default_factory=list)
    blocked_patterns: list[str] = field(default_factory=list)
    whitelisted_users: list[str] = field(default_factory=list)
    blacklisted_users: list[str] = field(default_factory=list)
    auto_hide_spam: bool = True
    auto_hide_links: bool = True
    auto_flag_toxic: bool = True
    emoji_flood_threshold: int = 6
    min_comment_length: int = 2
    use_llm_classify: bool = False
    llm_classify_rate_limit: int = 10


# ====== Tier 1: Rule-based patterns ======

_SPAM_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"t\.me/", re.IGNORECASE),
    re.compile(r"wa\.me/", re.IGNORECASE),
    re.compile(r"bit\.ly/", re.IGNORECASE),
    re.compile(r"@\w+\s*@\w+"),                       # multiple mentions (bot behavior)
    re.compile(r"(.)\1{5,}"),                          # character spam: "aaaaaa"
]

_EMOJI_FLOOD = re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF\U00002702-\U000027B0]{6,}")

_TOXIC_PATTERNS = [
    re.compile(r"\b(lừa đảo|scam|fake|hàng giả|bán hàng rác|lừa|đồ rác|ngu|khốn)\b", re.IGNORECASE),
]

_GREETING = re.compile(
    r"^(chào|hi|hello|xin chào|shop ơi|alo|a lô|hey)\b", re.IGNORECASE
)
_JOINING = re.compile(
    r"^(mình|em|tôi|anh|chị)\s+(mới|vừa)\s+(vào|đến|join)", re.IGNORECASE
)

_PRAISE = re.compile(
    r"(xinh|đẹp|tuyệt|hay|thích|yêu|love|cảm ơn|cam on|thanks|tks|thank you|quá đỉnh|tuyệt vời|hay quá|đẹp quá|xinh quá)",
    re.IGNORECASE,
)
_PRAISE_EMOJI = re.compile(r"[❤💕👍🔥💯🥰😍👏🙏💖]+")

_PRICING = re.compile(
    r"\b(giá|bao nhiêu|bao nhieu|bn|giảm giá|khuyến mãi|khuyen mai|sale|mã|voucher|coupon|rẻ|đắt)\b",
    re.IGNORECASE,
)
_SHIPPING = re.compile(
    r"\b(ship|giao hàng|giao hang|vận chuyển|van chuyen|cod|freeship|free ship|phí ship)\b",
    re.IGNORECASE,
)
_COMPLAINT = re.compile(
    r"\b(lỗi|hỏng|bể|tệ|kém|dở|chậm|trễ|sai|nhầm|hoàn|trả hàng|không được|hư)\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(
    r"(\?|không|có|sao|thế nào|the nao|bao lâu|bao lau|khi nào|ở đâu|nào|gì|gi\b|hả|nhỉ|vậy)",
    re.IGNORECASE,
)


def classify_rule_based(text: str, shop_rules: ShopRules | None = None) -> ClassifyResult:
    """Fast classification — runs on every comment. Target: <1ms."""
    rules = shop_rules or ShopRules()
    text_stripped = text.strip()
    text_lower = text_stripped.lower()

    # --- Shop custom blocklist (highest priority) ---
    if rules.blocked_keywords:
        for keyword in rules.blocked_keywords:
            if keyword.lower() in text_lower:
                return ClassifyResult(
                    intent="blocked", confidence=0.95,
                    action="hide",
                    reason=f"Matched blocked keyword: {keyword}",
                )

    # --- Shop custom blocked patterns ---
    for pattern_str in rules.blocked_patterns:
        try:
            if re.search(pattern_str, text_lower, re.IGNORECASE):
                return ClassifyResult(
                    intent="blocked", confidence=0.95,
                    action="hide",
                    reason=f"Matched blocked pattern: {pattern_str}",
                )
        except re.error:
            pass  # skip invalid regex

    # --- Empty / too short ---
    if not text_stripped:
        return ClassifyResult(intent="spam", confidence=0.95, action="hide")

    if len(text_stripped) < rules.min_comment_length:
        return ClassifyResult(intent="noise", confidence=0.8, action="ignore")

    # --- Spam detection ---
    if rules.auto_hide_spam:
        for pattern in _SPAM_PATTERNS:
            if pattern.search(text_stripped):
                return ClassifyResult(
                    intent="spam", confidence=0.9, action="hide",
                    reason="Spam pattern detected",
                )

    # Link-only filter
    if rules.auto_hide_links and re.search(r"https?://", text_stripped, re.IGNORECASE):
        return ClassifyResult(
            intent="spam", confidence=0.9, action="hide",
            reason="Contains link",
        )

    # Very long text (likely copy-paste spam)
    if len(text_stripped) > 500:
        return ClassifyResult(intent="spam", confidence=0.85, action="hide", reason="Unusually long comment")

    # Emoji flood
    if _EMOJI_FLOOD.search(text_stripped):
        return ClassifyResult(intent="noise", confidence=0.8, action="ignore", reason="Emoji flood")

    # Count emoji ratio
    emoji_count = sum(1 for c in text_stripped if ord(c) > 0x1F600)
    if emoji_count >= rules.emoji_flood_threshold and emoji_count > len(text_stripped) * 0.5:
        return ClassifyResult(intent="noise", confidence=0.8, action="ignore", reason="Emoji flood")

    # --- Toxic detection ---
    if rules.auto_flag_toxic:
        for pattern in _TOXIC_PATTERNS:
            if pattern.search(text_lower):
                return ClassifyResult(
                    intent="toxic", confidence=0.8, action="flag",
                    reason="Toxic content detected",
                )

    # --- Blacklisted user (checked at caller level usually, but also here for safety) ---

    # --- Greeting ---
    if (_GREETING.search(text_stripped) or _JOINING.search(text_stripped)) and len(text_stripped) < 40:
        return ClassifyResult(intent="greeting", confidence=0.8, action="skip_ai")

    # --- Praise ---
    if _PRAISE.search(text_stripped) or _PRAISE_EMOJI.search(text_stripped):
        # Only pure praise if short
        if len(text_stripped) < 50:
            return ClassifyResult(intent="praise", confidence=0.7, action="skip_ai")

    # --- Pricing questions ---
    if _PRICING.search(text_stripped):
        return ClassifyResult(intent="pricing", confidence=0.85, action="generate_ai")

    # --- Shipping questions ---
    if _SHIPPING.search(text_stripped):
        return ClassifyResult(intent="shipping", confidence=0.85, action="generate_ai")

    # --- Complaints ---
    if _COMPLAINT.search(text_stripped):
        return ClassifyResult(intent="complaint", confidence=0.8, action="generate_ai")

    # --- General questions ---
    if _QUESTION.search(text_stripped):
        return ClassifyResult(intent="question", confidence=0.7, action="generate_ai")

    # --- Low confidence — could be anything ---
    return ClassifyResult(intent="other", confidence=0.4, action="generate_ai")


# ====== Tier 2: LLM-based (only for low-confidence) ======

_LLM_CLASSIFY_PROMPT = """Phân loại comment livestream sau thành 1 trong các loại:
- question: câu hỏi về sản phẩm
- pricing: hỏi về giá, khuyến mãi
- shipping: hỏi về giao hàng
- complaint: phàn nàn, khiếu nại
- praise: khen ngợi
- greeting: chào hỏi
- spam: quảng cáo, link lạ
- toxic: nội dung tiêu cực, xúc phạm
- noise: không có nội dung ý nghĩa

Comment: "{text}"

Trả lời CHỈ 1 từ (tên loại). Không giải thích."""

_INTENT_ACTION_MAP = {
    "question": "generate_ai",
    "pricing": "generate_ai",
    "shipping": "generate_ai",
    "complaint": "generate_ai",
    "praise": "skip_ai",
    "greeting": "skip_ai",
    "spam": "hide",
    "toxic": "flag",
    "noise": "ignore",
}

_VALID_INTENTS = frozenset(_INTENT_ACTION_MAP.keys())


async def _check_llm_rate(shop_id: int, limit: int) -> bool:
    """Rate limit LLM classify calls: max `limit` per minute per shop."""
    r = _get_redis()
    key = f"llm_classify_rate:{shop_id}:{int(time.time()) // 60}"
    count = await r.incr(key)
    if count == 1:
        await r.expire(key, 65)
    return count <= limit


async def classify_llm(text: str) -> ClassifyResult:
    """Expensive classification via LLM — only for low-confidence cases."""
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key, transport="rest")
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = _LLM_CLASSIFY_PROMPT.format(text=text[:200])

    response = model.generate_content(prompt, generation_config={"max_output_tokens": 10})
    intent = response.text.strip().lower()

    if intent not in _VALID_INTENTS:
        intent = "other"

    return ClassifyResult(
        intent=intent,
        confidence=0.85,
        action=_INTENT_ACTION_MAP.get(intent, "generate_ai"),
    )


async def classify(
    text: str,
    shop_id: int,
    shop_rules: ShopRules | None = None,
    external_user_id: str | None = None,
) -> ClassifyResult:
    """Combined classifier: Tier 1 rule-based, Tier 2 LLM fallback."""
    rules = shop_rules or ShopRules()

    # Whitelist bypass — trusted users skip all filters
    if external_user_id and external_user_id in rules.whitelisted_users:
        return ClassifyResult(intent="question", confidence=1.0, action="generate_ai", reason="Whitelisted user")

    # Blacklisted user — auto hide
    if external_user_id and external_user_id in rules.blacklisted_users:
        return ClassifyResult(intent="blocked", confidence=1.0, action="hide", reason="Blacklisted user")

    # Tier 1: rule-based
    result = classify_rule_based(text, rules)

    # High confidence — use directly
    if result.confidence >= 0.6:
        return result

    # Tier 2: LLM fallback (only if enabled and within rate limit)
    if rules.use_llm_classify:
        if await _check_llm_rate(shop_id, rules.llm_classify_rate_limit):
            try:
                return await classify_llm(text)
            except Exception:
                pass  # fall through to rule-based result

    return result
