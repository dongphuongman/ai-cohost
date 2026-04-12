"""Routes generation requests to the cheapest available provider.

Strategy:
  1. ``prefer_quality=True`` (Agency plan) → HeyGen if available.
  2. Default → LiteAvatar if available AND it supports the requested avatar.
  3. Fallback → HeyGen if available.
  4. Auto-fallback: if LiteAvatar.generate() raises, retry once on HeyGen.

Every routing decision is logged with a reason so debugging provider
selection in production is straightforward.
"""
from __future__ import annotations

import logging

from .base import DHProvider, GenerateRequest, GenerateResponse
from .heygen import HeyGenProvider
from .liteavatar import LiteAvatarProvider

logger = logging.getLogger(__name__)


class NoProviderAvailableError(RuntimeError):
    """Raised when no provider can serve a request."""


class DHProviderRouter:
    def __init__(
        self,
        liteavatar: LiteAvatarProvider | None = None,
        heygen: HeyGenProvider | None = None,
    ):
        self.liteavatar = liteavatar or LiteAvatarProvider()
        self.heygen = heygen or HeyGenProvider()

    # ------------------------------------------------------------------ select

    def select_provider(
        self,
        request: GenerateRequest,
        prefer_quality: bool = False,
    ) -> DHProvider:
        # 1. Premium quality preference → HeyGen
        if prefer_quality:
            if self.heygen.is_available():
                logger.info(
                    "Selected provider: heygen (reason: prefer_quality=True)"
                )
                return self.heygen
            logger.warning(
                "prefer_quality=True but HeyGen unavailable, "
                "falling through to default routing"
            )

        # 2. Try LiteAvatar
        if self.liteavatar.is_available():
            if self.liteavatar.supports_avatar(request.avatar_id):
                logger.info(
                    "Selected provider: liteavatar "
                    "(reason: available + supports avatar=%s)",
                    request.avatar_id,
                )
                return self.liteavatar
            logger.info(
                "Selected provider: heygen "
                "(reason: liteavatar does not support avatar=%s)",
                request.avatar_id,
            )
        else:
            logger.info(
                "Selected provider: heygen "
                "(reason: liteavatar unavailable — LITE_AVATAR_URL unset or "
                "health check failed)"
            )

        # 3. Fallback to HeyGen
        if self.heygen.is_available():
            return self.heygen

        raise NoProviderAvailableError(
            "Không có provider nào sẵn sàng. "
            "Kiểm tra LITE_AVATAR_URL hoặc HEYGEN_API_KEY."
        )

    # ------------------------------------------------------------------ run

    def generate(
        self,
        request: GenerateRequest,
        prefer_quality: bool | None = None,
    ) -> GenerateResponse:
        """Pick a provider and trigger generation.

        Auto-fallback: if the selected provider is LiteAvatar and ``generate()``
        raises, retry exactly once on HeyGen (if available). HeyGen failures
        are NOT retried — the worker task's retry policy handles those.
        """
        if prefer_quality is None:
            prefer_quality = request.prefer_quality

        provider = self.select_provider(request, prefer_quality=prefer_quality)
        try:
            return provider.generate(request)
        except Exception as exc:
            logger.error("Provider %s.generate() failed: %s", provider.name, exc)
            if provider.name == "liteavatar" and self.heygen.is_available():
                logger.info(
                    "Selected provider: heygen "
                    "(reason: auto-fallback after liteavatar failure)"
                )
                return self.heygen.generate(request)
            raise

    def get_status(self, provider_name: str, job_id: str) -> GenerateResponse:
        provider = self._provider_by_name(provider_name)
        return provider.get_status(job_id)

    def finalize(
        self,
        response: GenerateResponse,
        shop_id: int,
    ) -> GenerateResponse:
        provider = self._provider_by_name(response.provider)
        return provider.finalize(response, shop_id=shop_id)

    # ------------------------------------------------------------------ utils

    def _provider_by_name(self, name: str) -> DHProvider:
        if name == "liteavatar":
            return self.liteavatar
        if name == "heygen":
            return self.heygen
        raise ValueError(f"Unknown provider: {name}")
