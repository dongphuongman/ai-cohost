"""Tests for voice clone schemas, validation, and service helpers."""

import pytest
from pydantic import ValidationError

from app.schemas.voices import VoiceCloneCreate, VoiceTestRequest, VoiceLinkRequest
from app.services.voices import (
    ALLOWED_AUDIO_EXTENSIONS,
    MAX_AUDIO_SIZE,
    MAX_CONSENT_SIZE,
    _get_extension,
    validate_audio_file,
    validate_consent_file,
)


# --- Schema validation tests ---


class TestVoiceCloneCreateSchema:
    def test_valid_create(self):
        data = VoiceCloneCreate(
            name="Linh Female",
            description="Giọng nữ miền Nam",
            consent_person_name="Nguyễn Thị Linh",
            consent_confirmed=True,
        )
        assert data.name == "Linh Female"
        assert data.consent_person_name == "Nguyễn Thị Linh"

    def test_missing_consent_confirmed_rejects(self):
        with pytest.raises(ValidationError) as exc_info:
            VoiceCloneCreate(
                name="Test",
                consent_person_name="Người test",
                consent_confirmed=False,
            )
        assert "đồng ý" in str(exc_info.value).lower() or "consent" in str(exc_info.value).lower()

    def test_missing_person_name_rejects(self):
        with pytest.raises(ValidationError):
            VoiceCloneCreate(
                name="Test",
                consent_person_name="A",  # too short (min 2)
                consent_confirmed=True,
            )

    def test_whitespace_only_person_name_rejects(self):
        with pytest.raises(ValidationError):
            VoiceCloneCreate(
                name="Test",
                consent_person_name="   ",  # strips to empty
                consent_confirmed=True,
            )

    def test_person_name_stripped(self):
        data = VoiceCloneCreate(
            name="Test",
            consent_person_name="  Nguyễn Văn A  ",
            consent_confirmed=True,
        )
        assert data.consent_person_name == "Nguyễn Văn A"

    def test_name_too_long_rejects(self):
        with pytest.raises(ValidationError):
            VoiceCloneCreate(
                name="x" * 201,
                consent_person_name="Người test",
                consent_confirmed=True,
            )

    def test_empty_name_rejects(self):
        with pytest.raises(ValidationError):
            VoiceCloneCreate(
                name="",
                consent_person_name="Người test",
                consent_confirmed=True,
            )


class TestVoiceTestRequest:
    def test_default_text(self):
        req = VoiceTestRequest()
        assert "AI Co-host" in req.text

    def test_custom_text(self):
        req = VoiceTestRequest(text="Hello world")
        assert req.text == "Hello world"

    def test_empty_text_rejects(self):
        with pytest.raises(ValidationError):
            VoiceTestRequest(text="")

    def test_text_too_long_rejects(self):
        with pytest.raises(ValidationError):
            VoiceTestRequest(text="x" * 501)


class TestVoiceLinkRequest:
    def test_link(self):
        req = VoiceLinkRequest(voice_clone_id=42)
        assert req.voice_clone_id == 42

    def test_unlink(self):
        req = VoiceLinkRequest(voice_clone_id=None)
        assert req.voice_clone_id is None

    def test_default_unlink(self):
        req = VoiceLinkRequest()
        assert req.voice_clone_id is None


# --- File validation helpers ---


class TestGetExtension:
    def test_mp3(self):
        assert _get_extension("voice.mp3") == ".mp3"

    def test_wav(self):
        assert _get_extension("recording.WAV") == ".wav"

    def test_no_extension(self):
        assert _get_extension("noext") == ""

    def test_none_filename(self):
        assert _get_extension(None) == ""

    def test_multiple_dots(self):
        assert _get_extension("my.voice.m4a") == ".m4a"


class TestFileValidationConstants:
    def test_allowed_extensions(self):
        assert ".wav" in ALLOWED_AUDIO_EXTENSIONS
        assert ".mp3" in ALLOWED_AUDIO_EXTENSIONS
        assert ".m4a" in ALLOWED_AUDIO_EXTENSIONS
        assert ".exe" not in ALLOWED_AUDIO_EXTENSIONS

    def test_audio_size_limit(self):
        assert MAX_AUDIO_SIZE == 50 * 1024 * 1024

    def test_consent_size_limit(self):
        assert MAX_CONSENT_SIZE == 10 * 1024 * 1024


# --- Async file validation tests ---


class FakeUploadFile:
    """Minimal UploadFile mock for testing validation."""

    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


@pytest.mark.asyncio
class TestValidateAudioFile:
    async def test_valid_mp3(self):
        audio = FakeUploadFile("voice.mp3", b"\x00" * 5000)
        result = await validate_audio_file(audio)
        assert len(result) == 5000

    async def test_valid_wav(self):
        audio = FakeUploadFile("voice.wav", b"\x00" * 5000)
        result = await validate_audio_file(audio)
        assert len(result) == 5000

    async def test_invalid_extension_rejects(self):
        audio = FakeUploadFile("voice.exe", b"\x00" * 5000)
        with pytest.raises(ValueError, match="Định dạng file"):
            await validate_audio_file(audio)

    async def test_too_large_rejects(self):
        audio = FakeUploadFile("voice.mp3", b"\x00" * (MAX_AUDIO_SIZE + 1))
        with pytest.raises(ValueError, match="quá lớn"):
            await validate_audio_file(audio)

    async def test_too_small_rejects(self):
        audio = FakeUploadFile("voice.mp3", b"\x00" * 100)
        with pytest.raises(ValueError, match="quá nhỏ"):
            await validate_audio_file(audio)


@pytest.mark.asyncio
class TestValidateConsentFile:
    async def test_valid_pdf(self):
        consent = FakeUploadFile("consent.pdf", b"%PDF" + b"\x00" * 500)
        result = await validate_consent_file(consent)
        assert len(result) == 504

    async def test_non_pdf_rejects(self):
        consent = FakeUploadFile("consent.docx", b"\x00" * 500)
        with pytest.raises(ValueError, match="PDF"):
            await validate_consent_file(consent)

    async def test_too_large_rejects(self):
        consent = FakeUploadFile("consent.pdf", b"\x00" * (MAX_CONSENT_SIZE + 1))
        with pytest.raises(ValueError, match="quá lớn"):
            await validate_consent_file(consent)

    async def test_too_small_rejects(self):
        consent = FakeUploadFile("consent.pdf", b"\x00" * 10)
        with pytest.raises(ValueError, match="rỗng"):
            await validate_consent_file(consent)
