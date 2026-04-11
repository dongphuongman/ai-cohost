import logging
from datetime import datetime, timezone

import httpx
from fastapi import UploadFile
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.content import Persona
from app.models.media import VoiceClone
from app.schemas.voices import VoiceCloneCreate
from app.services.usage import check_quota, track_usage

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_TYPES = {"audio/wav", "audio/mpeg", "audio/mp3", "audio/mp4", "audio/x-m4a", "audio/m4a"}
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a"}
MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_CONSENT_SIZE = 10 * 1024 * 1024  # 10 MB


def _get_extension(filename: str | None) -> str:
    if not filename:
        return ""
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


async def validate_audio_file(audio: UploadFile) -> bytes:
    """Validate audio file format and size. Returns file bytes."""
    ext = _get_extension(audio.filename)
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError(
            f"Định dạng file không hỗ trợ. Chấp nhận: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
        )

    content = await audio.read()
    if len(content) > MAX_AUDIO_SIZE:
        raise ValueError("File âm thanh quá lớn. Giới hạn 50MB.")
    if len(content) < 1000:
        raise ValueError("File âm thanh quá nhỏ hoặc rỗng.")

    return content


async def validate_consent_file(consent: UploadFile) -> bytes:
    """Validate consent PDF file. Returns file bytes."""
    ext = _get_extension(consent.filename)
    if ext != ".pdf":
        raise ValueError("Bản đồng ý phải là file PDF.")

    content = await consent.read()
    if len(content) > MAX_CONSENT_SIZE:
        raise ValueError("File PDF quá lớn. Giới hạn 10MB.")
    if len(content) < 100:
        raise ValueError("File PDF rỗng hoặc không hợp lệ.")

    return content


async def create_voice_clone(
    db: AsyncSession,
    shop_id: int,
    user_id: int,
    data: VoiceCloneCreate,
    audio_file: UploadFile,
    consent_file: UploadFile,
) -> VoiceClone:
    """Create a voice clone with full consent validation."""
    # 1. Check quota
    quota = await check_quota(db, shop_id, "voice_clone")
    if quota.exceeded:
        raise ValueError("Đã đạt giới hạn số giọng clone. Nâng cấp gói để thêm.")

    # 2. Validate files
    audio_bytes = await validate_audio_file(audio_file)
    consent_bytes = await validate_consent_file(consent_file)

    # 3. Store files — for now store as data URIs or local paths
    #    In production, upload to R2/S3. Using placeholder URLs with file size info.
    import uuid

    audio_key = f"voices/{shop_id}/{uuid.uuid4()}{_get_extension(audio_file.filename)}"
    consent_key = f"consents/{shop_id}/{uuid.uuid4()}.pdf"

    # TODO: Replace with actual R2/S3 upload when storage service is ready
    audio_url = f"storage://{audio_key}"
    consent_url = f"storage://{consent_key}"

    # 4. Create DB record
    voice = VoiceClone(
        shop_id=shop_id,
        created_by=user_id,
        name=data.name,
        description=data.description,
        source_audio_url=audio_url,
        consent_form_url=consent_url,
        consent_confirmed_at=datetime.now(timezone.utc),
        consent_confirmed_by=user_id,
        consent_person_name=data.consent_person_name,
        provider="elevenlabs",
        status="processing",
    )
    db.add(voice)
    await db.flush()

    # 5. Track usage
    await track_usage(
        db,
        shop_id=shop_id,
        resource_type="voice_clone",
        quantity=1,
        unit="count",
        user_id=user_id,
        resource_id=voice.id,
    )

    await db.commit()
    await db.refresh(voice)

    # 6. Enqueue async clone task
    from celery import current_app as celery_app

    celery_app.send_task(
        "tasks.media.clone_voice",
        args=[voice.id],
        queue="media_queue",
    )

    logger.info(
        "Voice clone created: id=%d shop=%d person=%s",
        voice.id, shop_id, data.consent_person_name,
    )

    return voice


async def list_voice_clones(
    db: AsyncSession, shop_id: int
) -> list[VoiceClone]:
    result = await db.execute(
        select(VoiceClone)
        .where(VoiceClone.shop_id == shop_id, VoiceClone.deleted_at.is_(None))
        .order_by(VoiceClone.created_at.desc())
    )
    return list(result.scalars().all())


async def get_voice_clone(
    db: AsyncSession, voice_id: int, shop_id: int
) -> VoiceClone | None:
    result = await db.execute(
        select(VoiceClone).where(
            VoiceClone.id == voice_id,
            VoiceClone.shop_id == shop_id,
            VoiceClone.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def delete_voice_clone(
    db: AsyncSession, voice_id: int, shop_id: int
) -> VoiceClone:
    voice = await get_voice_clone(db, voice_id, shop_id)
    if not voice:
        raise ValueError("Giọng nói không tồn tại")

    # 1. Remove from ElevenLabs (best effort)
    if voice.provider_voice_id and settings.elevenlabs_api_key:
        try:
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"https://api.elevenlabs.io/v1/voices/{voice.provider_voice_id}",
                    headers={"xi-api-key": settings.elevenlabs_api_key},
                    timeout=30,
                )
        except Exception:
            logger.warning("Failed to delete voice from ElevenLabs: %s", voice.provider_voice_id)

    # 2. Soft delete
    voice.deleted_at = datetime.now(timezone.utc)

    # 3. Unlink from any personas
    await db.execute(
        update(Persona)
        .where(Persona.voice_clone_id == voice_id)
        .values(voice_clone_id=None)
    )

    await db.commit()

    logger.info("Voice clone deleted: id=%d shop=%d", voice_id, shop_id)
    return voice


async def test_voice(voice: VoiceClone, text: str) -> bytes:
    """Generate TTS audio using the cloned voice via ElevenLabs."""
    if not voice.provider_voice_id:
        raise ValueError("Giọng nói chưa sẵn sàng")

    if not settings.elevenlabs_api_key:
        raise ValueError("ElevenLabs API chưa được cấu hình")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice.provider_voice_id}",
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text[:500],
                "model_id": "eleven_multilingual_v2",
            },
            timeout=30,
        )

    if response.status_code != 200:
        logger.error("ElevenLabs TTS failed: %d %s", response.status_code, response.text)
        raise ValueError("Không thể tạo audio thử nghiệm")

    return response.content


async def link_voice_to_persona(
    db: AsyncSession, persona_id: int, shop_id: int, voice_clone_id: int | None
) -> Persona:
    """Link or unlink a voice clone to a persona."""
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id, Persona.shop_id == shop_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise ValueError("Persona không tồn tại")

    if voice_clone_id is not None:
        voice = await get_voice_clone(db, voice_clone_id, shop_id)
        if not voice:
            raise ValueError("Giọng nói không tồn tại")
        if voice.status != "ready":
            raise ValueError("Giọng nói chưa sẵn sàng sử dụng")

    persona.voice_clone_id = voice_clone_id
    persona.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(persona)
    return persona
