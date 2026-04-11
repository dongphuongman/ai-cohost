"""Tests for digital human video schemas, validation, and service helpers."""

import pytest
from pydantic import ValidationError

from app.schemas.videos import (
    MAX_TEXT_LENGTH,
    VideoGenerateRequest,
    VideoResponse,
    VideoShareResponse,
)
from app.services.digital_human import WORDS_PER_MINUTE, estimate_duration_minutes


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
            "completed_at", "expires_at",
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
