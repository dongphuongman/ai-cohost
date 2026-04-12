"""Add provider CHECK constraint, default 'liteavatar', and prefer_quality column

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-12

Part of F7 digital human provider router refactor (Đợt 1).

- Adds CHECK constraint restricting dh_videos.provider to ('liteavatar','heygen').
  Existing rows are 'heygen' (the only previous value), so the constraint
  cannot fail on backfill.
- Sets the column default to 'liteavatar' for new inserts.
- Adds prefer_quality BOOLEAN NOT NULL DEFAULT false. Existing rows are
  backfilled to false.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. prefer_quality column — added before constraint so backfill is atomic
    op.execute(
        "ALTER TABLE dh_videos "
        "ADD COLUMN prefer_quality BOOLEAN NOT NULL DEFAULT false"
    )

    # 2. Allow either provider value going forward
    op.execute(
        "ALTER TABLE dh_videos "
        "ADD CONSTRAINT dh_videos_provider_check "
        "CHECK (provider IN ('liteavatar', 'heygen'))"
    )

    # 3. Default future inserts to the cheap self-hosted provider.
    #    The actual selection happens in the worker (DHProviderRouter); the
    #    default is just a safety net for direct SQL inserts.
    op.execute(
        "ALTER TABLE dh_videos ALTER COLUMN provider SET DEFAULT 'liteavatar'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE dh_videos ALTER COLUMN provider DROP DEFAULT")
    op.execute(
        "ALTER TABLE dh_videos DROP CONSTRAINT IF EXISTS dh_videos_provider_check"
    )
    op.execute("ALTER TABLE dh_videos DROP COLUMN IF EXISTS prefer_quality")
