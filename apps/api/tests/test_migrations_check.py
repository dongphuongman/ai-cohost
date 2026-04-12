"""Tests for the startup migration drift check (app.core.migrations).

These tests do not touch a real database. They construct a fake
``MigrationStatus`` and exercise the env-aware branching logic — that's
what actually decides whether a stale schema kills startup or just logs.
"""

from __future__ import annotations

import logging

import pytest

from app.core import migrations
from app.core.migrations import (
    MigrationStatus,
    _script_head,
    check_migrations_up_to_date,
)


def test_script_head_resolves_to_string():
    """Sanity: alembic.ini is on disk and we can read the script head."""
    head = _script_head()
    assert isinstance(head, str)
    assert len(head) > 0


def test_migration_status_up_to_date_property():
    assert MigrationStatus(head="0004", current="0004").up_to_date is True
    assert MigrationStatus(head="0004", current="0003").up_to_date is False
    assert MigrationStatus(head="0004", current=None).up_to_date is False
    # Defensive: head=None means we couldn't read the scripts at all
    assert MigrationStatus(head=None, current="0004").up_to_date is False


@pytest.mark.asyncio
async def test_drift_in_production_raises(monkeypatch, caplog):
    """Production: stale schema MUST abort startup. Better to fail the deploy."""
    async def fake_status(_engine):
        return MigrationStatus(head="0004", current="0002")

    monkeypatch.setattr(migrations, "get_migration_status", fake_status)

    with pytest.raises(RuntimeError, match="Database schema is out of date"):
        await check_migrations_up_to_date(engine=None, app_env="production")


@pytest.mark.asyncio
async def test_drift_in_development_warns_and_returns(monkeypatch, caplog):
    """Development: stale schema logs a loud warning but does not crash."""
    async def fake_status(_engine):
        return MigrationStatus(head="0004", current="0002")

    monkeypatch.setattr(migrations, "get_migration_status", fake_status)

    with caplog.at_level(logging.WARNING, logger="app.core.migrations"):
        status = await check_migrations_up_to_date(engine=None, app_env="development")

    assert status.up_to_date is False
    assert any("out of date" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_up_to_date_no_warning(monkeypatch, caplog):
    """Healthy case: no warnings, no exceptions, just an info log."""
    async def fake_status(_engine):
        return MigrationStatus(head="0004", current="0004")

    monkeypatch.setattr(migrations, "get_migration_status", fake_status)

    with caplog.at_level(logging.INFO, logger="app.core.migrations"):
        status = await check_migrations_up_to_date(engine=None, app_env="production")

    assert status.up_to_date is True
    # No "out of date" warnings should have been emitted
    assert not any("out of date" in r.message for r in caplog.records)
