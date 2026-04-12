"""Tests for the F7 digital human provider router and individual providers.

These tests fully mock HTTP — no real HeyGen or LiteAvatar calls are made.
They cover the four routing scenarios that matter for production correctness:

1. Default → LiteAvatar when available + supports avatar
2. Fallback → HeyGen when LiteAvatar is down
3. Fallback → HeyGen when LiteAvatar doesn't support the avatar
4. Auto-fallback → HeyGen when LiteAvatar.generate() raises
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from dh_providers import (
    DHProviderRouter,
    GenerateRequest,
    GenerateResponse,
    HeyGenProvider,
    LiteAvatarProvider,
)
from dh_providers.router import NoProviderAvailableError


# ---------- helpers ----------------------------------------------------------


def _request(avatar_id: str = "linh_female", prefer_quality: bool = False) -> GenerateRequest:
    return GenerateRequest(
        text="Xin chào",
        avatar_id=avatar_id,
        background="#FFFFFF",
        prefer_quality=prefer_quality,
        shop_id=1,
    )


def _make_router(
    *,
    lite_available: bool,
    heygen_available: bool,
    lite_supports: bool = True,
    lite_generate_raises: bool = False,
) -> tuple[DHProviderRouter, MagicMock, MagicMock]:
    lite = MagicMock(spec=LiteAvatarProvider)
    lite.name = "liteavatar"
    lite.is_available.return_value = lite_available
    lite.supports_avatar.return_value = lite_supports
    if lite_generate_raises:
        lite.generate.side_effect = RuntimeError("LiteAvatar worker exploded")
    else:
        lite.generate.return_value = GenerateResponse(
            provider="liteavatar", job_id="lite-job-1", status="processing"
        )

    heygen = MagicMock(spec=HeyGenProvider)
    heygen.name = "heygen"
    heygen.is_available.return_value = heygen_available
    heygen.supports_avatar.return_value = True
    heygen.generate.return_value = GenerateResponse(
        provider="heygen", job_id="hg-job-1", status="processing"
    )

    return DHProviderRouter(liteavatar=lite, heygen=heygen), lite, heygen


# ---------- routing decisions ------------------------------------------------


class TestRouterSelection:
    def test_default_picks_liteavatar_when_available(self):
        router, lite, heygen = _make_router(lite_available=True, heygen_available=True)
        provider = router.select_provider(_request())
        assert provider is lite
        heygen.generate.assert_not_called()

    def test_falls_back_to_heygen_when_liteavatar_down(self):
        router, lite, heygen = _make_router(lite_available=False, heygen_available=True)
        provider = router.select_provider(_request())
        assert provider is heygen

    def test_falls_back_to_heygen_for_unsupported_avatar(self):
        router, lite, heygen = _make_router(
            lite_available=True, heygen_available=True, lite_supports=False
        )
        provider = router.select_provider(_request(avatar_id="custom_user_avatar_xyz"))
        assert provider is heygen
        # And LiteAvatar generate should never be invoked
        lite.generate.assert_not_called()

    def test_prefer_quality_picks_heygen_even_if_liteavatar_up(self):
        router, lite, heygen = _make_router(lite_available=True, heygen_available=True)
        provider = router.select_provider(_request(), prefer_quality=True)
        assert provider is heygen

    def test_prefer_quality_falls_through_when_heygen_unavailable(self):
        router, lite, heygen = _make_router(lite_available=True, heygen_available=False)
        provider = router.select_provider(_request(), prefer_quality=True)
        assert provider is lite

    def test_raises_when_both_providers_down(self):
        router, _, _ = _make_router(lite_available=False, heygen_available=False)
        with pytest.raises(NoProviderAvailableError):
            router.select_provider(_request())


# ---------- generate() with auto-fallback ------------------------------------


class TestRouterGenerate:
    def test_generate_uses_selected_provider(self):
        router, lite, heygen = _make_router(lite_available=True, heygen_available=True)
        result = router.generate(_request())
        assert result.provider == "liteavatar"
        lite.generate.assert_called_once()
        heygen.generate.assert_not_called()

    def test_auto_fallback_to_heygen_after_liteavatar_failure(self):
        router, lite, heygen = _make_router(
            lite_available=True,
            heygen_available=True,
            lite_generate_raises=True,
        )
        result = router.generate(_request())
        assert result.provider == "heygen"
        lite.generate.assert_called_once()
        heygen.generate.assert_called_once()

    def test_no_fallback_when_heygen_down_after_liteavatar_failure(self):
        router, lite, heygen = _make_router(
            lite_available=True,
            heygen_available=False,
            lite_generate_raises=True,
        )
        with pytest.raises(RuntimeError, match="exploded"):
            router.generate(_request())

    def test_heygen_failure_does_not_auto_fallback(self):
        """HeyGen failures bubble up — Celery retry policy handles them."""
        router, lite, heygen = _make_router(
            lite_available=False, heygen_available=True
        )
        heygen.generate.side_effect = RuntimeError("HeyGen 500")
        with pytest.raises(RuntimeError, match="HeyGen 500"):
            router.generate(_request())

    def test_prefer_quality_pulled_from_request(self):
        router, lite, heygen = _make_router(lite_available=True, heygen_available=True)
        result = router.generate(_request(prefer_quality=True))
        assert result.provider == "heygen"


# ---------- LiteAvatarProvider stub behavior ---------------------------------


class TestLiteAvatarStub:
    def test_unavailable_when_url_unset(self):
        provider = LiteAvatarProvider(base_url="")
        assert provider.is_available() is False

    def test_unavailable_when_health_check_errors(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("connection refused")
        provider = LiteAvatarProvider(base_url="http://lite-avatar:8080", http_client=mock_client)
        assert provider.is_available() is False

    def test_available_when_health_returns_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        provider = LiteAvatarProvider(
            base_url="http://lite-avatar:8080", http_client=mock_client
        )
        assert provider.is_available() is True

    def test_supports_only_gallery_avatars(self):
        provider = LiteAvatarProvider()
        assert provider.supports_avatar("linh_female") is True
        assert provider.supports_avatar("custom_user_xyz") is False
        assert provider.supports_avatar("default_avatar") is False


# ---------- LiteAvatarProvider HTTP integration ------------------------------


class TestLiteAvatarHTTP:
    """HTTP integration tests for LiteAvatarProvider real implementation.

    The provider uses a sync ``httpx.Client`` (not AsyncClient) because
    Celery tasks call it directly. Tests inject a MagicMock through the
    ``http_client`` kwarg so no real network traffic is generated.
    """

    BASE_URL = "http://lite-avatar:8080"

    def _provider(self, client: MagicMock) -> LiteAvatarProvider:
        return LiteAvatarProvider(base_url=self.BASE_URL, http_client=client)

    def _ok_response(self, payload: dict, status_code: int = 200) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = payload
        resp.text = str(payload)
        return resp

    # --- is_available --------------------------------------------------------

    def test_health_check_success_returns_true(self):
        client = MagicMock()
        client.get.return_value = self._ok_response({"status": "ok"})
        assert self._provider(client).is_available() is True
        # Must hit /health endpoint
        called_url = client.get.call_args[0][0]
        assert called_url == f"{self.BASE_URL}/health"

    def test_health_check_404_returns_false(self):
        client = MagicMock()
        client.get.return_value = self._ok_response({}, status_code=404)
        assert self._provider(client).is_available() is False

    def test_health_check_connection_error_returns_false(self):
        client = MagicMock()
        client.get.side_effect = httpx.ConnectError("connection refused")
        assert self._provider(client).is_available() is False

    def test_health_check_timeout_returns_false(self):
        client = MagicMock()
        client.get.side_effect = httpx.ReadTimeout("read timeout")
        assert self._provider(client).is_available() is False

    # --- supports_avatar -----------------------------------------------------

    def test_supports_avatar_returns_true_for_known(self):
        provider = LiteAvatarProvider(base_url=self.BASE_URL)
        for avatar_id in ("linh_female", "nam_male", "huong_female",
                          "tuan_male", "mai_female"):
            assert provider.supports_avatar(avatar_id) is True

    def test_supports_avatar_returns_false_for_unknown(self):
        provider = LiteAvatarProvider(base_url=self.BASE_URL)
        assert provider.supports_avatar("custom_avatar_xyz") is False
        assert provider.supports_avatar("") is False

    # --- generate ------------------------------------------------------------

    def test_generate_success_returns_response_with_job_id(self):
        client = MagicMock()
        client.post.return_value = self._ok_response(
            {"job_id": "la-job-abc-123", "status": "queued"}
        )

        result = self._provider(client).generate(_request())

        assert isinstance(result, GenerateResponse)
        assert result.provider == "liteavatar"
        assert result.job_id == "la-job-abc-123"
        assert result.status == "queued"
        assert result.cost_usd == 0.0
        # Must hit /generate endpoint
        called_url = client.post.call_args[0][0]
        assert called_url == f"{self.BASE_URL}/generate"

    def test_generate_with_voice_id_logs_warning_and_passes_none(self, caplog):
        client = MagicMock()
        client.post.return_value = self._ok_response(
            {"job_id": "la-1", "status": "queued"}
        )

        req = GenerateRequest(
            text="xin chào",
            avatar_id="linh_female",
            voice_id="el_voice_42",
            shop_id=1,
        )

        import logging

        with caplog.at_level(logging.WARNING, logger="dh_providers.liteavatar"):
            self._provider(client).generate(req)

        # Warning must mention ElevenLabs not implemented
        assert any(
            "ElevenLabs" in rec.message and "el_voice_42" in rec.message
            for rec in caplog.records
        )

        # voice_audio_url in payload must be None (worker falls back to gTTS)
        payload = client.post.call_args[1]["json"]
        assert payload["voice_audio_url"] is None

    def test_generate_http_error_raises(self):
        client = MagicMock()
        err_resp = MagicMock()
        err_resp.status_code = 500
        err_resp.text = "Internal Server Error"
        client.post.return_value = err_resp

        with pytest.raises(RuntimeError, match="500"):
            self._provider(client).generate(_request())

    def test_generate_includes_all_request_fields_in_payload(self):
        client = MagicMock()
        client.post.return_value = self._ok_response(
            {"job_id": "la-1", "status": "queued"}
        )

        req = GenerateRequest(
            text="Xin chào thế giới",
            avatar_id="nam_male",
            background="#00FF00",
            language="vi",
            shop_id=1,
        )
        self._provider(client).generate(req)

        payload = client.post.call_args[1]["json"]
        assert payload["text"] == "Xin chào thế giới"
        assert payload["avatar_id"] == "nam_male"
        assert payload["background"] == "#00FF00"
        assert payload["language"] == "vi"
        assert payload["voice_audio_url"] is None

    # --- get_status ----------------------------------------------------------

    def test_get_status_ready_returns_video_url(self):
        client = MagicMock()
        client.get.return_value = self._ok_response(
            {
                "job_id": "la-1",
                "status": "ready",
                "video_url": "storage://lite-avatar/abc.mp4",
                "duration_seconds": 42,
                "error": None,
            }
        )

        result = self._provider(client).get_status("la-1")

        assert result.status == "ready"
        assert result.video_url == "storage://lite-avatar/abc.mp4"
        assert result.duration_seconds == 42
        assert result.error_message is None
        assert result.provider == "liteavatar"
        assert result.cost_usd == 0.0
        # Must hit /status/{job_id}
        called_url = client.get.call_args[0][0]
        assert called_url == f"{self.BASE_URL}/status/la-1"

    def test_get_status_processing_returns_no_url(self):
        client = MagicMock()
        client.get.return_value = self._ok_response(
            {
                "job_id": "la-1",
                "status": "processing",
                "video_url": None,
                "duration_seconds": None,
                "error": None,
            }
        )

        result = self._provider(client).get_status("la-1")

        assert result.status == "processing"
        assert result.video_url is None
        assert result.duration_seconds is None
        assert result.error_message is None

    def test_get_status_failed_returns_error_message(self):
        client = MagicMock()
        client.get.return_value = self._ok_response(
            {
                "job_id": "la-1",
                "status": "failed",
                "video_url": None,
                "duration_seconds": None,
                "error": "LiteAvatar inference crashed: OOM",
            }
        )

        result = self._provider(client).get_status("la-1")

        assert result.status == "failed"
        assert result.error_message == "LiteAvatar inference crashed: OOM"
        assert result.video_url is None

    def test_get_status_404_raises(self):
        client = MagicMock()
        err_resp = MagicMock()
        err_resp.status_code = 404
        err_resp.text = "Job not found"
        client.get.return_value = err_resp

        with pytest.raises(RuntimeError, match="404"):
            self._provider(client).get_status("unknown-job")


# ---------- HeyGenProvider behavior ------------------------------------------


class TestHeyGenProvider:
    def test_unavailable_without_api_key(self):
        provider = HeyGenProvider(api_key="")
        assert provider.is_available() is False

    def test_available_with_api_key(self):
        provider = HeyGenProvider(api_key="hg_test_key")
        assert provider.is_available() is True

    def test_supports_any_avatar(self):
        provider = HeyGenProvider(api_key="hg_test_key")
        assert provider.supports_avatar("anything") is True
        assert provider.supports_avatar("custom_avatar_99") is True

    def test_generate_calls_v2_endpoint(self):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"data": {"video_id": "hg-abc-123"}}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_post_resp

        provider = HeyGenProvider(api_key="hg_test_key", http_client=mock_client)
        response = provider.generate(_request(avatar_id="anna"))

        assert response.provider == "heygen"
        assert response.job_id == "hg-abc-123"
        assert response.status == "processing"
        # Verify the v2 endpoint and X-Api-Key header were used
        call_args = mock_client.post.call_args
        assert "/v2/video/generate" in call_args[0][0]
        assert call_args[1]["headers"]["X-Api-Key"] == "hg_test_key"

    def test_generate_uses_elevenlabs_voice_when_voice_id_present(self):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"data": {"video_id": "hg-1"}}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_post_resp

        provider = HeyGenProvider(api_key="key", http_client=mock_client)
        req = GenerateRequest(text="hello", avatar_id="anna", voice_id="el_voice_42")
        provider.generate(req)

        payload = mock_client.post.call_args[1]["json"]
        voice = payload["video_inputs"][0]["voice"]
        assert voice["type"] == "elevenlabs"
        assert voice["voice_id"] == "el_voice_42"

    def test_get_status_completed(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "status": "completed",
                "video_url": "https://heygen.cdn/abc.mp4",
                "duration": 12.5,
            }
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        provider = HeyGenProvider(api_key="k", http_client=mock_client)
        result = provider.get_status("hg-1")

        assert result.status == "ready"
        assert result.video_url == "https://heygen.cdn/abc.mp4"
        assert result.duration_seconds == 12

    def test_get_status_failed(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"status": "failed", "error": "rate limited"}
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        provider = HeyGenProvider(api_key="k", http_client=mock_client)
        result = provider.get_status("hg-1")

        assert result.status == "failed"
        assert "rate limited" in result.error_message

    def test_get_status_still_processing(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"status": "processing"}}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        provider = HeyGenProvider(api_key="k", http_client=mock_client)
        result = provider.get_status("hg-1")

        assert result.status == "processing"
        assert result.video_url is None

    def test_finalize_downloads_watermarks_and_stores(self):
        # Mock download
        mock_dl_resp = MagicMock()
        mock_dl_resp.content = b"raw_video_bytes"
        mock_client = MagicMock()
        mock_client.get.return_value = mock_dl_resp

        provider = HeyGenProvider(api_key="k", http_client=mock_client)
        ready = GenerateResponse(
            provider="heygen",
            job_id="hg-1",
            status="ready",
            video_url="https://heygen.cdn/abc.mp4",
            duration_seconds=60,
        )

        # Patch watermark + storage helpers (avoid invoking ffmpeg in tests)
        with patch("dh_providers.heygen.add_watermark", return_value=b"wm_video_bytes") as wm, \
             patch(
                 "dh_providers.heygen.save_video_artifact",
                 return_value="storage://videos/1/abc.mp4",
             ) as save:
            finalized = provider.finalize(ready, shop_id=1)

        wm.assert_called_once_with(b"raw_video_bytes")
        save.assert_called_once_with(b"wm_video_bytes", shop_id=1)
        assert finalized.video_url == "storage://videos/1/abc.mp4"
        assert finalized.file_size_bytes == len(b"wm_video_bytes")
        # 60s @ $0.40/min = $0.40
        assert finalized.cost_usd == pytest.approx(0.40)

    def test_finalize_noop_when_not_ready(self):
        provider = HeyGenProvider(api_key="k")
        not_ready = GenerateResponse(provider="heygen", job_id="hg", status="processing")
        result = provider.finalize(not_ready, shop_id=1)
        assert result is not_ready  # untouched


# ---------- save_video_artifact placeholder ----------------------------------


class TestSaveVideoArtifact:
    def test_returns_storage_placeholder_url(self):
        from dh_providers.base import save_video_artifact

        url = save_video_artifact(b"some bytes", shop_id=42)
        assert url.startswith("storage://videos/42/")
        assert url.endswith(".mp4")

    def test_unique_per_call(self):
        from dh_providers.base import save_video_artifact

        u1 = save_video_artifact(b"x", shop_id=1)
        u2 = save_video_artifact(b"x", shop_id=1)
        assert u1 != u2
