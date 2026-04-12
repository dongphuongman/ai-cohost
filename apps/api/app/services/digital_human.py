import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.media import DhVideo, VoiceClone
from app.schemas.videos import VideoGenerateRequest
from app.services.usage import check_quota, track_usage

logger = logging.getLogger(__name__)

# Rough estimate: ~150 words per minute of video
WORDS_PER_MINUTE = 150


def estimate_duration_minutes(text: str) -> float:
    word_count = len(text.split())
    return max(word_count / WORDS_PER_MINUTE, 0.1)


async def generate_video(
    db: AsyncSession,
    shop_id: int,
    user_id: int,
    data: VideoGenerateRequest,
) -> DhVideo:
    """Create a digital human video generation job."""
    # 1. Check quota
    quota = await check_quota(db, shop_id, "dh_video")
    estimated = estimate_duration_minutes(data.text)
    if quota.exceeded:
        raise ValueError(
            f"Không đủ quota video. Còn {quota.remaining:.0f} video, "
            f"vui lòng nâng cấp gói."
        )

    # 2. Validate voice clone if specified
    if data.voice_clone_id is not None:
        vc_result = await db.execute(
            select(VoiceClone).where(
                VoiceClone.id == data.voice_clone_id,
                VoiceClone.shop_id == shop_id,
                VoiceClone.deleted_at.is_(None),
            )
        )
        voice = vc_result.scalar_one_or_none()
        if not voice:
            raise ValueError("Giọng nói không tồn tại")
        if voice.status != "ready":
            raise ValueError("Giọng nói chưa sẵn sàng sử dụng")

    # 3. Create DB record — has_watermark is ALWAYS True
    # provider defaults to 'liteavatar' (cheap self-hosted) at the DB level;
    # the worker's DHProviderRouter overwrites it with the actual provider
    # selected at execution time (heygen fallback when liteavatar is down).
    video = DhVideo(
        shop_id=shop_id,
        created_by=user_id,
        script_id=data.script_id,
        source_text=data.text,
        avatar_preset=data.avatar_preset,
        voice_clone_id=data.voice_clone_id,
        background=data.background or "#FFFFFF",
        provider="liteavatar",
        prefer_quality=data.prefer_quality,
        status="queued",
        has_watermark=True,
    )
    db.add(video)
    await db.flush()

    # 4. Track usage
    await track_usage(
        db,
        shop_id=shop_id,
        resource_type="dh_video",
        quantity=1,
        unit="count",
        user_id=user_id,
        resource_id=video.id,
    )

    await db.commit()
    await db.refresh(video)

    # 5. Enqueue async task
    from celery import current_app as celery_app

    celery_app.send_task(
        "tasks.media.generate_dh_video",
        args=[video.id],
        queue="media_queue",
    )

    logger.info(
        "DH video job created: id=%d shop=%d est_minutes=%.1f",
        video.id, shop_id, estimated,
    )

    return video


async def list_videos(
    db: AsyncSession, shop_id: int, limit: int = 50, offset: int = 0
) -> list[DhVideo]:
    result = await db.execute(
        select(DhVideo)
        .where(DhVideo.shop_id == shop_id)
        .order_by(DhVideo.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_video(
    db: AsyncSession, video_id: int, shop_id: int
) -> DhVideo | None:
    result = await db.execute(
        select(DhVideo).where(
            DhVideo.id == video_id,
            DhVideo.shop_id == shop_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_video(
    db: AsyncSession, video_id: int, shop_id: int
) -> None:
    video = await get_video(db, video_id, shop_id)
    if not video:
        raise ValueError("Video không tồn tại")

    # TODO: Remove video file from R2/S3 when storage is implemented
    if video.video_url and not video.video_url.startswith("storage://"):
        try:
            async with httpx.AsyncClient() as client:
                # Best-effort cleanup of remote file
                pass
        except Exception:
            logger.warning("Failed to remove video file: %s", video.video_url)

    await db.delete(video)
    await db.commit()

    logger.info("DH video deleted: id=%d shop=%d", video_id, shop_id)


async def generate_share_link(
    db: AsyncSession, video_id: int, shop_id: int
) -> dict:
    """Generate a temporary share link for a video."""
    video = await get_video(db, video_id, shop_id)
    if not video:
        raise ValueError("Video không tồn tại")
    if video.status != "ready" or not video.video_url:
        raise ValueError("Video chưa sẵn sàng để chia sẻ")

    # Generate a signed/temporary URL
    # TODO: Replace with actual R2 presigned URL when storage is ready
    token = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    share_url = f"{settings.api_url}/api/v1/videos/{video_id}/download?token={token}"

    return {"share_url": share_url, "expires_at": expires_at}
