"""LiteAvatar provider — self-hosted, ~$0/min.

Stub implementation (Đợt 1). The actual lite-avatar-worker FastAPI service
ships in Đợt 2. Until then ``is_available()`` returns False (because
``LITE_AVATAR_URL`` is unset by default), so the router transparently falls
back to HeyGen — production behavior is unchanged.

When the worker service ships, fill in the HTTP calls below; the provider
interface is already wired into the router and Celery task.
"""
from __future__ import annotations

import logging

import httpx

from config import settings

from .base import DHProvider, GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)


class LiteAvatarProvider(DHProvider):
    name = "liteavatar"
    supports_custom_avatar = False  # Only the pre-loaded gallery is supported
    cost_per_minute_usd = 0.0  # Self-hosted

    # Avatars pre-loaded into the worker container in Đợt 2.
    AVAILABLE_AVATARS = frozenset(
        {
            "linh_female",
            "nam_male",
            "huong_female",
            "tuan_male",
            "mai_female",
        }
    )

    def __init__(self, base_url: str | None = None, http_client: httpx.Client | None = None):
        self._base_url = base_url if base_url is not None else settings.lite_avatar_url
        self._http = http_client

    # ------------------------------------------------------------------ checks

    def is_available(self) -> bool:
        """Health-check the LiteAvatar worker.

        Returns False immediately if ``LITE_AVATAR_URL`` is unset, which is
        the default in Đợt 1 — guaranteeing the router falls back to HeyGen.
        Never caches: a transient outage should not pin us to HeyGen forever.
        """
        if not self._base_url:
            return False
        try:
            client = self._http or httpx.Client()
            r = client.get(f"{self._base_url}/health", timeout=5)
            return r.status_code == 200
        except Exception as exc:
            logger.warning("LiteAvatar health check failed: %s", exc)
            return False

    def supports_avatar(self, avatar_id: str) -> bool:
        return avatar_id in self.AVAILABLE_AVATARS

    # ------------------------------------------------------------------ API
    # The methods below are placeholders for Đợt 2. They are guarded by
    # ``is_available()`` returning False in Đợt 1, so the router will never
    # actually call them in production. Tests cover both branches.

    def generate(self, request: GenerateRequest) -> GenerateResponse:  # pragma: no cover
        if not self._base_url:
            raise RuntimeError(
                "LiteAvatar worker URL not configured (LITE_AVATAR_URL). "
                "Đợt 2 not yet deployed — router should have selected HeyGen."
            )
        # Đợt 2: POST {base}/generate with text+avatar_id+voice_audio_url, return job_id
        raise NotImplementedError("LiteAvatar generate() lands in Đợt 2")

    def get_status(self, job_id: str) -> GenerateResponse:  # pragma: no cover
        if not self._base_url:
            raise RuntimeError(
                "LiteAvatar worker URL not configured (LITE_AVATAR_URL)."
            )
        # Đợt 2: GET {base}/status/{job_id}
        raise NotImplementedError("LiteAvatar get_status() lands in Đợt 2")
