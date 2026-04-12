"""Add is_from_host column to comments

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-12

Adds a boolean flag distinguishing host/bot comments from viewer comments so
analytics can exclude them from intent classification, top-question
aggregation, and "frequently asked" rollups.

Production-safety notes
-----------------------
This migration is split into online-safe primitives:

- ``ADD COLUMN ... DEFAULT false`` is metadata-only on PostgreSQL 11+ and
  does not rewrite the table.
- The partial index is built with ``CREATE INDEX CONCURRENTLY`` outside the
  alembic transaction (AUTOCOMMIT isolation) so writes to ``comments`` are
  not blocked during deploy.
- The ILIKE backfill heuristic is **not** run here. Ship the column, then
  run ``apps/api/scripts/backfill_self_replies.py`` out-of-band in a
  low-traffic window. Running it inside the migration held ACCESS
  EXCLUSIVE-adjacent locks on the hottest write table in the product and
  was the original deploy-lock risk this split is fixing.

Downgrade note
--------------
**This migration is forward-only in practice.** The ILIKE backfill clears
``intent = NULL`` for matched rows; dropping the column does not restore
the prior intent values, so a rollback permanently loses analytics
classification for every row the backfill touched. The ``downgrade()``
function is provided only so alembic's history machinery is well-formed;
do not use it to recover from a bad deploy.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Metadata-only on PG 11+, takes a brief ACCESS EXCLUSIVE lock.
    op.execute(
        "ALTER TABLE comments "
        "ADD COLUMN is_from_host BOOLEAN NOT NULL DEFAULT false"
    )

    # CREATE INDEX CONCURRENTLY must run outside a transaction. Alembic
    # opens one by default; escape it with AUTOCOMMIT isolation for this
    # statement only. IF NOT EXISTS guards against retries after a partial
    # build (CONCURRENTLY can leave INVALID indexes around on failure).
    bind = op.get_bind()
    with bind.execution_options(isolation_level="AUTOCOMMIT"):
        bind.exec_driver_sql(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "comments_session_viewer_idx "
            "ON comments (session_id) WHERE is_from_host = false"
        )

    # Backfill intentionally NOT run here. See module docstring.


def downgrade() -> None:
    # Forward-only migration — see module docstring. This path exists
    # purely so alembic history is well-formed. Running it after a real
    # upgrade will permanently discard any intent values the offline
    # backfill cleared.
    bind = op.get_bind()
    with bind.execution_options(isolation_level="AUTOCOMMIT"):
        bind.exec_driver_sql(
            "DROP INDEX CONCURRENTLY IF EXISTS comments_session_viewer_idx"
        )
    op.execute("ALTER TABLE comments DROP COLUMN IF EXISTS is_from_host")
