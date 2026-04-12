"""Startup migration drift check.

Compares the alembic revision the running code expects (script head) against
the revision currently applied to the database. Used by ``app.main`` during
``lifespan`` startup so a stale dev DB fails fast with a precise error
instead of silently throwing ``UndefinedColumnError`` 50 frames deep on the
first request.

History
-------
Added 2026-04-12 in response to the Nhóm A regression: commit 086a047
introduced ORM mappings and SQL queries referencing ``comments.is_from_host``,
but the corresponding migration (0004) was never applied to the dev DB.
The result was a half-broken WebSocket handler whose INSERTs all failed,
no error visible to the user (extension showed an optimistic local counter),
and zero AI suggestions despite a fully working Celery worker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


# alembic.ini lives at the api package root: apps/api/alembic.ini
# This file is at apps/api/app/core/migrations.py → 3 levels up.
_ALEMBIC_INI = Path(__file__).resolve().parent.parent.parent / "alembic.ini"


@dataclass(frozen=True)
class MigrationStatus:
    """Result of a migration drift check.

    ``head`` is what the on-disk migration scripts say the schema should be.
    ``current`` is what the database says it actually is. They should match.
    ``up_to_date`` is just ``head == current`` for ergonomic call-site checks.
    """

    head: str | None
    current: str | None

    @property
    def up_to_date(self) -> bool:
        return self.head is not None and self.head == self.current


def _script_head() -> str | None:
    """Read the latest revision from alembic migration scripts on disk.

    Pure file I/O — does not touch the database. Safe to call from sync code.
    """
    if not _ALEMBIC_INI.exists():
        # Defensive: if alembic.ini moves, fail loud rather than silently
        # returning "up to date".
        raise FileNotFoundError(
            f"alembic.ini not found at {_ALEMBIC_INI}. "
            f"app.core.migrations needs this file to determine the script head."
        )
    cfg = Config(str(_ALEMBIC_INI))
    return ScriptDirectory.from_config(cfg).get_current_head()


async def get_migration_status(engine: AsyncEngine) -> MigrationStatus:
    """Read script head + DB current revision for the given async engine.

    Uses ``run_sync`` to bridge into alembic's sync MigrationContext API.
    Does not modify the database.
    """
    head = _script_head()

    def _read_current(sync_conn) -> str | None:
        return MigrationContext.configure(sync_conn).get_current_revision()

    async with engine.connect() as conn:
        current = await conn.run_sync(_read_current)

    return MigrationStatus(head=head, current=current)


async def check_migrations_up_to_date(
    engine: AsyncEngine,
    *,
    app_env: str,
) -> MigrationStatus:
    """Verify the DB is at the script head, and react based on environment.

    - In production: raise ``RuntimeError`` so the process dies before any
      request hits a half-migrated schema. Better to fail the deploy than
      to ship a silent data-corruption window.
    - In any other environment (development/staging): log a loud warning
      and return. Devs see the message in their uvicorn output and know to
      run ``alembic upgrade head``.

    Returns the ``MigrationStatus`` so callers (or tests) can inspect it.
    """
    status = await get_migration_status(engine)

    if status.up_to_date:
        logger.info(
            "Database migrations up to date (revision=%s)", status.current
        )
        return status

    # Drift detected.
    msg = (
        f"Database schema is out of date: "
        f"DB revision={status.current!r}, code expects head={status.head!r}. "
        f"Run `alembic upgrade head` from apps/api/."
    )

    if app_env == "production":
        # Hard fail — never serve traffic against a stale schema in prod.
        logger.critical(msg)
        raise RuntimeError(msg)

    # Dev / staging: shout but keep running so devs can still hit endpoints
    # that don't touch the affected tables.
    logger.warning(msg)
    return status
