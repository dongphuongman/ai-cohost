"""Tests for comment_classifier — rule-based tier (30+ cases)."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing")

import pytest

from app.services.comment_classifier import ClassifyResult, ShopRules, classify_rule_based


# ====== Spam detection (10 cases) ======


def test_spam_http_link():
    r = classify_rule_based("Check out https://spam.com for deals")
    assert r.intent == "spam"
    assert r.action == "hide"


def test_spam_telegram_link():
    r = classify_rule_based("Join t.me/spamgroup now")
    assert r.intent == "spam"
    assert r.action == "hide"


def test_spam_whatsapp_link():
    r = classify_rule_based("Message me wa.me/123456")
    assert r.intent == "spam"
    assert r.action == "hide"


def test_spam_bitly_link():
    r = classify_rule_based("Click bit.ly/abc123")
    assert r.intent == "spam"
    assert r.action == "hide"


def test_spam_multiple_mentions():
    r = classify_rule_based("@user1 @user2 buy my stuff")
    assert r.intent == "spam"
    assert r.action == "hide"


def test_spam_character_repeat():
    r = classify_rule_based("aaaaaaaaa")
    assert r.intent == "spam"
    assert r.action == "hide"


def test_spam_empty():
    r = classify_rule_based("")
    assert r.intent == "spam"
    assert r.action == "hide"


def test_spam_very_long():
    r = classify_rule_based("x" * 501)
    assert r.intent == "spam"
    assert r.action == "hide"


def test_spam_link_only_filter():
    rules = ShopRules(auto_hide_links=True)
    r = classify_rule_based("Check https://example.com", rules)
    assert r.intent == "spam"
    assert r.action == "hide"


def test_spam_link_disabled():
    """When auto_hide_links=False but auto_hide_spam=False, links pass through."""
    rules = ShopRules(auto_hide_spam=False, auto_hide_links=False)
    r = classify_rule_based("Check https://example.com")
    # Still caught by default spam patterns if auto_hide_spam is True
    # With both disabled, should not be spam
    r = classify_rule_based("Check https://example.com", rules)
    assert r.action != "hide"


# ====== Toxic detection (5 cases) ======


def test_toxic_scam():
    r = classify_rule_based("Shop bán hàng giả, mọi người đừng mua")
    assert r.intent == "toxic"
    assert r.action == "flag"


def test_toxic_lua_dao():
    r = classify_rule_based("Lừa đảo rồi mọi người ơi")
    assert r.intent == "toxic"
    assert r.action == "flag"


def test_toxic_fake():
    r = classify_rule_based("Đồ fake 100%")
    assert r.intent == "toxic"
    assert r.action == "flag"


def test_toxic_disabled():
    rules = ShopRules(auto_flag_toxic=False)
    r = classify_rule_based("Shop bán hàng giả", rules)
    assert r.action != "flag"


def test_toxic_case_insensitive():
    r = classify_rule_based("SCAM shop này")
    assert r.intent == "toxic"
    assert r.action == "flag"


# ====== Greeting detection (5 cases) ======


def test_greeting_chao():
    r = classify_rule_based("Chào shop")
    assert r.intent == "greeting"
    assert r.action == "skip_ai"


def test_greeting_hi():
    r = classify_rule_based("Hi shop ơi")
    assert r.intent == "greeting"
    assert r.action == "skip_ai"


def test_greeting_hello():
    r = classify_rule_based("Hello")
    assert r.intent == "greeting"
    assert r.action == "skip_ai"


def test_greeting_join():
    r = classify_rule_based("Mình mới vào live")
    assert r.intent == "greeting"
    assert r.action == "skip_ai"


def test_greeting_long_not_greeting():
    """Long text starting with greeting should NOT be classified as greeting."""
    r = classify_rule_based("Chào shop, mình muốn hỏi về sản phẩm này giá bao nhiêu vậy ạ")
    assert r.intent != "greeting"


# ====== Praise detection (5 cases) ======


def test_praise_dep():
    r = classify_rule_based("Đẹp quá")
    assert r.intent == "praise"
    assert r.action == "skip_ai"


def test_praise_cam_on():
    r = classify_rule_based("Cảm ơn shop")
    # Note: this matches _PRAISE but also could match thanks pattern
    assert r.action == "skip_ai"


def test_praise_emoji():
    r = classify_rule_based("❤💕👍")
    assert r.action == "skip_ai"


def test_praise_love():
    r = classify_rule_based("Love sản phẩm này")
    assert r.intent == "praise"
    assert r.action == "skip_ai"


def test_praise_long_is_question():
    """Longer text with praise + question should generate AI when over praise threshold."""
    r = classify_rule_based("Sản phẩm đẹp quá, mình muốn hỏi là có size L cho người cao 1m75 không ạ?")
    assert r.action == "generate_ai"


# ====== Question / actionable detection (5 cases) ======


def test_question_price():
    r = classify_rule_based("Giá bao nhiêu ạ")
    assert r.intent == "pricing"
    assert r.action == "generate_ai"


def test_question_shipping():
    r = classify_rule_based("Ship về Hà Nội mấy ngày")
    assert r.intent == "shipping"
    assert r.action == "generate_ai"


def test_question_general():
    r = classify_rule_based("Còn hàng không ạ?")
    assert r.intent == "question"
    assert r.action == "generate_ai"


def test_question_complaint():
    r = classify_rule_based("Sản phẩm bị lỗi rồi shop ơi")
    assert r.intent == "complaint"
    assert r.action == "generate_ai"


def test_question_voucher():
    r = classify_rule_based("Có mã giảm giá không shop")
    assert r.intent == "pricing"
    assert r.action == "generate_ai"


# ====== Emoji flood detection ======


def test_emoji_5_ok():
    """5 regular emojis should NOT trigger flood."""
    r = classify_rule_based("Hello 😀😃😄😁😆")
    assert r.intent != "noise"


def test_emoji_flood_6():
    """6+ consecutive emojis from same range should trigger flood."""
    r = classify_rule_based("😀😃😄😁😆😅")
    assert r.intent == "noise"
    assert r.action == "ignore"


# ====== Custom keyword blocklist ======


def test_blocklist_exact_match():
    rules = ShopRules(blocked_keywords=["competitor shop"])
    r = classify_rule_based("Mua bên competitor shop rẻ hơn", rules)
    assert r.intent == "blocked"
    assert r.action == "hide"


def test_blocklist_case_insensitive():
    rules = ShopRules(blocked_keywords=["SPAM"])
    r = classify_rule_based("This is spam content", rules)
    assert r.intent == "blocked"
    assert r.action == "hide"


def test_blocklist_no_match():
    rules = ShopRules(blocked_keywords=["competitor"])
    r = classify_rule_based("Giá bao nhiêu ạ", rules)
    assert r.intent != "blocked"


# ====== Min comment length ======


def test_too_short():
    r = classify_rule_based(".")
    assert r.intent == "noise"
    assert r.action == "ignore"


def test_short_ok():
    r = classify_rule_based("ok")
    # 2 chars meets default min_comment_length=2
    assert r.intent != "noise" or r.confidence < 0.9


# ====== Combined classifier (async) ======


@pytest.mark.asyncio
async def test_classify_whitelist_bypass():
    """Whitelisted users should bypass all filters."""
    from unittest.mock import AsyncMock, patch

    rules = ShopRules(
        whitelisted_users=["trusted_user_123"],
        blocked_keywords=["spam_word"],
    )

    with patch("app.services.comment_classifier._redis", new_callable=AsyncMock):
        from app.services.comment_classifier import classify

        result = await classify(
            "spam_word here",
            shop_id=1,
            shop_rules=rules,
            external_user_id="trusted_user_123",
        )
        assert result.action == "generate_ai"
        assert result.reason == "Whitelisted user"


@pytest.mark.asyncio
async def test_classify_blacklist():
    """Blacklisted users should be auto-hidden."""
    from unittest.mock import AsyncMock, patch

    rules = ShopRules(blacklisted_users=["bad_user_456"])

    with patch("app.services.comment_classifier._redis", new_callable=AsyncMock):
        from app.services.comment_classifier import classify

        result = await classify(
            "Normal question",
            shop_id=1,
            shop_rules=rules,
            external_user_id="bad_user_456",
        )
        assert result.action == "hide"
        assert result.intent == "blocked"


@pytest.mark.asyncio
async def test_classify_spam_no_llm():
    """Spam comments should NOT trigger LLM classification (cost saving)."""
    from unittest.mock import AsyncMock, patch

    with patch("app.services.comment_classifier._redis", new_callable=AsyncMock):
        with patch("app.services.comment_classifier.classify_llm") as mock_llm:
            from app.services.comment_classifier import classify

            result = await classify(
                "Check https://spam.com",
                shop_id=1,
                shop_rules=ShopRules(use_llm_classify=True),
            )
            assert result.action == "hide"
            mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_classify_flagged_no_llm():
    """Flagged (toxic) comments should NOT trigger LLM — already high confidence."""
    from unittest.mock import AsyncMock, patch

    with patch("app.services.comment_classifier._redis", new_callable=AsyncMock):
        with patch("app.services.comment_classifier.classify_llm") as mock_llm:
            from app.services.comment_classifier import classify

            result = await classify(
                "Lừa đảo shop này",
                shop_id=1,
                shop_rules=ShopRules(use_llm_classify=True),
            )
            assert result.action == "flag"
            mock_llm.assert_not_called()
