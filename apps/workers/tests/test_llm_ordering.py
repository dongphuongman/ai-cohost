"""Regression tests for llm.generate_suggestion ordering contract.

Context — incident 2026-04-12:
  A 17ms race in session 24 let AI suggestions leak into "top questions".
  The worker was publishing streaming chunks to Redis while the suggestion
  row was not yet committed to Postgres. The extension quick-paste loop
  meanwhile pushed the text back into FB chat, the scraper re-emitted it
  over WS as a comment.new, and is_likely_self_reply queried suggestions
  and found no row — so the AI reply was classified as a viewer comment.

The contract this test locks in:
  Every Redis publish from _do_generate that exposes AI text to the
  frontend (both ``suggestion.stream`` chunks and ``suggestion.complete``)
  MUST happen AFTER the suggestion row's INSERT has been committed.

If a future edit re-introduces streaming publishes inside
_call_llm_with_fallback, or moves the .complete publish above db.commit(),
this test fails.
"""
from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import llm.py without triggering real engine/redis construction.
#
# apps/workers/tasks/llm.py builds a SQLAlchemy engine and a redis client
# at import time. We stub both so the import is free of side effects and
# the test can inject its own tracker.
# ---------------------------------------------------------------------------

@pytest.fixture
def llm_module(monkeypatch):
    # Stub config before import so settings access doesn't try to read env.
    fake_settings = types.SimpleNamespace(
        database_url="postgresql+asyncpg://fake/fake",
        redis_url="redis://fake",
        gemini_api_key="fake",
        deepseek_api_key="",
    )
    fake_config = types.ModuleType("config")
    fake_config.settings = fake_settings
    monkeypatch.setitem(sys.modules, "config", fake_config)

    fake_celery_app = types.ModuleType("celery_app")
    fake_celery_app.app = MagicMock()
    # Make @app.task(...) a no-op decorator so task registration succeeds.
    fake_celery_app.app.task = lambda *a, **kw: (lambda fn: fn)
    monkeypatch.setitem(sys.modules, "celery_app", fake_celery_app)

    # Stub create_engine so import-time DB connect is a noop.
    import sqlalchemy
    monkeypatch.setattr(
        sqlalchemy, "create_engine", lambda *a, **kw: MagicMock(name="engine")
    )

    # Stub redis.from_url so import-time client build is a noop.
    import redis
    monkeypatch.setattr(
        redis, "from_url", lambda *a, **kw: MagicMock(name="redis_client")
    )

    # Now import.
    if "tasks.llm" in sys.modules:
        del sys.modules["tasks.llm"]
    from tasks import llm as llm_module
    return llm_module


def test_redis_publish_happens_after_db_commit(llm_module):
    """Lock in ordering: commit() must precede every publish() of AI text.

    We monkeypatch both ``_redis.publish`` and the Session.commit used by
    _do_generate, record the order of calls in a shared list, and assert
    that no publish happens before the commit.
    """
    call_log: list[str] = []

    # 1. Fake LLM — return known text and chunks WITHOUT touching network
    #    or Redis. Crucially, _call_llm_with_fallback must NOT publish
    #    chunks itself — the test would fail the ordering assertion if it
    #    did, since no commit has happened yet when the LLM call runs.
    def fake_llm(prompt, comment_id, session_id):
        call_log.append("llm_call")
        return (
            "Dạ chào chị/em! Test reply",
            "fake-model",
            "fake-provider",
            ["Dạ chào ", "chị/em! ", "Test reply"],
        )

    # 2. Fake Session used inside _do_generate (via `with Session(_engine)`).
    #    _do_generate runs several queries in sequence: comment fetch,
    #    session fetch, persona fetch, RAG query, and the final suggestion
    #    INSERT. Each expects a mappings().first() row with a different
    #    shape. We return one dict with all the keys any caller might
    #    read — extra keys are harmless since the code accesses by key.
    class FakeResult:
        def mappings(self):
            return self
        def first(self):
            return {
                # comment fetch
                "id": 42,
                "text": "Test viewer comment",
                "session_id": 24,
                # session fetch
                "persona_id": None,
                "active_product_ids": None,
                # RAG query
                "products": [],
                "faqs": [],
                # suggestion INSERT returning
                "created_at": "2026-04-12T10:16:58.583+00:00",
            }
        def scalar(self):
            return None
        def all(self):
            return []

    class FakeSession:
        def __init__(self, *a, **kw):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def execute(self, *a, **kw):
            return FakeResult()
        def commit(self):
            call_log.append("db_commit")

    def fake_publish(channel, payload):
        data = json.loads(payload)
        call_log.append(f"publish:{data.get('type')}")

    # 3. Patch inside the module namespace. _get_embedding calls out to
    #    Gemini, _build_prompt is pure but we short-circuit it anyway, and
    #    _redis.lrange reads conversation history — stub them all out.
    with patch.object(llm_module, "_call_llm_with_fallback", side_effect=fake_llm), \
         patch.object(llm_module, "Session", FakeSession), \
         patch.object(llm_module._redis, "publish", side_effect=fake_publish), \
         patch.object(llm_module._redis, "setex", MagicMock()), \
         patch.object(llm_module._redis, "lpush", MagicMock()), \
         patch.object(llm_module._redis, "ltrim", MagicMock()), \
         patch.object(llm_module._redis, "lrange", return_value=[]), \
         patch.object(llm_module, "_classify_intent", return_value=("question", 0.9)), \
         patch.object(llm_module, "_get_embedding", return_value=[0.0] * 384), \
         patch.object(llm_module, "_build_prompt", return_value="fake prompt"):
        llm_module._do_generate(comment_id=769, session_id=24, shop_id=1)

    # 4. Locate the LAST commit — _do_generate commits twice (once after
    #    updating comment.intent in step 2, once after inserting the
    #    suggestion in step 11). The race we care about is the second one:
    #    every publish must land after the suggestion row is committed,
    #    so we use the LAST commit index as the bar.
    commit_indices = [i for i, name in enumerate(call_log) if name == "db_commit"]
    if not commit_indices:
        pytest.fail(f"db.commit() never called. call_log={call_log}")
    last_commit_idx = commit_indices[-1]

    publish_events = [
        (i, name) for i, name in enumerate(call_log) if name.startswith("publish:")
    ]
    assert publish_events, f"No Redis publish recorded. call_log={call_log}"

    # 5. THE CONTRACT: every publish must come AFTER the suggestion commit.
    for idx, name in publish_events:
        assert idx > last_commit_idx, (
            "Ordering violation — a Redis publish happened before the final "
            "db.commit(). This re-opens the 2026-04-12 self-reply race. "
            f"Publish {name!r} "
            f"was at index {idx}, final commit was at index {last_commit_idx}. "
            f"Full call_log={call_log}"
        )

    # 6. Sanity: the publishes should include the stream chunks we buffered
    #    plus the final .complete, proving the chunks got flushed after
    #    commit rather than silently dropped.
    event_types = [name.split(":", 1)[1] for _, name in publish_events]
    assert event_types.count("suggestion.stream") == 3, (
        f"expected 3 buffered stream chunks to publish after commit, got "
        f"{event_types}"
    )
    assert event_types[-1] == "suggestion.complete", (
        f"suggestion.complete must be the final publish, got {event_types}"
    )
