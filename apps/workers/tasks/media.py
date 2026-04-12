import json
import logging

import httpx
import redis
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from celery_app import app
from config import settings
from dh_providers import DHProviderRouter, GenerateRequest

logger = logging.getLogger(__name__)

# Sync DB engine for Celery tasks
_sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
    "postgresql+asyncpg", "postgresql"
)
_sync_engine = create_engine(_sync_db_url)
_redis_client = redis.from_url(settings.redis_url)


def _get_voice(session: Session, voice_id: int) -> dict | None:
    result = session.execute(
        sa.text("SELECT * FROM voice_clones WHERE id = :id"), {"id": voice_id}
    )
    row = result.mappings().first()
    return dict(row) if row else None


def _update_voice(session: Session, voice_id: int, **kwargs) -> None:
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    session.execute(
        sa.text(f"UPDATE voice_clones SET {sets} WHERE id = :id"),
        {"id": voice_id, **kwargs},
    )
    session.commit()


@app.task(name="tasks.media.generate_tts", soft_time_limit=30)
def generate_tts(suggestion_id: int, text: str, voice_id: str | None = None) -> dict:
    """Generate TTS audio for a suggestion."""
    return {"status": "not_implemented", "suggestion_id": suggestion_id}


def _get_video(session: Session, video_id: int) -> dict | None:
    result = session.execute(
        sa.text("SELECT * FROM dh_videos WHERE id = :id"), {"id": video_id}
    )
    row = result.mappings().first()
    return dict(row) if row else None


def _update_video(session: Session, video_id: int, **kwargs) -> None:
    sets = ", ".join(f"{k} = :{k}" for k in kwargs)
    session.execute(
        sa.text(f"UPDATE dh_videos SET {sets} WHERE id = :id"),
        {"id": video_id, **kwargs},
    )
    session.commit()


@app.task(
    name="tasks.media.generate_dh_video",
    soft_time_limit=600,
    max_retries=2,
    acks_late=True,
)
def generate_dh_video(video_id: int) -> dict:
    """Generate a digital human video via the provider router.

    The router selects LiteAvatar by default and falls back to HeyGen when
    LiteAvatar is unavailable, doesn't support the requested avatar, or its
    generate() call fails. When ``LITE_AVATAR_URL`` is unset (Đợt 1 default),
    the router always picks HeyGen — production behavior is unchanged.

    The output video MUST include a visible 'Nội dung tạo bởi AI' watermark
    to comply with Vietnamese regulations on synthetic media. Watermarking
    runs inside each provider's ``finalize()`` step.
    """
    import time
    from datetime import datetime, timedelta, timezone

    with Session(_sync_engine) as session:
        video = _get_video(session, video_id)
        if not video:
            logger.error("DH video %d not found", video_id)
            return {"status": "error", "video_id": video_id}

        shop_id = video["shop_id"]
        _update_video(session, video_id, status="processing")

        try:
            # 1. Resolve voice clone (ElevenLabs voice id) if specified
            voice_id: str | None = None
            if video["voice_clone_id"]:
                vc = _get_voice(session, video["voice_clone_id"])
                if vc and vc["provider_voice_id"]:
                    voice_id = vc["provider_voice_id"]

            # 2. Build provider-agnostic request
            request = GenerateRequest(
                text=video["source_text"],
                avatar_id=video["avatar_preset"] or "default_avatar",
                voice_id=voice_id,
                background=video["background"] or "#FFFFFF",
                prefer_quality=bool(video.get("prefer_quality", False)),
                shop_id=shop_id,
            )

            # 3. Route → trigger generation
            router = DHProviderRouter()
            create_response = router.generate(request)

            _update_video(
                session,
                video_id,
                provider=create_response.provider,
                provider_job_id=create_response.job_id,
            )

            # 4. Poll until ready (max ~10 minutes), then finalize
            max_polls = 60
            for _ in range(max_polls):
                time.sleep(10)

                status = router.get_status(create_response.provider, create_response.job_id)

                if status.status == "ready":
                    finalized = router.finalize(status, shop_id=shop_id)

                    now = datetime.now(timezone.utc)
                    _update_video(
                        session,
                        video_id,
                        status="ready",
                        video_url=finalized.video_url,
                        video_duration_seconds=finalized.duration_seconds,
                        file_size_bytes=finalized.file_size_bytes,
                        credits_used=finalized.cost_usd or None,
                        completed_at=now,
                        expires_at=now + timedelta(days=30),
                    )

                    _redis_client.publish(
                        f"notifications:{shop_id}",
                        json.dumps({
                            "type": "video.ready",
                            "video_id": video_id,
                            "message": "Video digital human đã sẵn sàng!",
                        }),
                    )

                    logger.info(
                        "DH video %d ready via %s: duration=%ss size=%s cost=$%.4f",
                        video_id,
                        finalized.provider,
                        finalized.duration_seconds,
                        finalized.file_size_bytes,
                        finalized.cost_usd,
                    )
                    return {"status": "ready", "video_id": video_id, "provider": finalized.provider}

                if status.status == "failed":
                    raise RuntimeError(
                        f"{status.provider} processing failed: {status.error_message}"
                    )

            raise RuntimeError(
                f"{create_response.provider} processing timeout after 10 minutes"
            )

        except Exception as exc:
            logger.exception("DH video %d failed", video_id)

            error_text = str(exc)[:500]
            _update_video(session, video_id, status="failed", error_message=error_text)

            _redis_client.publish(
                f"notifications:{shop_id}",
                json.dumps({
                    "type": "video.failed",
                    "video_id": video_id,
                    "message": "Không thể tạo video. Vui lòng thử lại.",
                }),
            )

            raise


