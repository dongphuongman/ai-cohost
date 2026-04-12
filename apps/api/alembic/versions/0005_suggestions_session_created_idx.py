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

Production-safety note
----------------------
The index is built with ``CREATE INDEX CONCURRENTLY`` outside alembic's
transaction (AUTOCOMMIT isolation). The ``suggestions`` table is on the
WS hot path (every AI reply writes a row) and a blocking build would
stall WS inserts and trigger the extension's optimistic-UI failure mode.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    with bind.execution_options(isolation_level="AUTOCOMMIT"):
        bind.exec_driver_sql(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "suggestions_session_created_idx "
            "ON suggestions (session_id, created_at DESC)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    with bind.execution_options(isolation_level="AUTOCOMMIT"):
        bind.exec_driver_sql(
            "DROP INDEX CONCURRENTLY IF EXISTS suggestions_session_created_idx"
        )
