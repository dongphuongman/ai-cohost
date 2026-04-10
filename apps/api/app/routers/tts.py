"""TTS (Text-to-Speech) endpoint for reading suggestions aloud."""

import io
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    voice: str = Field(default="vi-VN-HoaiMyNeural")


@router.post("/generate")
async def generate_tts(
    body: TTSRequest,
    shop: ShopContext = Depends(get_current_shop),
):
    """Generate TTS audio for a suggestion text. Returns MP3 stream."""
    try:
        # Use edge-tts (free, no API key needed) as primary TTS
        import edge_tts

        communicate = edge_tts.Communicate(body.text, body.voice)
        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_buffer.seek(0)
        return StreamingResponse(
            audio_buffer,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=tts.mp3"},
        )
    except ImportError:
        logger.warning("edge-tts not installed, TTS unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS service không khả dụng",
        )
    except Exception:
        logger.exception("TTS generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể tạo audio",
        )