@app.task(
    name="tasks.media.clone_voice",
    soft_time_limit=300,
    max_retries=2,
    acks_late=True,
)
def clone_voice(voice_clone_id: int) -> dict:
    """Clone voice via ElevenLabs Instant Voice Cloning API."""
    with Session(_sync_engine) as session:
        voice = _get_voice(session, voice_clone_id)
        if not voice:
            logger.error("Voice clone %d not found", voice_clone_id)
            return {"status": "error", "voice_clone_id": voice_clone_id}

        shop_id = voice["shop_id"]

        try:
            if not settings.elevenlabs_api_key:
                raise RuntimeError("ELEVENLABS_API_KEY not configured")

            # 1. Download audio from storage
            # TODO: Replace with actual R2/S3 download when storage is ready
            audio_url = voice["source_audio_url"]
            if audio_url.startswith("storage://"):
                logger.warning(
                    "Storage download not implemented yet for voice %d, "
                    "using placeholder for ElevenLabs API call",
                    voice_clone_id,
                )
                raise RuntimeError(
                    "File storage not yet implemented. "
                    "Configure R2/S3 to enable voice cloning."
                )

            audio_bytes = httpx.get(audio_url, timeout=60).content

            # 2. Call ElevenLabs API
            response = httpx.post(
                "https://api.elevenlabs.io/v1/voices/add",
                headers={"xi-api-key": settings.elevenlabs_api_key},
                data={
                    "name": f"cohost_{shop_id}_{voice_clone_id}",
                    "description": voice["description"] or "",
                },
                files={
                    "files": (
                        f"voice_{voice_clone_id}.mp3",
                        audio_bytes,
                        "audio/mpeg",
                    ),
                },
                timeout=120,
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"ElevenLabs API error: {response.status_code} {response.text}"
                )

            provider_voice_id = response.json()["voice_id"]

            # 3. Update DB
            _update_voice(
                session,
                voice_clone_id,
                provider_voice_id=provider_voice_id,
                status="ready",
            )

            # 4. Notify via Redis pub/sub
            _redis_client.publish(
                f"notifications:{shop_id}",
                json.dumps({
                    "type": "voice.ready",
                    "voice_id": voice_clone_id,
                    "name": voice["name"],
                    "message": f"Giọng nói \"{voice['name']}\" đã sẵn sàng sử dụng!",
                }),
            )

            logger.info("Voice clone %d ready: provider_id=%s", voice_clone_id, provider_voice_id)
            return {"status": "ready", "voice_clone_id": voice_clone_id}

        except Exception as e:
            logger.exception("Voice clone %d failed", voice_clone_id)

            _update_voice(session, voice_clone_id, status="failed")

            _redis_client.publish(
                f"notifications:{shop_id}",
                json.dumps({
                    "type": "voice.failed",
                    "voice_id": voice_clone_id,
                    "message": f"Không thể tạo giọng nói \"{voice['name']}\". Vui lòng thử lại.",
                }),
            )

            raise
