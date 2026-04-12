"""LiteAvatar provider — self-hosted, ~$0/min.

Đợt 2: real implementation talking to the FastAPI worker service in
``services/lite-avatar-worker``. When ``LITE_AVATAR_URL`` is unset the
provider still short-circuits to ``is_available() is False`` — so in
environments without the worker deployed the router transparently falls
back to HeyGen, identical to Đợt 1 behavior.

Interface contract (mandated by ``DHProvider`` base class):
    - Sync methods (NO async) — Celery tasks call these directly.
    - Constructor signature ``(base_url, http_client)`` preserved from
      Đợt 1 so existing tests keep passing unchanged.
    - ``http_client`` is an injected ``httpx.Client``; when None the
      provider spins up a short-lived client per call.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from config import settings

from .base import DHProvider, GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)


class LiteAvatarProvider(DHProvider):
    name = "liteavatar"
    supports_custom_avatar = False  # Only the pre-loaded gallery is supported
    cost_per_minute_usd = 0.0  # Self-hosted

    # Avatars pre-loaded into the worker container. Folder names under
    # services/lite-avatar-worker/avatars/ must match this set.
    AVAILABLE_AVATARS = frozenset(
        {
            "linh_female",
            "nam_male",
            "huong_female",
            "tuan_male",
            "mai_female",
        }
    )

    # Per-request timeouts (seconds). Health is cheap; generate/status are
    # quick too because the worker returns immediately and runs inference
    # on a BackgroundTask — polling is what reveals the actual work.
    HEALTH_TIMEOUT = 5.0
    GENERATE_TIMEOUT = 30.0
    STATUS_TIMEOUT = 10.0

    def __init__(
        self,
        base_url: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self._base_url = base_url if base_url is not None else settings.lite_avatar_url
        self._http = http_client

    # ------------------------------------------------------------------ checks

    def is_available(self) -> bool:
        """Health-check the worker.

        Returns False immediately when ``LITE_AVATAR_URL`` is unset so the
        router cheaply falls back to HeyGen. Never caches: a transient
        outage should not pin us to HeyGen forever.
        """
        if not self._base_url:
            return False
        try:
            r = self._get("/health", timeout=self.HEALTH_TIMEOUT)
            return r.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.warning("LiteAvatar health check failed: %s", exc)
            return False

    def supports_avatar(self, avatar_id: str) -> bool:
        return avatar_id in self.AVAILABLE_AVATARS

    # ------------------------------------------------------------------ API

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        if not self._base_url:
            raise RuntimeError(
                "LiteAvatar worker URL not configured (LITE_AVATAR_URL). "
                "Router should have selected HeyGen before reaching here."
            )

        # Voice cloning: if a voice_id is provided, the API layer is
        # expected to pre-generate audio via ElevenLabs and pass the URL.
        # Until that integration lands we fall back to gTTS inside the
        # worker — log the gap so it's visible in production.
        voice_audio_url = self._generate_elevenlabs_audio(
            request.text, request.voice_id
        )

        payload = {
            "text": request.text,
            "avatar_id": request.avatar_id,
            "voice_audio_url": voice_audio_url,
            "background": request.background,
            "language": request.language,
        }

        r = self._post("/generate", json=payload, timeout=self.GENERATE_TIMEOUT)

        if r.status_code != 200:
            raise RuntimeError(
                f"LiteAvatar /generate failed ({r.status_code}): {r.text[:200]}"
            )

        data = r.json()
        return GenerateResponse(
            provider=self.name,
            job_id=data["job_id"],
            status=data.get("status", "queued"),
            cost_usd=0.0,
            raw=data,
        )

    def get_status(self, job_id: str) -> GenerateResponse:
        if not self._base_url:
            raise RuntimeError(
                "LiteAvatar worker URL not configured (LITE_AVATAR_URL)."
            )

        r = self._get(f"/status/{job_id}", timeout=self.STATUS_TIMEOUT)

        if r.status_code != 200:
            raise RuntimeError(
                f"LiteAvatar /status failed ({r.status_code}): {r.text[:200]}"
            )

        data = r.json()
        return GenerateResponse(
            provider=self.name,
            job_id=job_id,
            status=data.get("status", "processing"),
            video_url=data.get("video_url"),
            duration_seconds=data.get("duration_seconds"),
            error_message=data.get("error"),
            cost_usd=0.0,
            raw=data,
        )

    # ------------------------------------------------------------------ helpers

    def _generate_elevenlabs_audio(
        self, text: str, voice_id: Optional[str]
    ) -> Optional[str]:
        """Pre-generate ElevenLabs audio and return a URL the worker can fetch.

        NOT implemented in Đợt 2 — the ElevenLabs integration ships later.
        Returning None tells the worker to fall back to gTTS, which still
        produces functional Vietnamese output.
        """
        if voice_id:
            logger.warning(
                "ElevenLabs voice_id=%s provided but ElevenLabs integration "
                "not implemented yet; LiteAvatar worker will use gTTS fallback",
                voice_id,
            )
        return None

    def _get(self, path: str, timeout: float) -> httpx.Response:
        url = f"{self._base_url}{path}"
        if self._http is not None:
            return self._http.get(url, timeout=timeout)
        with httpx.Client() as client:
            return client.get(url, timeout=timeout)

    def _post(self, path: str, json: dict, timeout: float) -> httpx.Response:
        url = f"{self._base_url}{path}"
        if self._http is not None:
            return self._http.post(url, json=json, timeout=timeout)
        with httpx.Client() as client:
            return client.post(url, json=json, timeout=timeout)
