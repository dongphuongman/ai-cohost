"""Regression tests for the ``is_from_host`` host-vs-viewer comment split.

Background
----------
On 2026-04-12, every WebSocket ``comment.new`` event silently failed in dev
because the ``comments.is_from_host`` column referenced by the ORM model and
the WS handler had never been applied to the database. The extension's
optimistic UI counter happily showed "36 comments read", but the backend
INSERT raised ``UndefinedColumnError``, the transaction rolled back, and zero
Celery tasks were enqueued. Result: 0 AI suggestions despite a fully
operational worker. Root cause was missing ``alembic upgrade head`` after
pulling commit 086a047 (Nhóm A).

These tests pin the two halves of the regression mode so the same shape of
bug fails fast in CI:

1. **Logic** — ``_looks_like_host_reply`` must NOT classify viewer comments
   from the simulator as host-bot replies. If a future contributor expands
   ``_HOST_REPLY_PREFIXES`` too aggressively, real questions like "Shop ơi
   giá bao nhiêu vậy ạ?" would silently get dropped from the AI pipeline
   with no error log.

2. **Drift** — every column mapped on the ``Comment`` ORM model must appear
   in at least one alembic migration file. Catches "model field added but
   no migration written", which is the underlying pattern that caused this
   incident. Note: this does NOT replace running ``alembic upgrade head``
   on the dev DB — that's handled by the startup migration check in
   ``app.main``. This only catches the *file-level* drift between code and
   migration scripts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.session import Comment
from app.ws.handler import (
    _HOST_REPLY_PREFIXES,
    _SELF_REPLY_MIN_LEN,
    _SELF_REPLY_PREFIX_LEN,
    _is_self_reply_match,
    _looks_like_host_reply,
    is_likely_self_reply,
)


# ---------------------------------------------------------------------------
# 1. Logic regression — host-reply heuristic must not eat viewer comments
# ---------------------------------------------------------------------------


# Verbatim copy of the comment phrases the live-stream-simulator.html sends.
# If anyone edits the simulator, this list should be updated to match. The
# point is to assert that the heuristic stays narrow enough to never
# misclassify a real viewer question.
SIMULATOR_VIEWER_COMMENTS = [
    # questions
    "Shop ơi giá bao nhiêu vậy ạ?",
    "Có ship COD không shop?",
    "Da dầu mụn dùng được không ạ?",
    "Bao lâu thì thoa lại 1 lần shop?",
    "Có mùi thơm không shop ơi?",
    "Dùng cho da nhạy cảm được không?",
    "Hạn sử dụng còn bao lâu ạ?",
    "Có giấy chứng nhận FDA không shop?",
    "Đang có khuyến mãi gì không ạ?",
    "Ship về Đà Nẵng mấy ngày shop?",
    "Sản phẩm có chứa cồn không ạ?",
    "Combo 2 cái giảm thêm không shop?",
    "Dùng trước hay sau kem chống nắng?",
    "Có tester gửi kèm không shop?",
    "Thanh toán qua Momo được không?",
    "Đổi trả trong bao nhiêu ngày shop?",
    "Sản phẩm origin ở đâu vậy?",
    "Có hướng dẫn sử dụng không shop?",
    "Bên em có bán sỉ không ạ?",
    "Mình đặt 3 cái free ship luôn không?",
    # greetings
    "Chào shop ơi! 🎉",
    "Hi shop, mình mới vào nè",
    "Xin chào mọi người!",
    "Shop ơi live rồi à, vào ngay 😍",
    "Chào cả nhà!",
    "Hello shop! 👋",
    "Alo alo, có ai không?",
    "Mới vào, có gì hot không shop?",
    # praise
    "Xinh quá shop ơi! 😍",
    "Sản phẩm đẹp thật!",
    "Thích quá luôn! ❤️",
    "Mình dùng rồi, tốt lắm ạ!",
    "Đỉnh quá shop ơi 🔥",
    "Xem live shop vui quá 😊",
    "Ủng hộ shop nè ❤️",
    "Review hay quá!",
    # complaints
    "Mình mua lần trước bị dị ứng luôn!",
    "Ship chậm quá, đợi 1 tuần chưa nhận",
    "Hàng giao không giống hình!",
    "Tại sao giá hôm nay khác hôm qua?",
]


@pytest.mark.parametrize("text", SIMULATOR_VIEWER_COMMENTS)
def test_simulator_viewer_comments_are_not_classified_as_host_replies(text: str):
    """Real viewer comments must NEVER trigger the host-reply heuristic.

    If this test fails, the AI pipeline will silently drop the matching
    comment shape and the user will see "0 gợi ý" without any error log
    pointing at the cause. That's the exact failure mode of the original
    incident.
    """
    assert _looks_like_host_reply(text) is False, (
        f"Viewer comment was incorrectly classified as a host bot reply: {text!r}. "
        f"Check apps/api/app/ws/handler.py::_HOST_REPLY_PREFIXES — a prefix was "
        f"likely added that's too broad."
    )


@pytest.mark.parametrize(
    "text",
    [
        "Dạ shop sẽ ship trong 2 ngày ạ",
        "Dạ vâng, sản phẩm còn hàng nha",
        "Cảm ơn bạn đã ủng hộ shop ❤️",
        "Cảm ơn anh chị đã quan tâm",
        "dạ shop xin báo giá",  # case-insensitive
        "  Dạ shop có ship COD nha  ",  # leading whitespace
    ],
)
def test_known_host_reply_prefixes_are_classified_as_host(text: str):
    """The narrow allowlist of bot-reply prefixes must still be detected.

    This is the *positive* half of the heuristic — without it, A4's host
    filtering does nothing.
    """
    assert _looks_like_host_reply(text) is True, (
        f"Known bot reply was not detected: {text!r}. Check that "
        f"_HOST_REPLY_PREFIXES still covers the auto-reply phrasing the "
        f"worker emits."
    )


@pytest.mark.parametrize("text", ["", None])
def test_empty_text_is_not_a_host_reply(text):
    """Defensive: never crash on empty/None text from a malformed payload."""
    assert _looks_like_host_reply(text) is False


def test_host_reply_prefixes_are_lowercase_and_stripped():
    """Internal invariant: prefixes are matched against ``text.strip().lower()``,
    so the source list itself must be lowercase. Otherwise the heuristic
    silently matches nothing."""
    for prefix in _HOST_REPLY_PREFIXES:
        assert prefix == prefix.lower().strip(), (
            f"_HOST_REPLY_PREFIXES entry is not lowercase/stripped: {prefix!r}. "
            f"Matching uses head.strip().lower(), so a non-lowercase entry is "
            f"dead code."
        )


# ---------------------------------------------------------------------------
# 2. Drift regression — every Comment ORM column must exist in a migration
# ---------------------------------------------------------------------------


_VERSIONS_DIR = Path(__file__).parent.parent / "alembic" / "versions"


def _all_migration_text() -> str:
    """Concatenated source of every alembic migration script.

    Used as a coarse "does this column name appear anywhere in the migration
    history?" check. Cheap and good enough to catch the failure mode where
    someone added a ``Mapped[]`` field on the model but forgot the
    corresponding ``ADD COLUMN`` statement.
    """
    parts: list[str] = []
    for path in sorted(_VERSIONS_DIR.glob("*.py")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_comment_model_columns_have_corresponding_migration():
    """Every column mapped on Comment must appear in some migration file.

    This catches the file-level drift that caused the 2026-04-12 incident:
    the ``is_from_host`` field existed on the ORM model and was used in raw
    SQL queries, but no migration created the column on the database. CI
    test runs *do* apply ``alembic upgrade head`` to a fresh test DB, so a
    truly missing migration would also fail downstream tests — but this
    test fails fast with a precise error message instead of a confusing
    UndefinedColumnError 50 frames deep.
    """
    migration_source = _all_migration_text()
    mapped_columns = {col.name for col in Comment.__table__.columns}

    missing = [c for c in sorted(mapped_columns) if c not in migration_source]
    assert not missing, (
        f"These Comment columns are mapped on the ORM model but do not "
        f"appear in any alembic migration file: {missing}. Either add a "
        f"migration that creates them, or remove the ORM mapping. "
        f"(This test guards against the 2026-04-12 is_from_host incident.)"
    )


# ---------------------------------------------------------------------------
# 3. Host-loop self-reply detection
# ---------------------------------------------------------------------------
#
# When the host actually clicks Send on a Quick-Paste suggestion, the live
# chat panel shows the AI's text back as a fresh comment. The Chrome
# extension scrapes it on the next polling tick and pushes it to the WS as
# `comment.new`, which (without intervention) triggers a new suggestion
# task and pollutes Top Questions on the dashboard. We caught this exact
# leak in session 17 during the 2026-04-12 UAT.
#
# These tests pin both halves of the fix:
#
#   * `_is_self_reply_match` — pure logic that decides whether a comment
#     text matches a list of recently-sent suggestion texts. No DB.
#
#   * `is_likely_self_reply` — thin DB wrapper. Tested with a fake async
#     session so we can verify the fast-path short-circuit, the cutoff
#     query, and the empty-recent-list case without standing up Postgres.


# Realistic suggestion text that the AI persona generates today. Pinned
# verbatim from session 17 of the 2026-04-12 UAT — when this fails because
# the persona changes, the test should be UPDATED, not the matcher loosened.
_SAMPLE_SUGGESTIONS = [
    "Dạ đúng rồi chị yêu ơi! 🥰 Giá KEM MẶT VICTORY NGỌC TRAI TRẮNG DA hôm nay vẫn là 60,000 VND đó ạ! Mình yên tâm mua sắm nha! ❤️",
    "Chào chị yêu ơi! 🥰 Hôm nay bên em có deal KEM MẶT VICTORY NGỌC TRAI TRẮNG DA chỉ 60K thôi nha! ❤️",
    "Dạ em xin lỗi vì em không thể hỗ trợ mình về vấn đề này ạ. Để em check lại nha!",
]


class TestSelfReplyMatchPure:
    """Pure-logic tests for _is_self_reply_match. No DB, no I/O."""

    def test_exact_match_is_detected(self):
        """The exact same text the AI sent must match."""
        text = _SAMPLE_SUGGESTIONS[0]
        assert _is_self_reply_match(text, _SAMPLE_SUGGESTIONS) is True

    def test_case_insensitive_match(self):
        """The scraper might lowercase or uppercase. Match anyway."""
        text = _SAMPLE_SUGGESTIONS[0].upper()
        assert _is_self_reply_match(text, _SAMPLE_SUGGESTIONS) is True

    def test_whitespace_normalized(self):
        """Leading/trailing whitespace from the scraper must not break match."""
        text = "   " + _SAMPLE_SUGGESTIONS[0] + "   "
        assert _is_self_reply_match(text, _SAMPLE_SUGGESTIONS) is True

    def test_truncated_comment_matches_full_suggestion(self):
        """FB truncates long messages mid-sentence; match the prefix."""
        # First 50 chars of a 100-char suggestion
        truncated = _SAMPLE_SUGGESTIONS[0][:50]
        assert _is_self_reply_match(truncated, _SAMPLE_SUGGESTIONS) is True

    def test_extended_comment_matches_short_suggestion(self):
        """Scraper appends a timestamp/author suffix; match the prefix the
        other direction."""
        sug = "Dạ shop báo giá 350,000 VND ạ, freeship nha!"
        comment = sug + " 12:34 PM"
        assert _is_self_reply_match(comment, [sug]) is True

    def test_unrelated_viewer_comment_does_not_match(self):
        """A real viewer question must NOT match any suggestion."""
        text = "Shop ơi giá bao nhiêu vậy ạ?"
        assert _is_self_reply_match(text, _SAMPLE_SUGGESTIONS) is False

    def test_short_comment_skipped(self):
        """Comments under min length never match — avoids false positives
        on '?', 'ok', 'có ạ'."""
        # Even with a suggestion that starts with 'ok', a 2-char 'ok'
        # comment must not be classified as a self-reply.
        assert _is_self_reply_match("ok", ["ok shop, để em check"]) is False
        assert _is_self_reply_match("?", _SAMPLE_SUGGESTIONS) is False
        assert _is_self_reply_match("", _SAMPLE_SUGGESTIONS) is False
        assert _is_self_reply_match("   ", _SAMPLE_SUGGESTIONS) is False

    def test_empty_suggestion_list(self):
        """No recent suggestions → never a self-reply."""
        assert _is_self_reply_match("Dạ shop ơi", []) is False

    def test_short_suggestion_in_list_is_skipped(self):
        """A degenerate 1-char suggestion must not poison the matcher."""
        assert _is_self_reply_match("ok shop", ["a", "b"]) is False

    def test_partial_overlap_below_prefix_threshold_does_not_match(self):
        """Two messages sharing only the first 10 chars must NOT match —
        the 30-char prefix gate guards against generic openings like
        'Dạ shop ơi'."""
        sug = "Dạ shop ơi giá KEM CHỐNG NẮNG là 350K ạ"
        # Both start with 'dạ shop ơi giá ' (15 chars) but the suggestion is
        # about a different product than the comment.
        comment = "Dạ shop ơi giá SỮA RỬA MẶT là bao nhiêu vậy ạ?"
        assert _is_self_reply_match(comment, [sug]) is False

    def test_constants_are_sane(self):
        """Internal invariants the matcher relies on."""
        assert _SELF_REPLY_MIN_LEN >= 1
        assert _SELF_REPLY_PREFIX_LEN >= _SELF_REPLY_MIN_LEN
        assert _SELF_REPLY_PREFIX_LEN <= 100  # not absurdly long


# ---- DB wrapper tests ------------------------------------------------------
#
# We don't stand up Postgres for these. Instead we patch the fetch helper so
# is_likely_self_reply runs against a controlled list of "recent suggestion
# texts". This catches the wiring around the pure matcher: the short-text
# fast-path, the empty-recent-list short-circuit, and the propagation of
# matches from the matcher into the boolean return.

import app.ws.handler as handler_mod  # noqa: E402  (intentional late import)


class _FakeDB:
    """Sentinel object handed to is_likely_self_reply.

    The real function only forwards it to the patched fetch helper, so
    nothing here is exercised — but having a distinct object lets the test
    assert that the right session was passed through unchanged.
    """


@pytest.fixture
def patched_fetch(monkeypatch):
    """Replace _fetch_recent_suggestion_texts with a controllable fake.

    Yields a setter the test can use to install per-call return values.
    """
    state = {"texts": [], "calls": []}

    async def fake_fetch(db, session_id, *, window_minutes=5):
        state["calls"].append((db, session_id, window_minutes))
        return state["texts"]

    monkeypatch.setattr(
        handler_mod, "_fetch_recent_suggestion_texts", fake_fetch
    )
    return state


@pytest.mark.asyncio
async def test_is_likely_self_reply_returns_true_on_match(patched_fetch):
    patched_fetch["texts"] = list(_SAMPLE_SUGGESTIONS)
    db = _FakeDB()
    result = await is_likely_self_reply(db, 17, _SAMPLE_SUGGESTIONS[0])
    assert result is True
    # Sanity: the wrapper actually called the fetch with our session_id
    assert patched_fetch["calls"] == [(db, 17, 5)]


@pytest.mark.asyncio
async def test_is_likely_self_reply_returns_false_when_no_match(patched_fetch):
    patched_fetch["texts"] = list(_SAMPLE_SUGGESTIONS)
    result = await is_likely_self_reply(
        _FakeDB(), 17, "Shop ơi giá bao nhiêu vậy ạ?"
    )
    assert result is False


@pytest.mark.asyncio
async def test_is_likely_self_reply_skips_db_for_short_text(patched_fetch):
    """Short text must not even hit the DB. Verified by checking call count."""
    result = await is_likely_self_reply(_FakeDB(), 17, "ok")
    assert result is False
    assert patched_fetch["calls"] == [], (
        "Short text should short-circuit BEFORE the DB query — saves a "
        "roundtrip on common one-word viewer replies."
    )


@pytest.mark.asyncio
async def test_is_likely_self_reply_skips_db_for_empty_text(patched_fetch):
    assert await is_likely_self_reply(_FakeDB(), 17, "") is False
    assert await is_likely_self_reply(_FakeDB(), 17, "   ") is False
    assert await is_likely_self_reply(_FakeDB(), 17, None) is False
    assert patched_fetch["calls"] == []


@pytest.mark.asyncio
async def test_is_likely_self_reply_returns_false_when_no_recent_suggestions(
    patched_fetch,
):
    """Brand new session with zero sent suggestions yet — never a self-reply."""
    patched_fetch["texts"] = []  # session has no sent suggestions
    result = await is_likely_self_reply(
        _FakeDB(), 17, "Dạ shop báo giá 350K ạ, freeship cho mình nha!"
    )
    assert result is False
    # Did consult the DB though — that's the difference vs the short-text path
    assert len(patched_fetch["calls"]) == 1


@pytest.mark.asyncio
async def test_is_likely_self_reply_truncated_facebook_render(patched_fetch):
    """End-to-end shape of the actual UAT bug: AI sends a long reply, FB
    renders it truncated, the scraper sends the truncated form back as a
    new comment. Must be tagged as host."""
    full = (
        "Dạ đúng rồi chị yêu ơi! 🥰 Giá KEM MẶT VICTORY NGỌC TRAI TRẮNG DA "
        "hôm nay vẫn là 60,000 VND đó ạ!"
    )
    truncated = full[:60]  # FB truncated mid-sentence
    patched_fetch["texts"] = [full]
    result = await is_likely_self_reply(_FakeDB(), 17, truncated)
    assert result is True


# ---------------------------------------------------------------------------
# 4. Status-agnostic detection — regression for the 2026-04-12 polluted-DB bug
# ---------------------------------------------------------------------------
#
# The first cut of the host-loop fix gated detection on
# ``suggestions.status = 'sent'``. Backfill against the dev DB caught only
# 76 of ~137 historical leaks because:
#
#   * `pasted_not_sent` is set when the extension's Quick Paste action drops
#     text into the FB chat input. The extension has no signal for the
#     subsequent manual Send click, so this status is really
#     "pasted-and-maybe-sent". 50 such leaks existed.
#
#   * `suggested` is the unmodified initial state. Sometimes the comment
#     re-scrape WS event arrives before the extension PATCHes the status,
#     leaving real sends with `suggested`. 11 such leaks existed.
#
# These tests pin the new contract: the matcher cares about TEXT, not
# STATUS. The fetch helper hands every recent-window suggestion in the
# session to the matcher, regardless of state. Concrete regression target
# is session 15 / suggestion #267 / comment #460 from the 2026-04-12 bug.


class TestStatusAgnosticDetection:
    """The matcher must not gate on suggestion.status.

    These are pure-logic tests on _is_self_reply_match: the matcher takes
    plain text strings and has no concept of status. The point of the
    tests is to assert "given a suggestion text that the DB stored under
    status X, will the matcher catch the re-scrape?" — the answer must
    be yes for every status, because status is an extension UI state
    and the live FB chat panel doesn't care about it.
    """

    def test_self_reply_detected_when_suggestion_status_is_pasted_not_sent(self):
        """Quick Paste fills the FB chat input. The extension marks the
        suggestion `pasted_not_sent` because it can't observe the host's
        manual click on FB's own Send button. But the host DOES click —
        the text appears in chat and gets re-scraped on the next polling
        tick. Detection must fire.

        Pinned from session 15 / suggestion #267 / comment #460 in the
        2026-04-12 dataset.
        """
        suggestion_text = (
            "Dạ đúng rồi chị yêu ơi!💖 KEM MẶT VICTORY NGỌC TRAI TRẮNG DA "
            "giúp da sáng mịn, đều màu hơn đó ạ!"
        )
        # status='pasted_not_sent' is irrelevant to the matcher — it
        # only sees the text.
        assert _is_self_reply_match(suggestion_text, [suggestion_text]) is True

    def test_self_reply_detected_when_suggestion_status_is_suggested(self):
        """Race condition: the comment re-scrape WS event arrives before
        the extension PATCHes the suggestion status. Real sends can sit
        at `suggested` for a few hundred ms. Detection must fire on the
        text alone."""
        suggestion_text = (
            "Dạ chị yêu ơi!💖 Bên em luôn đặt chất lượng sản phẩm và sự "
            "hài lòng của khách hàng lên hàng đầu nha!"
        )
        assert _is_self_reply_match(suggestion_text, [suggestion_text]) is True

    def test_self_reply_detected_when_suggestion_status_is_dismissed(self):
        """Future-proofing: even if a new status like `dismissed` is added
        to the suggestion lifecycle, the matcher must keep working on
        text alone. Status is an extension UI signal, not a delivery
        signal — adding a new state should never silently regress
        detection."""
        suggestion_text = (
            "Dạ chào chị yêu! 🥰 Hôm nay nhà em có deal 32 ảnh 4x6 ép "
            "plastic chỉ 26k đó ạ!"
        )
        assert _is_self_reply_match(suggestion_text, [suggestion_text]) is True

    def test_session_15_id_460_regression(self):
        """Verbatim regression from the 2026-04-12 polluted dashboard.

        Comment #460 in session 15 was a re-scrape of suggestion #267
        whose status was `pasted_not_sent`. The first cut of the fix
        missed it because of the `status='sent'` filter. With status
        gone from the query, the same text pair must match.
        """
        text = (
            "Dạ đúng rồi chị yêu ơi!💖 KEM MẶT VICTORY NGỌC TRAI TRẮNG DA "
            "giúp da sáng mịn, đều màu hơn đó ạ!"
        )
        # Even mixed in with unrelated suggestions, the matcher must hit.
        recent = [
            "Chào shop ơi 🎉",  # unrelated viewer-style noise
            text,  # the offending re-scrape source
            "Dạ shop báo giá 350K nha",
        ]
        assert _is_self_reply_match(text, recent) is True


@pytest.mark.asyncio
async def test_fetch_helper_does_not_filter_by_status():
    """The fetch helper must hand the matcher every suggestion in the
    window regardless of status.

    We don't stand up Postgres for this test. Instead we hand the helper
    a stub async session whose ``execute`` records the SQLAlchemy
    statement, then compile that statement to literal SQL and assert
    the WHERE clause does not mention ``status``. This is a structural
    check on the query, not a behavioural one — it pins the contract
    that whoever edits this helper next can't quietly re-add the
    status filter without a test failure.
    """
    captured: dict = {}

    class _StubResult:
        def all(self):
            return []

    class _StubSession:
        async def execute(self, stmt):
            captured["stmt"] = stmt
            return _StubResult()

    await handler_mod._fetch_recent_suggestion_texts(_StubSession(), 17)

    stmt = captured["stmt"]
    # Compile with literal binds so the rendered SQL is human-inspectable.
    rendered = str(
        stmt.compile(compile_kwargs={"literal_binds": True})
    ).lower()

    assert "status" not in rendered, (
        "The recent-suggestion fetch must not gate on suggestion.status. "
        "Status is an extension UI state, not a 'delivered to FB' signal — "
        "see the docstring on _fetch_recent_suggestion_texts for the full "
        "rationale (2026-04-12 polluted-dashboard regression)."
    )
    # Sanity: the query DID still scope by session and time.
    assert "session_id" in rendered
    assert "created_at" in rendered
