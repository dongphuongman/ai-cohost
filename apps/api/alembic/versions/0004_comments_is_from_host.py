"""Add is_from_host column to comments

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-12

Adds a boolean flag distinguishing host/bot comments from viewer comments so
analytics can exclude them from intent classification, top-question
aggregation, and "frequently asked" rollups.

- Default false: existing rows are treated as viewer comments.
- A backfill heuristic flips well-known bot reply prefixes ("Dạ, chị/em ơi",
  "Dạ shop", "Cảm ơn bạn") to is_from_host = true and clears their intent so
  they no longer pollute analytics. Test on a dev DB before promoting.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE comments "
        "ADD COLUMN is_from_host BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "CREATE INDEX comments_session_viewer_idx "
        "ON comments (session_id) WHERE is_from_host = false"
    )

    # Backfill: mark obvious bot replies and clear their intent so they stop
    # being counted as viewer questions/complaints in analytics.
    op.execute(
        """
        UPDATE comments
           SET is_from_host = true,
               intent = NULL
         WHERE text ILIKE 'Dạ, chị/em ơi%'
            OR text ILIKE 'Dạ shop%'
            OR text ILIKE 'Cảm ơn bạn%'
            OR text ILIKE 'Dạ vâng%'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS comments_session_viewer_idx")
    op.execute("ALTER TABLE comments DROP COLUMN IF EXISTS is_from_host")
