"""Comprehensive safety tests for F9 — Auto-Reply Mode.

This test suite covers ALL safety invariants:
- Default OFF
- Whitelist intents (greeting, thanks, FAQ match)
- Blacklist intents (complaint, pricing)
- Blacklist conditions (numbers, long comments)
- Confidence thresholds
- Rate limits
- Plan checks
- Undo tracking / auto-disable
- Schema validation

Total: 50+ test cases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from pydantic import ValidationError

from app.schemas.auto_reply import AutoReplyDecision, AutoReplyToggleRequest
from app.services.auto_reply import (
    AUTO_REPLY_PLANS,
    BLACKLISTED_INTENTS,
    DEFAULT_FAQ_THRESHOLD,
    FAQ_ELIGIBLE_INTENTS,
    MAX_COMMENT_LENGTH,
    NUMBERS_PATTERN,
    RATE_LIMIT_PER_HOUR,
    RATE_LIMIT_PER_MINUTE,
    UNDO_THRESHOLD,
    WHITELIST_MIN_CONFIDENCE,
    WHITELISTED_INTENTS,
    should_auto_reply,
    check_rate_limit,
    record_undo,
)


# --- Fixtures ---


def make_comment(text="Chào shop", intent="greeting", confidence=0.95):
    """Create a mock Comment object."""
    c = MagicMock()
    c.text_ = text
    c.intent = intent
    c.confidence = confidence
    c.id = 1
    return c


def make_suggestion(rag_faq_ids=None):
    """Create a mock Suggestion object."""
    s = MagicMock()
    s.id = 10
    s.text_ = "Chào bạn! Cảm ơn đã ghé thăm live."
    s.rag_faq_ids = rag_faq_ids
    return s


def make_session(auto_reply_enabled=True, threshold=0.9):
    """Create a mock LiveSession object."""
    s = MagicMock()
    s.id = 100
    s.shop_id = 1
    s.metadata_ = {
        "auto_reply_enabled": auto_reply_enabled,
        "auto_reply_threshold": threshold,
    }
    return s


# --- Schema tests ---


class TestAutoReplyToggleRequest:
    def test_enable(self):
        req = AutoReplyToggleRequest(enabled=True)
        assert req.enabled is True
        assert req.threshold == 0.9  # default

    def test_disable(self):
        req = AutoReplyToggleRequest(enabled=False)
        assert req.enabled is False

    def test_custom_threshold(self):
        req = AutoReplyToggleRequest(enabled=True, threshold=0.95)
        assert req.threshold == 0.95

    def test_threshold_too_low_rejects(self):
        with pytest.raises(ValidationError):
            AutoReplyToggleRequest(enabled=True, threshold=0.3)

    def test_threshold_too_high_rejects(self):
        with pytest.raises(ValidationError):
            AutoReplyToggleRequest(enabled=True, threshold=1.1)

    def test_threshold_min_boundary(self):
        req = AutoReplyToggleRequest(enabled=True, threshold=0.5)
        assert req.threshold == 0.5

    def test_threshold_max_boundary(self):
        req = AutoReplyToggleRequest(enabled=True, threshold=1.0)
        assert req.threshold == 1.0


class TestAutoReplyDecision:
    def test_allowed(self):
        d = AutoReplyDecision(allowed=True, reason="Greeting auto-reply")
        assert d.allowed is True

    def test_blocked(self):
        d = AutoReplyDecision(allowed=False, reason="Complaint")
        assert d.allowed is False


# --- Constants tests ---


class TestConstants:
    def test_blacklisted_intents(self):
        assert "complaint" in BLACKLISTED_INTENTS
        assert "pricing" in BLACKLISTED_INTENTS
        assert "greeting" not in BLACKLISTED_INTENTS

    def test_whitelisted_intents(self):
        assert "greeting" in WHITELISTED_INTENTS
        assert "thanks" in WHITELISTED_INTENTS
        assert "complaint" not in WHITELISTED_INTENTS

    def test_faq_eligible_intents(self):
        assert "question" in FAQ_ELIGIBLE_INTENTS
        assert "shipping" in FAQ_ELIGIBLE_INTENTS

    def test_no_overlap_between_whitelist_and_blacklist(self):
        assert WHITELISTED_INTENTS.isdisjoint(BLACKLISTED_INTENTS)

    def test_rate_limits(self):
        assert RATE_LIMIT_PER_MINUTE == 5
        assert RATE_LIMIT_PER_HOUR == 30

    def test_max_comment_length(self):
        assert MAX_COMMENT_LENGTH == 100

    def test_default_faq_threshold(self):
        assert DEFAULT_FAQ_THRESHOLD == 0.9

    def test_whitelist_min_confidence(self):
        assert WHITELIST_MIN_CONFIDENCE == 0.8

    def test_undo_threshold(self):
        assert UNDO_THRESHOLD == 2

    def test_auto_reply_plans(self):
        assert "pro" in AUTO_REPLY_PLANS
        assert "enterprise" in AUTO_REPLY_PLANS
        assert "trial" not in AUTO_REPLY_PLANS
        assert "starter" not in AUTO_REPLY_PLANS


# --- Numbers pattern tests ---


class TestNumbersPattern:
    def test_3_digits_matches(self):
        assert NUMBERS_PATTERN.search("giá 150k") is not None

    def test_phone_number_matches(self):
        assert NUMBERS_PATTERN.search("gọi 0901234567") is not None

    def test_order_code_matches(self):
        assert NUMBERS_PATTERN.search("mã đơn 123456") is not None

    def test_2_digits_no_match(self):
        assert NUMBERS_PATTERN.search("có 2 màu") is None

    def test_1_digit_no_match(self):
        assert NUMBERS_PATTERN.search("muốn 1 cái") is None

    def test_no_digits_no_match(self):
        assert NUMBERS_PATTERN.search("chào shop") is None

    def test_price_with_dot_matches(self):
        assert NUMBERS_PATTERN.search("199.000đ") is not None


# --- Core decision logic tests ---


@pytest.mark.asyncio
class TestShouldAutoReplyDefault:
    """Test: auto-reply is OFF by default."""

    async def test_disabled_by_default(self):
        comment = make_comment()
        suggestion = make_suggestion()
        session = make_session(auto_reply_enabled=False)
        decision = await should_auto_reply(comment, suggestion, session, "pro")
        assert decision.allowed is False
        assert "chưa bật" in decision.reason

    async def test_empty_metadata(self):
        comment = make_comment()
        suggestion = make_suggestion()
        session = MagicMock()
        session.id = 100
        session.shop_id = 1
        session.metadata_ = {}
        decision = await should_auto_reply(comment, suggestion, session, "pro")
        assert decision.allowed is False

    async def test_none_metadata(self):
        comment = make_comment()
        suggestion = make_suggestion()
        session = MagicMock()
        session.id = 100
        session.shop_id = 1
        session.metadata_ = None
        decision = await should_auto_reply(comment, suggestion, session, "pro")
        assert decision.allowed is False


@pytest.mark.asyncio
class TestShouldAutoReplyPlanCheck:
    """Test: only Pro and Enterprise plans can use auto-reply."""

    async def test_trial_plan_rejected(self):
        decision = await should_auto_reply(
            make_comment(), make_suggestion(), make_session(), "trial"
        )
        assert decision.allowed is False
        assert "Gói" in decision.reason

    async def test_starter_plan_rejected(self):
        decision = await should_auto_reply(
            make_comment(), make_suggestion(), make_session(), "starter"
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_pro_plan_allowed(self, _mock_rate):
        decision = await should_auto_reply(
            make_comment(), make_suggestion(), make_session(), "pro"
        )
        assert decision.allowed is True

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_enterprise_plan_allowed(self, _mock_rate):
        decision = await should_auto_reply(
            make_comment(), make_suggestion(), make_session(), "enterprise"
        )
        assert decision.allowed is True


@pytest.mark.asyncio
class TestShouldAutoReplyWhitelist:
    """Test: only whitelisted intents get auto-reply."""

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_greeting_allowed(self, _):
        decision = await should_auto_reply(
            make_comment("Chào shop ơi", "greeting", 0.95),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is True
        assert "Greeting" in decision.reason

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_thanks_allowed(self, _):
        decision = await should_auto_reply(
            make_comment("Cảm ơn shop", "thanks", 0.90),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is True
        assert "Thanks" in decision.reason

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_faq_match_allowed(self, _):
        decision = await should_auto_reply(
            make_comment("Ship bao lâu?", "question", 0.95),
            make_suggestion(rag_faq_ids=[42]),
            make_session(threshold=0.9),
            "pro",
        )
        assert decision.allowed is True
        assert "FAQ" in decision.reason

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_shipping_faq_match_allowed(self, _):
        decision = await should_auto_reply(
            make_comment("Giao hàng mấy ngày?", "shipping", 0.92),
            make_suggestion(rag_faq_ids=[10]),
            make_session(threshold=0.9),
            "pro",
        )
        assert decision.allowed is True

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_faq_no_match_ids_rejected(self, _):
        """FAQ intent but no rag_faq_ids → not auto-replied."""
        decision = await should_auto_reply(
            make_comment("Ship bao lâu?", "question", 0.95),
            make_suggestion(rag_faq_ids=None),
            make_session(),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_faq_empty_ids_rejected(self, _):
        decision = await should_auto_reply(
            make_comment("Ship bao lâu?", "question", 0.95),
            make_suggestion(rag_faq_ids=[]),
            make_session(),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_unknown_intent_rejected(self, _):
        decision = await should_auto_reply(
            make_comment("Hmm", "unknown", 0.5),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False


@pytest.mark.asyncio
class TestShouldAutoReplyBlacklist:
    """Test: blacklisted intents NEVER get auto-reply."""

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_complaint_always_blocked(self, _):
        decision = await should_auto_reply(
            make_comment("Sản phẩm tệ quá", "complaint", 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False
        assert "Khiếu nại" in decision.reason

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_pricing_always_blocked(self, _):
        decision = await should_auto_reply(
            make_comment("Giá bao nhiêu", "pricing", 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False
        assert "Giá" in decision.reason

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_comment_with_numbers_blocked(self, _):
        decision = await should_auto_reply(
            make_comment("Gọi 0901234567", "greeting", 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False
        assert "số" in decision.reason

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_comment_with_price_blocked(self, _):
        decision = await should_auto_reply(
            make_comment("Giá 150k được không", "greeting", 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False
        assert "số" in decision.reason

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_comment_with_order_code_blocked(self, _):
        decision = await should_auto_reply(
            make_comment("Mã đơn 123456", "greeting", 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_long_comment_blocked(self, _):
        long_text = "Chào shop, " + "a" * 100  # > 100 chars
        decision = await should_auto_reply(
            make_comment(long_text, "greeting", 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False
        assert "dài" in decision.reason

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_exactly_100_chars_allowed(self, _):
        text = "C" * 100  # exactly 100 chars
        decision = await should_auto_reply(
            make_comment(text, "greeting", 0.95),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is True

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_101_chars_blocked(self, _):
        text = "C" * 101  # 101 chars
        decision = await should_auto_reply(
            make_comment(text, "greeting", 0.95),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False


@pytest.mark.asyncio
class TestShouldAutoReplyConfidence:
    """Test: confidence threshold enforcement."""

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_greeting_low_confidence_rejected(self, _):
        decision = await should_auto_reply(
            make_comment("Chào", "greeting", 0.7),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_greeting_exactly_threshold_allowed(self, _):
        decision = await should_auto_reply(
            make_comment("Chào shop", "greeting", 0.8),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is True

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_greeting_below_threshold_rejected(self, _):
        decision = await should_auto_reply(
            make_comment("Chào", "greeting", 0.79),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_faq_below_custom_threshold_rejected(self, _):
        decision = await should_auto_reply(
            make_comment("Ship bao lâu", "question", 0.85),
            make_suggestion(rag_faq_ids=[1]),
            make_session(threshold=0.9),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_faq_at_custom_threshold_allowed(self, _):
        decision = await should_auto_reply(
            make_comment("Ship bao lâu", "question", 0.9),
            make_suggestion(rag_faq_ids=[1]),
            make_session(threshold=0.9),
            "pro",
        )
        assert decision.allowed is True

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_none_confidence_rejected(self, _):
        decision = await should_auto_reply(
            make_comment("Chào", "greeting", None),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False


@pytest.mark.asyncio
class TestShouldAutoReplyRateLimit:
    """Test: rate limit triggers auto-disable."""

    async def test_rate_limit_exceeded_blocks(self):
        mock_redis = AsyncMock()
        mock_session = make_session()

        with patch("app.services.auto_reply._get_redis", return_value=mock_redis):
            with patch("app.services.auto_reply.check_rate_limit", return_value=False):
                with patch("app.services.auto_reply.disable_auto_reply") as mock_disable:
                    decision = await should_auto_reply(
                        make_comment(), make_suggestion(), mock_session, "pro"
                    )
                    assert decision.allowed is False
                    assert "giới hạn" in decision.reason
                    mock_disable.assert_called_once()


# --- Rate limit function tests ---


@pytest.mark.asyncio
class TestCheckRateLimit:
    async def test_within_limits(self):
        r = AsyncMock()
        pipe = AsyncMock()
        pipe.execute = AsyncMock(return_value=[1, 1])
        r.pipeline = MagicMock(return_value=pipe)
        r.expire = AsyncMock()

        result = await check_rate_limit(r, session_id=100)
        assert result is True

    async def test_minute_exceeded(self):
        r = AsyncMock()
        pipe = AsyncMock()
        pipe.execute = AsyncMock(return_value=[6, 6])  # > 5/min
        r.pipeline = MagicMock(return_value=pipe)

        result = await check_rate_limit(r, session_id=100)
        assert result is False

    async def test_hour_exceeded(self):
        r = AsyncMock()
        pipe = AsyncMock()
        pipe.execute = AsyncMock(return_value=[1, 31])  # > 30/hour
        r.pipeline = MagicMock(return_value=pipe)

        result = await check_rate_limit(r, session_id=100)
        assert result is False

    async def test_at_minute_limit_ok(self):
        r = AsyncMock()
        pipe = AsyncMock()
        pipe.execute = AsyncMock(return_value=[5, 5])  # exactly at limit
        r.pipeline = MagicMock(return_value=pipe)
        r.expire = AsyncMock()

        result = await check_rate_limit(r, session_id=100)
        assert result is True

    async def test_at_hour_limit_ok(self):
        r = AsyncMock()
        pipe = AsyncMock()
        pipe.execute = AsyncMock(return_value=[1, 30])  # exactly at limit
        r.pipeline = MagicMock(return_value=pipe)
        r.expire = AsyncMock()

        result = await check_rate_limit(r, session_id=100)
        assert result is True


# --- Undo tracking tests ---


@pytest.mark.asyncio
class TestRecordUndo:
    async def test_first_undo_no_disable(self):
        r = AsyncMock()
        r.incr = AsyncMock(return_value=1)
        r.expire = AsyncMock()

        should_disable = await record_undo(r, session_id=100)
        assert should_disable is False

    async def test_second_undo_triggers_disable(self):
        r = AsyncMock()
        r.incr = AsyncMock(return_value=2)

        should_disable = await record_undo(r, session_id=100)
        assert should_disable is True

    async def test_third_undo_still_triggers(self):
        r = AsyncMock()
        r.incr = AsyncMock(return_value=3)

        should_disable = await record_undo(r, session_id=100)
        assert should_disable is True


# --- Edge case tests ---


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_two_digit_number_allowed(self, _):
        """Two-digit numbers (e.g. 'có 2 màu', 'size 38') should be allowed."""
        decision = await should_auto_reply(
            make_comment("Có 2 màu không shop", "greeting", 0.95),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is True

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_blacklist_checked_before_whitelist(self, _):
        """Complaint intent should be blocked even with high confidence."""
        decision = await should_auto_reply(
            make_comment("Tệ quá", "complaint", 1.0),
            make_suggestion(rag_faq_ids=[1, 2, 3]),
            make_session(),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_numbers_checked_before_whitelist(self, _):
        """Numbers should block even a greeting intent."""
        decision = await should_auto_reply(
            make_comment("Chào shop, SĐT 0901234567", "greeting", 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_length_checked_before_whitelist(self, _):
        """Long comment should block even a greeting intent."""
        long_greeting = "Chào shop ơi, " + "rất vui " * 15  # > 100 chars
        decision = await should_auto_reply(
            make_comment(long_greeting, "greeting", 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_unknown_intent_default_blocked(self, _):
        """Unknown/unmapped intents should default to blocked."""
        decision = await should_auto_reply(
            make_comment("xyz", "random_intent", 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False

    @patch("app.services.auto_reply.check_rate_limit", return_value=True)
    async def test_none_intent_blocked(self, _):
        decision = await should_auto_reply(
            make_comment("hello", None, 0.99),
            make_suggestion(),
            make_session(),
            "pro",
        )
        assert decision.allowed is False
