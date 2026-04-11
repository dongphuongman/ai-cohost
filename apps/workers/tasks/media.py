import json
import logging

import httpx
import redis
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from celery_app import app
from config import settings

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


HEYGEN_API_URL = "https://api.heygen.com"


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


def _add_watermark(video_bytes: bytes) -> bytes:
    """Add 'Nội dung tạo bởi AI' watermark to video via ffmpeg.

    Watermark: semi-transparent text at bottom-right corner.
    Falls back to original bytes if ffmpeg is unavailable.
    """
    import os
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as inp:
        inp.write(video_bytes)
        input_path = inp.name

    output_path = input_path.replace(".mp4", "_wm.mp4")

    try:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", (
                "drawtext=text='Nội dung tạo bởi AI':"
                "fontcolor=white@0.5:fontsize=18:"
                "x=w-tw-20:y=h-th-20:"
                "shadowcolor=black@0.3:shadowx=1:shadowy=1"
            ),
            "-codec:a", "copy",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)

        with open(output_path, "rb") as f:
            result = f.read()
        return result
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("ffmpeg watermark failed, returning original video")
        return video_bytes
    finally:
        for p in (input_path, output_path):
            try:
                os.unlink(p)
            except OSError:
                pass


@app.task(
    name="tasks.media.generate_dh_video",
    soft_time_limit=600,
    max_retries=2,
    acks_late=True,
)
def generate_dh_video(video_id: int) -> dict:
    """Generate digital human video via HeyGen API.

    The output video MUST include a visible 'Nội dung tạo bởi AI'
    watermark overlay to comply with Vietnamese regulations on synthetic media.
    """
    import os
    import time
    from datetime import datetime, timedelta

    with Session(_sync_engine) as session:
        video = _get_video(session, video_id)
        if not video:
            logger.error("DH video %d not found", video_id)
            return {"status": "error", "video_id": video_id}

        shop_id = video["shop_id"]
        _update_video(session, video_id, status="processing")

        try:
            if not settings.heygen_api_key:
                raise RuntimeError("HEYGEN_API_KEY not configured")

            # 1. Resolve voice config
            voice_config: dict
            if video["voice_clone_id"]:
                vc = _get_voice(session, video["voice_clone_id"])
                if vc and vc["provider_voice_id"]:
                    voice_config = {
                        "type": "elevenlabs",
                        "voice_id": vc["provider_voice_id"],
                        "input_text": video["source_text"],
                    }
                else:
                    voice_config = {
                        "type": "text",
                        "input_text": video["source_text"],
                    }
            else:
                voice_config = {
                    "type": "text",
                    "input_text": video["source_text"],
                }

            # 2. Call HeyGen API to create video
            payload = {
                "video_inputs": [{
                    "character": {
                        "type": "avatar",
                        "avatar_id": video["avatar_preset"] or "default_avatar",
                    },
                    "voice": voice_config,
                    "background": {
                        "type": "color",
                        "value": video["background"] or "#FFFFFF",
                    },
                }],
                "dimension": {"width": 1280, "height": 720},
            }

            response = httpx.post(
                f"{HEYGEN_API_URL}/v2/video/generate",
                headers={"X-Api-Key": settings.heygen_api_key},
                json=payload,
                timeout=60,
            )

            if response.status_code != 200:
                raise RuntimeError(f"HeyGen API error: {response.status_code} {response.text}")

            heygen_video_id = response.json()["data"]["video_id"]
            _update_video(session, video_id, provider_job_id=heygen_video_id)

            # 3. Poll for completion (max ~10 minutes)
            max_polls = 60
            for _ in range(max_polls):
                time.sleep(10)

                status_resp = httpx.get(
                    f"{HEYGEN_API_URL}/v1/video_status.get",
                    params={"video_id": heygen_video_id},
                    headers={"X-Api-Key": settings.heygen_api_key},
                    timeout=30,
                )

                status_data = status_resp.json()["data"]

                if status_data["status"] == "completed":
                    video_url_heygen = status_data["video_url"]
                    duration = status_data.get("duration", 0)

                    # 4. Download video from HeyGen
                    video_bytes = httpx.get(video_url_heygen, timeout=120).content

                    # 5. Add watermark (mandatory)
                    video_bytes = _add_watermark(video_bytes)

                    # 6. Store video
                    # TODO: Upload to R2/S3 when storage is ready
                    import uuid
                    video_key = f"videos/{shop_id}/{video_id}_{uuid.uuid4().hex[:8]}.mp4"
                    stored_url = f"storage://{video_key}"

                    # 7. Update DB
                    now = datetime.utcnow()
                    _update_video(
                        session,
                        video_id,
                        status="ready",
                        video_url=stored_url,
                        video_duration_seconds=int(duration),
                        file_size_bytes=len(video_bytes),
                        completed_at=now,
                        expires_at=now + timedelta(days=30),
                    )

                    # 8. Notify
                    _redis_client.publish(
                        f"notifications:{shop_id}",
                        json.dumps({
                            "type": "video.ready",
                            "video_id": video_id,
                            "message": "Video digital human đã sẵn sàng!",
                        }),
                    )

                    logger.info(
                        "DH video %d ready: duration=%ds size=%d",
                        video_id, int(duration), len(video_bytes),
                    )
                    return {"status": "ready", "video_id": video_id}

                elif status_data["status"] == "failed":
                    error_msg = status_data.get("error", "Unknown HeyGen error")
                    raise RuntimeError(f"HeyGen processing failed: {error_msg}")

            raise RuntimeError("HeyGen processing timeout after 10 minutes")

        except Exception:
            logger.exception("DH video %d failed", video_id)

            error_text = str(Exception)[:500] if Exception else "Unknown error"
            _update_video(session, video_id, status="failed")

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
