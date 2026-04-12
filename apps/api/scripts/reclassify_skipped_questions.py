"""Backfill intent labels for historical comments after the
2026-04-12 classifier fix (greeting/praise was swallowing real
buying-intent questions).

Re-runs ``classify_rule_based`` against every viewer comment in the
database. Reports any comment whose intent would change under the
new logic. Updates the ``intent`` and ``confidence`` columns only —
deliberately does NOT enqueue suggestion generation. Those comments
are already historical: regenerating suggestions for live sessions
that ended hours or days ago would be noise, not value. The point of
this backfill is to fix the analytics rollups (Top Questions, intent
breakdown, FAQ frequency) so the dashboard reflects what the new
classifier would have done.

Usage
-----
    # Inspect what would change without touching the DB
    uv run python -m scripts.reclassify_skipped_questions --dry-run

    # After reviewing the dry-run report, apply the changes
    uv run python -m scripts.reclassify_skipped_questions --apply

Safety
------
- Default mode requires --dry-run or --apply explicitly.
- Self-reply comments (is_from_host=true) are skipped — they were
  already cleaned by ``backfill_self_replies.py`` and should not be
  reclassified.
- Spam/toxic/blocked classifications are NEVER changed by this script.
  We only flip skip_ai → generate_ai-equivalent intents (greeting →
  question/pricing/etc., praise → question/pricing/etc.). Anything
  the new classifier would still mark as spam/toxic/blocked is left
  alone to avoid touching moderation decisions retroactively.
- A confirmation prompt fires before --apply commits.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import text

from app.core.database import async_session, engine
from app.services.comment_classifier import classify_rule_based


# Intents we consider "skip" — historically these meant the comment got
# no AI suggestion. If the new classifier upgrades any of these to a
# real intent, that is the bug we are backfilling.
_SKIP_INTENTS = frozenset({"greeting", "praise", "noise", "other"})

# Intents the new classifier produces that route to AI. If the old
# intent was in _SKIP_INTENTS and the new one is in this set, the row
# is a true bugfix candidate.
_AI_INTENTS = frozenset({
    "question", "pricing", "shipping", "complaint", "wholesale", "promotion"
})


@dataclass
class Change:
    comment_id: int
    session_id: int
    old_intent: str | None
    new_intent: str
    new_confidence: float
    text_preview: str


_SCAN_PAGE_SIZE = 5000


async def scan() -> list[Change]:
    """Walk every viewer comment and find ones the new classifier upgrades.

    Paginated by ``id`` range so we never hold the entire comment history
    in memory or pin one long-lived session open against the live writer.
    Each page opens and closes its own session.
    """
    changes: list[Change] = []
    last_id = 0
    scanned = 0

    while True:
        async with async_session() as db:
            rows = await db.execute(text("""
                SELECT id, session_id, text, intent
                  FROM comments
                 WHERE is_from_host = false
                   AND is_spam = false
                   AND id > :last_id
                 ORDER BY id
                 LIMIT :lim
            """), {"last_id": last_id, "lim": _SCAN_PAGE_SIZE})
            page = list(rows)

        if not page:
            break

        for r in page:
            old_intent = r.intent
            # Only consider rows whose old intent was a skip — we are not
            # going to override moderation decisions (spam/toxic/blocked) or
            # already-correct routings.
            if old_intent not in _SKIP_INTENTS:
                continue

            try:
                result = classify_rule_based(r.text or "")
            except Exception as exc:  # pragma: no cover - defensive
                print(f"  classify failed for comment {r.id}: {exc!r}")
                continue

            # Only flag rows the new classifier promotes to a real AI intent.
            if result.intent not in _AI_INTENTS:
                continue

            changes.append(Change(
                comment_id=r.id,
                session_id=r.session_id,
                old_intent=old_intent,
                new_intent=result.intent,
                new_confidence=result.confidence,
                text_preview=(r.text or "")[:80],
            ))

        scanned += len(page)
        last_id = page[-1].id
        print(f"  scanned {scanned} comments, {len(changes)} candidates so far")

    return changes


def print_report(changes: list[Change]) -> None:
    if not changes:
        print("\nNo intent upgrades found. Historical labels are consistent "
              "with the new classifier.")
        return

    print(f"\nFound {len(changes)} comment(s) the new classifier would "
          f"route to AI but were historically skipped:")

    transitions: Counter[tuple[str, str]] = Counter()
    by_session: dict[int, list[Change]] = {}
    for c in changes:
        transitions[(c.old_intent or "?", c.new_intent)] += 1
        by_session.setdefault(c.session_id, []).append(c)

    print("\n  Transition counts (old → new):")
    for (old, new), count in sorted(transitions.items(), key=lambda x: -x[1]):
        print(f"    {old:>10} → {new:<10}  {count}")

    print("\n  Sample changes per session (max 3 each):")
    for sid, cs in sorted(by_session.items())[:10]:
        print(f"\n    session {sid}: {len(cs)} change(s)")
        for c in cs[:3]:
            print(f"      #{c.comment_id} {c.old_intent} → {c.new_intent}: "
                  f"{c.text_preview}")
    if len(by_session) > 10:
        print(f"\n    ... and {len(by_session) - 10} more sessions")


_APPLY_BATCH_SIZE = 500
_APPLY_BATCH_SLEEP_S = 0.05


async def apply_changes(changes: list[Change]) -> int:
    """Chunked UPDATE with per-batch commits and an audit log.

    The previous version ran one row-by-row transaction for every change
    and committed once at the end. On a historical bugfix touching
    thousands of comments this held row locks against the live writer
    for the entire run and any crash mid-loop lost the whole update.
    We now:

    - Write an audit log of (run_ts, comment_id, old_intent, new_intent)
      BEFORE touching the DB so the change set is reversible.
    - Batch into ``_APPLY_BATCH_SIZE`` rows using a single UPDATE ... FROM
      (VALUES ...) per batch (one round-trip per chunk).
    - Commit per batch and sleep briefly between batches so the live WS
      insert path can interleave.
    """
    if not changes:
        return 0

    from datetime import datetime, timezone
    from pathlib import Path
    audit_path = Path("reclassify_skipped_questions_audit.log")
    run_ts = datetime.now(timezone.utc).isoformat()
    with audit_path.open("a") as f:
        f.write(f"# run_at={run_ts} total={len(changes)}\n")
        for c in changes:
            f.write(
                f"{run_ts}\t{c.comment_id}\t{c.old_intent or ''}\t{c.new_intent}\n"
            )
    print(f"  audit log: {audit_path.resolve()}")

    total = 0
    for start in range(0, len(changes), _APPLY_BATCH_SIZE):
        chunk = changes[start:start + _APPLY_BATCH_SIZE]
        # Build a VALUES list + single UPDATE ... FROM. Keeps each batch
        # to one round-trip instead of N row-level UPDATEs.
        values_sql = ", ".join(
            f"(:id_{i}, :intent_{i}, :conf_{i})" for i in range(len(chunk))
        )
        params: dict[str, object] = {}
        for i, c in enumerate(chunk):
            params[f"id_{i}"] = c.comment_id
            params[f"intent_{i}"] = c.new_intent
            params[f"conf_{i}"] = c.new_confidence
        stmt = text(f"""
            UPDATE comments
               SET intent = v.intent,
                   confidence = v.confidence
              FROM (VALUES {values_sql}) AS v(id, intent, confidence)
             WHERE comments.id = v.id
        """)
        async with async_session() as db:
            result = await db.execute(stmt, params)
            await db.commit()
            total += result.rowcount or 0
        print(f"  applied {min(start + _APPLY_BATCH_SIZE, len(changes))}/{len(changes)}")
        await asyncio.sleep(_APPLY_BATCH_SLEEP_S)

    return total


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Report only, no DB changes")
    group.add_argument("--apply", action="store_true", help="Apply changes to the database")
    args = parser.parse_args()

    changes = await scan()
    print_report(changes)

    if args.dry_run:
        print("\n[dry-run] No changes written.")
    elif args.apply:
        if not changes:
            print("\nNothing to apply.")
        else:
            try:
                resp = input(f"\nApply intent update to {len(changes)} comment(s)? [y/N] ")
            except EOFError:
                resp = ""
            if resp.strip().lower() == "y":
                rows = await apply_changes(changes)
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
