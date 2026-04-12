"""Backfill is_from_host=true for historical self-reply comments.

Re-runs the host-loop self-reply detection from app.ws.handler against every
existing session in the database. The same matching contract used by the
live WS path (exact equality + 30-char prefix in either direction, against
ALL suggestions in the same session — no status filter, no time window for
historical scan) is applied to every viewer comment.

Status filter rationale: dropped on 2026-04-12 after the initial backfill
caught only 76 of ~137 historical leaks. The earlier ``status='sent'``
filter assumed ``pasted_not_sent`` and ``suggested`` could not have been
delivered to FB chat. They can — Quick Paste fills the chat input but the
extension never sees the host's manual click-Send, and races between the
re-scrape WS event and the status PATCH leave some real sends with status
``suggested``. Same-session scope is the actual safety rail. See
``app.ws.handler._fetch_recent_suggestion_texts`` for the full writeup.

Why this exists
---------------
Sessions created before the live dedup landed contain AI replies that were
re-scraped from Facebook chat and stored as viewer comments. Those rows
pollute Top Questions, intent rollups, and the FAQ frequency report. This
script flips them to is_from_host=true and clears their intent so the
analytics layer treats them the same as any other host message.

Usage
-----
    # Inspect what would change without touching the DB
    uv run python -m scripts.backfill_self_replies --dry-run

    # After reviewing the dry-run report, apply the changes
    uv run python -m scripts.backfill_self_replies --apply

Safety
------
- Default mode is --dry-run; --apply must be explicit.
- Per-session report shows which comment IDs match which suggestion IDs
  so spot-checks are possible before --apply.
- A confirmation prompt fires before --apply commits, with the total row
  count. Ctrl-C aborts cleanly.
- The matching logic is identical to the live path so dry-run and live
  results stay aligned.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import text

from app.core.database import async_session, engine
from app.ws.handler import _is_self_reply_match


@dataclass
class Match:
    session_id: int
    comment_id: int
    suggestion_id: int
    text_preview: str


async def scan() -> list[Match]:
    """Walk every session and collect viewer comments that match a sent suggestion."""
    matches: list[Match] = []

    async with async_session() as db:
        # Sessions that have at least one suggestion AND at least one viewer
        # comment — the only ones where a self-reply leak is possible. No
        # status filter on suggestions: pasted_not_sent and suggested can
        # also leak through to FB chat (extension can't observe the host's
        # manual Send click after Quick Paste, and the re-scrape WS event
        # can race the status PATCH).
        sessions = await db.execute(text("""
            SELECT DISTINCT s.id
              FROM live_sessions s
              JOIN suggestions g ON g.session_id = s.id
              JOIN comments    c ON c.session_id = s.id AND c.is_from_host = false
        """))
        session_ids = [row.id for row in sessions]

    print(f"Scanning {len(session_ids)} candidate sessions...")

    for sid in session_ids:
        async with async_session() as db:
            sug_rows = await db.execute(text("""
                SELECT id, text FROM suggestions
                 WHERE session_id = :s
            """), {"s": sid})
            sugs = [(r.id, r.text) for r in sug_rows]

            cmt_rows = await db.execute(text("""
                SELECT id, text FROM comments
                 WHERE session_id = :s AND is_from_host = false
            """), {"s": sid})

            sug_texts = [t for _, t in sugs]
            for c in cmt_rows:
                if _is_self_reply_match(c.text, sug_texts):
                    # Find the specific suggestion that matched (for the report)
                    matched_sid = None
                    for sg_id, sg_text in sugs:
                        if _is_self_reply_match(c.text, [sg_text]):
                            matched_sid = sg_id
                            break
                    matches.append(Match(
                        session_id=sid,
                        comment_id=c.id,
                        suggestion_id=matched_sid or 0,
                        text_preview=(c.text or "")[:80],
                    ))

    return matches


def print_report(matches: list[Match]) -> None:
    if not matches:
        print("\nNo self-reply leaks found. Database is clean.")
        return

    print(f"\nFound {len(matches)} viewer comment(s) that look like self-replies:")
    by_session: dict[int, list[Match]] = {}
    for m in matches:
        by_session.setdefault(m.session_id, []).append(m)

    for sid, ms in sorted(by_session.items()):
        print(f"\n  session {sid}: {len(ms)} match(es)")
        for m in ms[:5]:
            print(f"    comment #{m.comment_id} ← suggestion #{m.suggestion_id}: {m.text_preview}")
        if len(ms) > 5:
            print(f"    ... and {len(ms) - 5} more")


async def apply_matches(matches: list[Match]) -> int:
    if not matches:
        return 0
    ids = [m.comment_id for m in matches]
    async with async_session() as db:
        result = await db.execute(text("""
            UPDATE comments
               SET is_from_host = true,
                   intent = NULL
             WHERE id = ANY(:ids)
        """), {"ids": ids})
        await db.commit()
        return result.rowcount or 0


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Report only, no DB changes")
    group.add_argument("--apply", action="store_true", help="Apply changes to the database")
    args = parser.parse_args()

    matches = await scan()
    print_report(matches)

    if args.dry_run:
        print("\n[dry-run] No changes written.")
    elif args.apply:
        if not matches:
            print("\nNothing to apply.")
        else:
            try:
                resp = input(f"\nApply update to {len(matches)} comment(s)? [y/N] ")
            except EOFError:
                resp = ""
            if resp.strip().lower() == "y":
                rows = await apply_matches(matches)
                print(f"Updated {rows} row(s).")
            else:
                print("Aborted.")

    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
