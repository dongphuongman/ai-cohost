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


async def scan() -> list[Change]:
    """Walk every viewer comment and find ones the new classifier upgrades."""
    changes: list[Change] = []

    async with async_session() as db:
        # Only viewer comments. Self-replies (is_from_host=true) and
        # historically-spammed rows are out of scope.
        rows = await db.execute(text("""
            SELECT id, session_id, text, intent
              FROM comments
             WHERE is_from_host = false
               AND is_spam = false
        """))
        all_rows = list(rows)

    print(f"Scanning {len(all_rows)} viewer comments...")

    for r in all_rows:
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


async def apply_changes(changes: list[Change]) -> int:
    if not changes:
        return 0

    # Update one row at a time so each gets its own intent value.
    # Volume is small (historical bugfix); a single batched UPDATE
    # would need a CASE expression and is not worth the complexity.
    total = 0
    async with async_session() as db:
        for c in changes:
            result = await db.execute(text("""
                UPDATE comments
                   SET intent = :intent,
                       confidence = :confidence
                 WHERE id = :id
            """), {"intent": c.new_intent, "confidence": c.new_confidence, "id": c.comment_id})
            total += result.rowcount or 0
        await db.commit()
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
