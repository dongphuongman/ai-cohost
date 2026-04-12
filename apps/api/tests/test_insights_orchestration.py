"""Orchestration tests for ``generate_session_insights``.

These complement the pure-unit tests in ``test_session_insights.py`` by
exercising the retry/cache/fallback loop end-to-end with mocked LLM and
Redis. They avoid a live DB by stubbing ``_gather_context``.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.analytics import SessionInsights
from app.services import session_insights as si


_FAKE_CONTEXT: dict = {
    # Anything — we stub PROMPT_TEMPLATE.format to ignore placeholders.
    "placeholder": "x",
}


@pytest.fixture
def fake_redis():
    """AsyncMock Redis client — returns no cache, accepts setex."""
    r = MagicMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    return r


@pytest.fixture(autouse=True)
def stub_gather_and_template():
    """Keep the orchestration tests DB-free."""
    with patch.object(
        si, "_gather_context", new=AsyncMock(return_value=_FAKE_CONTEXT)
    ), patch.object(si, "PROMPT_TEMPLATE", MagicMock(format=lambda **_: "PROMPT")):
        yield


def _llm_response(payload: dict) -> MagicMock:
    """Build a fake Gemini response whose ``.text`` is JSON."""
    resp = MagicMock()
    resp.text = json.dumps(payload)
    return resp


def _fake_gemini_client(responses: list[MagicMock]):
    """Build a client whose generate_content yields ``responses`` in order."""
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.generate_content = AsyncMock(side_effect=responses)
    return client


# ──────────────────────────────────────────────────────────────────────────
# #1: cache hit short-circuits before touching the LLM
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insights_cache_hit_short_circuits(fake_redis):
    cached_payload = {
        "positives": [],
        "improvements": [],
        "suggestions": [],
        "generated_at": "2026-04-12T00:00:00+00:00",
        "warning": None,
    }
    fake_redis.get = AsyncMock(return_value=json.dumps(cached_payload))

    with patch.object(si, "_get_redis", return_value=fake_redis), patch.object(
        si, "genai"
    ) as mock_genai:
        result = await si.generate_session_insights(
            db=MagicMock(), shop_id=1, session_id=42
        )

    assert isinstance(result, SessionInsights)
    assert result.cached is True
    mock_genai.Client.assert_not_called()
    fake_redis.setex.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────
# #2: Gemini init failure returns fallback insights, does not raise
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insights_gemini_init_failure_returns_fallback(fake_redis):
    fake_genai = MagicMock()
    fake_genai.Client.side_effect = RuntimeError("no api key")

    with patch.object(si, "_get_redis", return_value=fake_redis), patch.object(
        si, "genai", fake_genai
    ):
        result = await si.generate_session_insights(
            db=MagicMock(), shop_id=1, session_id=42
        )

    assert isinstance(result, SessionInsights)
    assert result.positives == []
    assert len(result.improvements) == 1
    assert "LLM provider" in result.improvements[0].detail
    # Fallback should NOT poison the cache.
    fake_redis.setex.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────
# #3: retry loop fires when first attempt is all-generic
# ──────────────────────────────────────────────────────────────────────────


_GENERIC_ITEM = {
    "title": "Tăng tương tác",
    "detail": "Nên tăng cường tương tác và phản hồi nhanh để hỗ trợ tốt hơn",
    "action": "Tập trung vào khách hàng",
}

_SPECIFIC_POSITIVE = {
    "title": "8 khách hỏi về LUVIBA LO46 phút 14:23",
    "detail": "8 comments cụ thể về combo 2 cái giảm 15%, session 1h22m",
    "action": None,
}
_SPECIFIC_IMPROVEMENT = {
    "title": "12 khách rời phiên phút 47 sản phẩm Fx799",
    "detail": "Drop 32→8 comments khi chuyển Fx799, intent='pricing' 12 lần",
    "action": "Vào Sản phẩm > Fx799 > cập nhật giá niêm yết",
}


@pytest.mark.asyncio
async def test_insights_retry_loop_on_generic_validation_failure(fake_redis):
    """First attempt returns generic-only → retry loop triggers → second
    attempt with specifics is accepted."""

    bad = _llm_response({
        "positives": [_GENERIC_ITEM, _GENERIC_ITEM, _GENERIC_ITEM],
        "improvements": [_GENERIC_ITEM],
        "suggestions": [_GENERIC_ITEM],
    })
    good = _llm_response({
        "positives": [_SPECIFIC_POSITIVE],
        "improvements": [_SPECIFIC_IMPROVEMENT],
        "suggestions": [_SPECIFIC_IMPROVEMENT],
    })

    fake_client = _fake_gemini_client([bad, good])
    fake_genai = MagicMock()
    fake_genai.Client.return_value = fake_client

    with patch.object(si, "_get_redis", return_value=fake_redis), patch.object(
        si, "genai", fake_genai
    ):
        result = await si.generate_session_insights(
            db=MagicMock(), shop_id=1, session_id=42
        )

    assert fake_client.aio.models.generate_content.await_count >= 2
    assert isinstance(result, SessionInsights)
    # Retry should have landed on the specific content.
    assert any("LUVIBA" in p.title for p in result.positives)
    fake_redis.setex.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────
# #4: final-attempt hallucinations are filtered (not crashed on)
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insights_hallucination_final_filter(fake_redis):
    """All attempts return a mix of clean + hallucinated items. After the
    retry budget runs out, the hallucinated items are dropped and a warning
    explains how many cards were hidden."""

    # Pull a real forbidden phrase so _validate_against_hallucination fires.
    forbidden = next(iter(si.FORBIDDEN_PHRASES))
    hallucinated = {
        "title": f"Thêm {forbidden}",
        "detail": f"Gợi ý {forbidden} cho user",
        "action": f"Vào {forbidden}",
    }

    payload = {
        "positives": [_SPECIFIC_POSITIVE],
        "improvements": [hallucinated, _SPECIFIC_IMPROVEMENT],
        "suggestions": [hallucinated],
    }
    # _MAX_RETRIES + 1 identical responses so every attempt hallucinates.
    responses = [
        _llm_response(payload) for _ in range(si._MAX_RETRIES + 1)
    ]

    fake_client = _fake_gemini_client(responses)
    fake_genai = MagicMock()
    fake_genai.Client.return_value = fake_client

    with patch.object(si, "_get_redis", return_value=fake_redis), patch.object(
        si, "genai", fake_genai
    ):
        result = await si.generate_session_insights(
            db=MagicMock(), shop_id=1, session_id=42
        )

    assert isinstance(result, SessionInsights)
    # Hallucinated items must be filtered out — only the clean one survives.
    assert all(forbidden not in it.title for it in result.improvements)
    assert all(forbidden not in it.title for it in result.suggestions)
    assert result.warning is not None
    assert "không có thật" in result.warning
    # Burned the full retry budget.
    assert (
        fake_client.aio.models.generate_content.await_count
        == si._MAX_RETRIES + 1
    )
