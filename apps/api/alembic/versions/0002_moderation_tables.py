"""Add moderation tables: shop_moderation_rules and flagged_comments

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-11

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE shop_moderation_rules (
        id                      BIGSERIAL PRIMARY KEY,
        shop_id                 BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,

        blocked_keywords        TEXT[] DEFAULT '{}',
        blocked_patterns        TEXT[] DEFAULT '{}',

        whitelisted_users       TEXT[] DEFAULT '{}',
        blacklisted_users       TEXT[] DEFAULT '{}',

        auto_hide_spam          BOOLEAN DEFAULT true,
        auto_hide_links         BOOLEAN DEFAULT true,
        auto_flag_toxic         BOOLEAN DEFAULT true,
        emoji_flood_threshold   INT DEFAULT 6,
        min_comment_length      INT DEFAULT 2,

        use_llm_classify        BOOLEAN DEFAULT false,
        llm_classify_rate_limit INT DEFAULT 10,

        created_at              TIMESTAMPTZ DEFAULT now(),
        updated_at              TIMESTAMPTZ DEFAULT now(),

        UNIQUE(shop_id)
    );
    """)

    op.execute("""
    CREATE TABLE flagged_comments (
        id              BIGSERIAL PRIMARY KEY,
        comment_id      BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
        shop_id         BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        reason          TEXT,
        status          TEXT DEFAULT 'pending',
        reviewed_by     BIGINT,
        reviewed_at     TIMESTAMPTZ,
        created_at      TIMESTAMPTZ DEFAULT now(),

        UNIQUE(comment_id)
    );
    """)

    op.execute("CREATE INDEX flagged_comments_shop_status_idx ON flagged_comments(shop_id, status);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS flagged_comments;")
    op.execute("DROP TABLE IF EXISTS shop_moderation_rules;")
