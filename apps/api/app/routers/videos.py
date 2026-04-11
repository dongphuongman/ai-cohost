import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.database import get_db
from app.schemas.videos import VideoGenerateRequest, VideoResponse, VideoShareResponse
from app.services.digital_human import (
    delete_video,
    generate_share_link,
    generate_video,
    get_video,
    list_videos,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("/", response_model=list[VideoResponse])
async def list_videos_endpoint(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    return await list_videos(db, shop.shop_id)


@router.post("/generate", response_model=VideoResponse, status_code=201)
async def generate_video_endpoint(
    data: VideoGenerateRequest,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    """Create a digital human video generation job."""
    try:
        video = await generate_video(db, shop.shop_id, shop.user_id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return video


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video_endpoint(
    video_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    video = await get_video(db, video_id, shop.shop_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video không tồn tại")
    return video


@router.delete("/{video_id}", status_code=204)
async def delete_video_endpoint(
    video_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_video(db, video_id, shop.shop_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{video_id}/download")
async def download_video(
    video_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    """Return the video download URL."""
    video = await get_video(db, video_id, shop.shop_id)
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video không tồn tại")
    if video.status != "ready" or not video.video_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video chưa sẵn sàng để tải",
        )
    return {"video_url": video.video_url}


@router.get("/{video_id}/share", response_model=VideoShareResponse)
async def share_video(
    video_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    """Generate a temporary share link for a video."""
    try:
        result = await generate_share_link(db, video_id, shop.shop_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return result
