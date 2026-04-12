"""Composite index on suggestions(session_id, created_at)

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-12

Supports the host-loop self-reply detection query in app.ws.handler:

    SELECT text FROM suggestions
     WHERE session_id = :sid
       AND status = 'sent'
       AND created_at >= :cutoff
     ORDER BY created_at DESC
     LIMIT 50

The pre-existing ``suggestions_session_idx`` covers session_id alone, which
is fine for short sessions but degrades when a long-running stream
accumulates thousands of suggestions. The composite index lets Postgres
range-scan the recent window directly instead of fetching every row in
the session and filtering by created_at in memory.

Cheap to add — small table, online btree, no rewrite. Safe to roll back.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS suggestions_session_created_idx "
        "ON suggestions (session_id, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS suggestions_session_created_idx")
