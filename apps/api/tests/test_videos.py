"""Tests for digital human video schemas, validation, and service helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.schemas.videos import (
    MAX_TEXT_LENGTH,
    VideoGenerateRequest,
    VideoResponse,
    VideoShareResponse,
)
from app.services.digital_human import (
    PREFER_QUALITY_PLANS,
    WORDS_PER_MINUTE,
    estimate_duration_minutes,
    generate_video,
)
from app.services.usage import QuotaStatus


# --- Schema validation tests ---


class TestVideoGenerateRequest:
    def test_valid_request(self):
        data = VideoGenerateRequest(
            text="Xin chào, đây là sản phẩm kem chống nắng SPF50.",
            avatar_preset="default_avatar",
            background="#FFFFFF",
        )
        assert data.text.startswith("Xin chào")
        assert data.avatar_preset == "default_avatar"
        assert "has_watermark" not in VideoGenerateRequest.model_fields

    def test_with_script_id(self):
        data = VideoGenerateRequest(
            text="Test content",
            script_id=42,
        )
        assert data.script_id == 42

    def test_with_voice_clone(self):
        data = VideoGenerateRequest(
            text="Test content",
            voice_clone_id=7,
        )
        assert data.voice_clone_id == 7

    def test_empty_text_rejects(self):
        with pytest.raises(ValidationError):
            VideoGenerateRequest(text="")

    def test_whitespace_only_text_rejects(self):
        with pytest.raises(ValidationError, match="không được để trống"):
            VideoGenerateRequest(text="   ")

    def test_text_too_long_rejects(self):
        with pytest.raises(ValidationError):
            VideoGenerateRequest(text="x" * (MAX_TEXT_LENGTH + 1))

    def test_text_at_max_length(self):
        data = VideoGenerateRequest(text="x" * MAX_TEXT_LENGTH)
        assert len(data.text) == MAX_TEXT_LENGTH

    def test_text_stripped(self):
        data = VideoGenerateRequest(text="  Hello world  ")
        assert data.text == "Hello world"

    def test_defaults(self):
        data = VideoGenerateRequest(text="Test")
        assert data.script_id is None
        assert data.voice_clone_id is None
        assert data.avatar_preset == "default_avatar"
        assert data.background == "#FFFFFF"


class TestVideoResponse:
    def test_from_attributes(self):
        assert VideoResponse.model_config["from_attributes"] is True

    def test_has_watermark_field(self):
        """VideoResponse must expose has_watermark so frontend can show disclosure."""
        fields = VideoResponse.model_fields
        assert "has_watermark" in fields
        assert "status" in fields
        assert "video_url" in fields
        assert "error_message" in fields

    def test_has_all_required_fields(self):
        fields = set(VideoResponse.model_fields.keys())
        expected = {
            "id", "shop_id", "created_by", "script_id", "source_text",
            "avatar_preset", "avatar_custom_url", "voice_clone_id",
            "background", "provider", "provider_job_id", "video_url",
            "video_duration_seconds", "file_size_bytes", "has_watermark",
            "status", "error_message", "credits_used", "created_at",
            "completed_at", "expires_at", "prefer_quality",
        }
        assert expected.issubset(fields)


class TestVideoShareResponse:
    def test_fields(self):
        fields = set(VideoShareResponse.model_fields.keys())
        assert "share_url" in fields
        assert "expires_at" in fields


# --- Service helper tests ---


class TestEstimateDuration:
    def test_150_words_is_1_minute(self):
        text = " ".join(["word"] * 150)
        assert estimate_duration_minutes(text) == pytest.approx(1.0)

    def test_300_words_is_2_minutes(self):
        text = " ".join(["word"] * 300)
        assert estimate_duration_minutes(text) == pytest.approx(2.0)

    def test_short_text_minimum(self):
        """Even very short text should return at least 0.1 minutes."""
        assert estimate_duration_minutes("Hi") >= 0.1

    def test_empty_after_split_minimum(self):
        assert estimate_duration_minutes("hello") >= 0.1

    def test_words_per_minute_constant(self):
        assert WORDS_PER_MINUTE == 150


# --- Watermark enforcement tests ---


class TestWatermarkEnforcement:
    """Verify that has_watermark cannot be set to False in the model."""

    def test_request_has_no_watermark_field(self):
        """VideoGenerateRequest should NOT have a has_watermark field —
        callers cannot opt out of watermarking."""
        assert "has_watermark" not in VideoGenerateRequest.model_fields

    def test_max_text_length_constant(self):
        assert MAX_TEXT_LENGTH == 5000


# --- prefer_quality plan-gate tests ---


class _PlanResult:
    """Mimic SQLAlchemy Result with ``scalar_one_or_none``."""

    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
class TestPreferQualityPlanGate:
    """The ``prefer_quality`` flag pins the expensive HeyGen path; only Pro/
    Enterprise may set it. Without this gate any user could bypass the
    LiteAvatar cost optimization (see digital_human.py:46)."""

    async def _make_request(self):
        return VideoGenerateRequest(text="Test content", prefer_quality=True)

    async def test_prefer_quality_blocks_starter_plan(self):
        db = MagicMock()
        db.execute = AsyncMock(return_value=_PlanResult("starter"))
        data = await self._make_request()

        ok_quota = QuotaStatus(used=0, limit=10, remaining=10)
        with patch(
            "app.services.digital_human.check_quota",
            new=AsyncMock(return_value=ok_quota),
        ):
            with pytest.raises(ValueError, match="Pro"):
                await generate_video(db, shop_id=1, user_id=1, data=data)

        # Gate must fire before any INSERT.
        db.add.assert_not_called()

    async def test_prefer_quality_allows_pro_plan(self):
        import sys
        import types

        db = MagicMock()
        db.execute = AsyncMock(return_value=_PlanResult("pro"))
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        data = await self._make_request()

        ok_quota = QuotaStatus(used=0, limit=10, remaining=10)

        # ``generate_video`` does ``from celery import current_app`` inline to
        # avoid a hard dep at import time. In the test env celery may be
        # absent, so we inject a stub module before the import fires.
        fake_celery_module = types.ModuleType("celery")
        fake_current_app = MagicMock()
        fake_current_app.send_task = MagicMock()
        fake_celery_module.current_app = fake_current_app

        with patch.dict(sys.modules, {"celery": fake_celery_module}), patch(
            "app.services.digital_human.check_quota",
            new=AsyncMock(return_value=ok_quota),
        ), patch(
            "app.services.digital_human.track_usage",
            new=AsyncMock(),
        ):
            video = await generate_video(db, shop_id=1, user_id=1, data=data)

        assert video.prefer_quality is True
        assert video.has_watermark is True
        db.add.assert_called_once()
        fake_current_app.send_task.assert_called_once()

    def test_plan_set_contains_expected_tiers(self):
        assert "pro" in PREFER_QUALITY_PLANS
        assert "enterprise" in PREFER_QUALITY_PLANS
        assert "starter" not in PREFER_QUALITY_PLANS
        assert "trial" not in PREFER_QUALITY_PLANS
