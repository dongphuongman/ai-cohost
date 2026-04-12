"""HeyGen provider — premium fallback (~$0.40/min)."""
from __future__ import annotations

import logging

import httpx

from config import settings

from .base import (
    DHProvider,
    GenerateRequest,
    GenerateResponse,
    add_watermark,
    save_video_artifact,
)

logger = logging.getLogger(__name__)

HEYGEN_API_URL = "https://api.heygen.com"


class HeyGenProvider(DHProvider):
    """Wraps the HeyGen v2 video generation API."""

    name = "heygen"
    supports_custom_avatar = True  # HeyGen supports presets + instant-avatar uploads
    cost_per_minute_usd = 0.40

    def __init__(self, api_key: str | None = None, http_client: httpx.Client | None = None):
        self._api_key = api_key if api_key is not None else settings.heygen_api_key
        self._http = http_client  # injectable for tests

    # ------------------------------------------------------------------ checks

    def is_available(self) -> bool:
        return bool(self._api_key)

    def supports_avatar(self, avatar_id: str) -> bool:
        # HeyGen accepts any preset or custom avatar id — no allowlist needed.
        return True

    # ------------------------------------------------------------------ http

    def _client(self) -> httpx.Client:
        return self._http or httpx.Client()

    def _headers(self) -> dict:
        return {"X-Api-Key": self._api_key}

    # ------------------------------------------------------------------ API

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        if not self._api_key:
            raise RuntimeError("HEYGEN_API_KEY not configured")

        voice_config: dict
        if request.voice_id:
            voice_config = {
                "type": "elevenlabs",
                "voice_id": request.voice_id,
                "input_text": request.text,
            }
        else:
            voice_config = {"type": "text", "input_text": request.text}

        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": request.avatar_id or "default_avatar",
                    },
                    "voice": voice_config,
                    "background": {
                        "type": "color",
                        "value": request.background or "#FFFFFF",
                    },
                }
            ],
            "dimension": {"width": 1280, "height": 720},
        }

        response = self._client().post(
            f"{HEYGEN_API_URL}/v2/video/generate",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HeyGen API error: {response.status_code} {response.text}")

        heygen_video_id = response.json()["data"]["video_id"]
        logger.info("HeyGen job created: %s", heygen_video_id)
        return GenerateResponse(
            provider=self.name,
            job_id=heygen_video_id,
            status="processing",
        )

    def get_status(self, job_id: str) -> GenerateResponse:
        if not self._api_key:
            raise RuntimeError("HEYGEN_API_KEY not configured")

        status_resp = self._client().get(
            f"{HEYGEN_API_URL}/v1/video_status.get",
            params={"video_id": job_id},
            headers=self._headers(),
            timeout=30,
        )
        data = status_resp.json()["data"]
        heygen_status = data.get("status")

        if heygen_status == "completed":
            return GenerateResponse(
                provider=self.name,
                job_id=job_id,
                status="ready",
                video_url=data.get("video_url"),
                duration_seconds=int(data.get("duration") or 0) or None,
                raw=data,
            )
        if heygen_status == "failed":
            return GenerateResponse(
                provider=self.name,
                job_id=job_id,
                status="failed",
                error_message=data.get("error", "Unknown HeyGen error"),
                raw=data,
            )
        return GenerateResponse(
            provider=self.name,
            job_id=job_id,
            status="processing",
            raw=data,
        )

    # --------------------------------------------------------------- finalize

    def finalize(self, response: GenerateResponse, shop_id: int) -> GenerateResponse:
        """Download → watermark → store. Mutates only the URL/size fields."""
        if response.status != "ready" or not response.video_url:
            return response

        video_bytes = self._client().get(response.video_url, timeout=120).content
        video_bytes = add_watermark(video_bytes)
        stored_url = save_video_artifact(video_bytes, shop_id=shop_id)

        duration_seconds = response.duration_seconds
        cost_usd = 0.0
        if duration_seconds:
            cost_usd = round((duration_seconds / 60.0) * self.cost_per_minute_usd, 4)

        return GenerateResponse(
            provider=self.name,
            job_id=response.job_id,
            status="ready",
            video_url=stored_url,
            duration_seconds=duration_seconds,
            file_size_bytes=len(video_bytes),
            cost_usd=cost_usd,
            raw=response.raw,
        )
