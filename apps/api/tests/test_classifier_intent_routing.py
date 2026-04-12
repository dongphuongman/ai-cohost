"""Regression tests for high-intent comment routing.

Guards three bugs found in the session 21/22 audit on 2026-04-12:

1. Greeting/praise prefixes used to swallow real questions because the
   greeting check ran before the pricing/shipping check.
   Example: "Shop ơi giá bao nhiêu vậy ạ?" → greeting → skip_ai → no
   suggestion generated → lost sale.

2. "hay" was in the praise regex but is also a Vietnamese conjunction
   meaning "or", so product-usage questions like "Dùng trước hay sau
   kem chống nắng?" were tagged as praise and skipped.

3. Greeting/praise checks did not look at "?" or question words, so
   any short comment ending in "?" but containing "shop ơi" still
   skipped AI.

If any of these tests fail, the AI comment responder is silently
losing buying-intent comments — DO NOT skip-fix.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing")

import pytest

from app.services.comment_classifier import classify_rule_based


# (text, expected_action, optional_expected_intent_or_None)
HIGH_INTENT_CASES = [
    # --- Bug #1: greeting/praise prefix should not swallow specific intent ---
    ("Shop ơi giá bao nhiêu vậy ạ?", "generate_ai", "pricing"),
    ("Shop ơi cái này giá ạ?", "generate_ai", "pricing"),
    ("Chào shop, sản phẩm này bao nhiêu?", "generate_ai", "pricing"),
    ("Shop ơi ship COD không?", "generate_ai", "shipping"),
    ("Shop ơi bán sỉ không?", "generate_ai", None),  # routed via question guardrail
    ("Hi shop, giá sỉ thế nào ạ?", "generate_ai", None),

    # --- Bug #2: "hay" homograph should not be praise ---
    ("Dùng trước hay sau kem chống nắng?", "generate_ai", None),
    ("Loại này hay loại kia ạ?", "generate_ai", None),
    ("Mua online hay tại shop?", "generate_ai", None),

    # --- Bug #3: question mark guardrail ---
    ("Có mùi thơm không shop ơi?", "generate_ai", None),
    ("Da dầu dùng được không?", "generate_ai", None),
    ("Có tester gửi kèm không shop?", "generate_ai", None),
    # "giảm" alone (without "giá") isn't in _PRICING regex on purpose —
    # avoids false positive on "giảm cân" etc. Routes via question
    # guardrail; intent ends up "question" but action is correct.
    ("Combo 2 cái giảm thêm không?", "generate_ai", None),
    ("Có ship COD không shop?", "generate_ai", "shipping"),

    # --- Pricing keyword variants ---
    ("Có mã giảm giá không?", "generate_ai", "pricing"),
    ("Mua 3 cái free ship luôn không?", "generate_ai", "shipping"),
    ("Đang có khuyến mãi gì không ạ?", "generate_ai", "pricing"),
]


@pytest.mark.parametrize("text,expected_action,expected_intent", HIGH_INTENT_CASES)
def test_high_intent_routes_to_ai(text, expected_action, expected_intent):
    result = classify_rule_based(text)
    assert result.action == expected_action, (
        f"Comment {text!r} got action={result.action!r} (intent={result.intent!r}, "
        f"confidence={result.confidence}); expected action={expected_action!r}. "
        f"Reason={result.reason!r}"
    )
    if expected_intent is not None:
        assert result.intent == expected_intent, (
            f"Comment {text!r} got intent={result.intent!r}, "
            f"expected {expected_intent!r}"
        )


# Negative tests — pure greeting/praise must still be skipped to avoid
# burning AI quota on chitchat. These were the original behaviors and
# must be preserved.
PURE_CHITCHAT_CASES = [
    ("Chào shop ơi mới vào nè", "skip_ai", "greeting"),
    ("Hi shop", "skip_ai", "greeting"),
    ("Hello", "skip_ai", "greeting"),
    ("Mình mới vào live", "skip_ai", "greeting"),
    ("Thích quá luôn", "skip_ai", "praise"),
    ("Đẹp quá shop ơi", "skip_ai", "praise"),
    ("Sản phẩm hay quá!", "skip_ai", "praise"),
    ("Hay thật đấy shop", "skip_ai", "praise"),
    ("Love sản phẩm này", "skip_ai", "praise"),
]


@pytest.mark.parametrize("text,expected_action,expected_intent", PURE_CHITCHAT_CASES)
def test_pure_chitchat_still_skipped(text, expected_action, expected_intent):
    result = classify_rule_based(text)
    assert result.action == expected_action, (
        f"Pure chitchat {text!r} got action={result.action!r}, "
        f"expected {expected_action!r}. Reason={result.reason!r}"
    )
    assert result.intent == expected_intent, (
        f"Chitchat {text!r} got intent={result.intent!r}, "
        f"expected {expected_intent!r}"
    )
