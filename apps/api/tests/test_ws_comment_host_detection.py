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
from app.ws.handler import _HOST_REPLY_PREFIXES, _looks_like_host_reply


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
