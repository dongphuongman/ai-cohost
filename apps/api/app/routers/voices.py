import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.database import get_db
from app.schemas.voices import VoiceCloneCreate, VoiceCloneResponse, VoiceTestRequest
from app.services.voices import (
    create_voice_clone,
    delete_voice_clone,
    get_voice_clone,
    list_voice_clones,
    test_voice,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voices", tags=["voices"])


@router.get("", response_model=list[VoiceCloneResponse])
async def list_voices(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    return await list_voice_clones(db, shop.shop_id)


@router.post("", response_model=VoiceCloneResponse, status_code=201)
async def create_voice(
    name: str = Form(..., min_length=1, max_length=200),
    consent_person_name: str = Form(..., min_length=2, max_length=200),
    consent_confirmed: bool = Form(...),
    audio_file: UploadFile = File(...),
    consent_file: UploadFile = File(...),
    description: str | None = Form(None),
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    """Create a voice clone. Requires audio sample + signed consent form (PDF)."""
    data = VoiceCloneCreate(
        name=name,
        description=description,
        consent_person_name=consent_person_name,
        consent_confirmed=consent_confirmed,
    )

    try:
        voice = await create_voice_clone(
            db, shop.shop_id, shop.user_id, data, audio_file, consent_file,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return voice


@router.get("/{voice_id}", response_model=VoiceCloneResponse)
async def get_voice(
    voice_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    voice = await get_voice_clone(db, voice_id, shop.shop_id)
    if not voice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Giọng nói không tồn tại")
    return voice


@router.delete("/{voice_id}", status_code=204)
async def delete_voice(
    voice_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    try:
        await delete_voice_clone(db, voice_id, shop.shop_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{voice_id}/test")
async def test_voice_endpoint(
    voice_id: int,
    body: VoiceTestRequest = VoiceTestRequest(),
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    """Test a cloned voice by generating TTS audio."""
    voice = await get_voice_clone(db, voice_id, shop.shop_id)
    if not voice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Giọng nói không tồn tại")
    if voice.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Giọng nói chưa sẵn sàng",
        )

    try:
        audio_bytes = await test_voice(voice, body.text)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.get("/{voice_id}/consent")
async def download_consent(
    voice_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    """Return the consent form URL for download."""
    voice = await get_voice_clone(db, voice_id, shop.shop_id)
    if not voice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Giọng nói không tồn tại")

    return {"consent_form_url": voice.consent_form_url, "consent_person_name": voice.consent_person_name}
