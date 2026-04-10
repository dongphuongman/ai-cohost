"""Fast intent classification for live comments — keyword-based, no LLM call."""

import re

# Non-actionable intents: skip LLM suggestion generation
SKIP_INTENTS = frozenset({"greeting", "thanks", "praise", "spam"})

_GREETING = re.compile(
    r"\b(chào|hi|hello|hey|shop ơi|xin chào|alo|a lô)\b", re.IGNORECASE
)
_THANKS = re.compile(
    r"\b(cảm ơn|cam on|thank|tks|cám ơn|xinh quá|đẹp quá|tuyệt vời|hay quá|quá đỉnh)\b",
    re.IGNORECASE,
)
_PRICING = re.compile(
    r"\b(giá|bao nhiêu|bao nhieu|bn|giảm giá|khuyến mãi|khuyen mai|sale|mã|voucher|coupon|rẻ|đắt)\b",
    re.IGNORECASE,
)
_SHIPPING = re.compile(
    r"\b(ship|giao hàng|giao hang|vận chuyển|van chuyen|cod|freeship|free ship|phí ship)\b",
    re.IGNORECASE,
)
_COMPLAINT = re.compile(
    r"\b(lỗi|hỏng|bể|fake|giả|scam|tệ|kém|dở|chậm|trễ|sai|nhầm|hoàn|trả)\b",
    re.IGNORECASE,
)
_SPAM_PATTERNS = re.compile(r"(https?://|@@|###|t\.me/|bit\.ly)", re.IGNORECASE)
_QUESTION_MARKERS = re.compile(
    r"(\?|không|có|sao|thế nào|the nao|bao lâu|bao lau|khi nào|ở đâu|nào|gì|gi\b|hả|nhỉ|vậy)",
    re.IGNORECASE,
)


def classify(text: str) -> tuple[str, float]:
    """Classify a comment's intent. Returns (intent, confidence).

    Intents: spam, greeting, thanks, praise, pricing, shipping, complaint, question, other.
    """
    text = text.strip()
    if not text:
        return ("spam", 0.9)

    # Spam: links, long text, repetitive patterns
    if _SPAM_PATTERNS.search(text) or len(text) > 500:
        return ("spam", 0.9)

    # Very short emoji-only or short meaningless
    if len(text) < 3:
        return ("praise", 0.7)

    # Count emoji ratio
    emoji_count = sum(1 for c in text if ord(c) > 0x1F600)
    if emoji_count > 3 and emoji_count > len(text) * 0.5:
        return ("praise", 0.7)

    if _GREETING.search(text) and len(text) < 30:
        return ("greeting", 0.8)

    if _THANKS.search(text):
        return ("thanks", 0.8)

    if _COMPLAINT.search(text):
        return ("complaint", 0.8)

    if _PRICING.search(text):
        return ("pricing", 0.85)

    if _SHIPPING.search(text):
        return ("shipping", 0.85)

    if _QUESTION_MARKERS.search(text):
        return ("question", 0.7)

    return ("other", 0.5)
