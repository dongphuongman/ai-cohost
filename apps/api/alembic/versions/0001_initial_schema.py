"""Initial schema with all 16 tables

Revision ID: 0001
Revises: None
Create Date: 2026-04-10

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # --- Tenant ---

    op.execute("""
    CREATE TABLE shops (
        id              BIGSERIAL PRIMARY KEY,
        uuid            UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
        name            TEXT NOT NULL,
        slug            TEXT UNIQUE NOT NULL,
        industry        TEXT,
        team_size       TEXT,
        owner_user_id   BIGINT NOT NULL,
        plan            TEXT NOT NULL DEFAULT 'trial',
        plan_status     TEXT NOT NULL DEFAULT 'active',
        trial_ends_at   TIMESTAMPTZ,
        timezone        TEXT DEFAULT 'Asia/Ho_Chi_Minh',
        settings        JSONB DEFAULT '{}',
        created_at      TIMESTAMPTZ DEFAULT now(),
        updated_at      TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX shops_owner_idx ON shops (owner_user_id)")
    op.execute("CREATE INDEX shops_plan_idx ON shops (plan, plan_status)")

    op.execute("""
    CREATE TABLE users (
        id              BIGSERIAL PRIMARY KEY,
        uuid            UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
        email           TEXT UNIQUE NOT NULL,
        email_verified  BOOLEAN DEFAULT false,
        password_hash   TEXT,
        full_name       TEXT,
        avatar_url      TEXT,
        phone           TEXT,
        oauth_provider  TEXT,
        oauth_id        TEXT,
        two_fa_enabled  BOOLEAN DEFAULT false,
        last_login_at   TIMESTAMPTZ,
        created_at      TIMESTAMPTZ DEFAULT now(),
        updated_at      TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX users_email_idx ON users (email)")
    op.execute("CREATE INDEX users_oauth_idx ON users (oauth_provider, oauth_id)")

    op.execute("""
    CREATE TABLE shop_members (
        id          BIGSERIAL PRIMARY KEY,
        shop_id     BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role        TEXT NOT NULL CHECK (role IN ('owner','admin','member')),
        invited_by  BIGINT REFERENCES users(id),
        invited_at  TIMESTAMPTZ DEFAULT now(),
        joined_at   TIMESTAMPTZ,
        status      TEXT DEFAULT 'active',
        UNIQUE (shop_id, user_id)
    )
    """)
    op.execute("CREATE INDEX shop_members_user_idx ON shop_members (user_id)")
    op.execute("CREATE INDEX shop_members_shop_idx ON shop_members (shop_id)")

    # --- Content ---

    op.execute("""
    CREATE TABLE products (
        id                    BIGSERIAL PRIMARY KEY,
        shop_id               BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        name                  TEXT NOT NULL,
        description           TEXT,
        price                 NUMERIC(12, 2),
        currency              TEXT DEFAULT 'VND',
        highlights            TEXT[] DEFAULT '{}',
        images                JSONB DEFAULT '[]',
        external_url          TEXT,
        category              TEXT,
        is_active             BOOLEAN DEFAULT true,
        embedding             vector(768),
        embedding_model       TEXT,
        embedding_updated_at  TIMESTAMPTZ,
        created_at            TIMESTAMPTZ DEFAULT now(),
        updated_at            TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("""
    CREATE INDEX products_embedding_idx ON products
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("CREATE INDEX products_shop_active_idx ON products (shop_id, is_active)")
    op.execute("CREATE INDEX products_shop_category_idx ON products (shop_id, category)")
    op.execute("CREATE INDEX products_name_trgm_idx ON products USING gin (name gin_trgm_ops)")

    op.execute("""
    CREATE TABLE product_faqs (
        id                    BIGSERIAL PRIMARY KEY,
        product_id            BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        shop_id               BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        question              TEXT NOT NULL,
        answer                TEXT NOT NULL,
        source                TEXT DEFAULT 'manual',
        order_index           INT DEFAULT 0,
        embedding             vector(768),
        embedding_model       TEXT,
        embedding_updated_at  TIMESTAMPTZ,
        created_at            TIMESTAMPTZ DEFAULT now(),
        updated_at            TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("""
    CREATE INDEX product_faqs_embedding_idx ON product_faqs
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("CREATE INDEX product_faqs_shop_product_idx ON product_faqs (shop_id, product_id)")

    op.execute("""
    CREATE TABLE personas (
        id              BIGSERIAL PRIMARY KEY,
        shop_id         BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        name            TEXT NOT NULL,
        description     TEXT,
        tone            TEXT,
        quirks          TEXT[],
        sample_phrases  TEXT[],
        voice_clone_id  BIGINT,
        is_default      BOOLEAN DEFAULT false,
        is_preset       BOOLEAN DEFAULT false,
        created_at      TIMESTAMPTZ DEFAULT now(),
        updated_at      TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX personas_shop_idx ON personas (shop_id)")
    op.execute("""
    CREATE UNIQUE INDEX personas_shop_default_idx ON personas (shop_id)
        WHERE is_default = true
    """)

    # --- Session ---

    op.execute("""
    CREATE TABLE live_sessions (
        id                  BIGSERIAL PRIMARY KEY,
        uuid                UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
        shop_id             BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        started_by          BIGINT NOT NULL REFERENCES users(id),
        platform            TEXT NOT NULL CHECK (platform IN
                              ('facebook','tiktok','youtube','shopee','other')),
        platform_url        TEXT,
        persona_id          BIGINT REFERENCES personas(id),
        active_product_ids  BIGINT[],
        started_at          TIMESTAMPTZ DEFAULT now(),
        ended_at            TIMESTAMPTZ,
        duration_seconds    INT,
        status              TEXT DEFAULT 'running',
        comments_count      INT DEFAULT 0,
        suggestions_count   INT DEFAULT 0,
        sent_count          INT DEFAULT 0,
        pasted_not_sent_count INT DEFAULT 0,
        read_count          INT DEFAULT 0,
        dismissed_count     INT DEFAULT 0,
        avg_latency_ms      INT,
        metadata            JSONB DEFAULT '{}',
        created_at          TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute(
        "CREATE INDEX live_sessions_shop_started_idx ON live_sessions (shop_id, started_at DESC)"
    )
    op.execute("""
    CREATE INDEX live_sessions_status_idx ON live_sessions (status)
        WHERE status = 'running'
    """)

    op.execute("""
    CREATE TABLE comments (
        id                  BIGSERIAL PRIMARY KEY,
        session_id          BIGINT NOT NULL REFERENCES live_sessions(id) ON DELETE CASCADE,
        shop_id             BIGINT NOT NULL REFERENCES shops(id),
        external_user_id    TEXT,
        external_user_name  TEXT,
        text                TEXT NOT NULL,
        received_at         TIMESTAMPTZ DEFAULT now(),
        language            TEXT DEFAULT 'vi',
        sentiment           TEXT,
        intent              TEXT,
        confidence          FLOAT,
        is_spam             BOOLEAN DEFAULT false,
        is_processed        BOOLEAN DEFAULT false,
        created_at          TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute(
        "CREATE INDEX comments_session_received_idx ON comments (session_id, received_at DESC)"
    )
    op.execute("CREATE INDEX comments_shop_idx ON comments (shop_id, received_at DESC)")
    op.execute("""
    CREATE INDEX comments_unprocessed_idx ON comments (session_id)
        WHERE is_processed = false
    """)

    op.execute("""
    CREATE TABLE suggestions (
        id              BIGSERIAL PRIMARY KEY,
        comment_id      BIGINT NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
        session_id      BIGINT NOT NULL REFERENCES live_sessions(id) ON DELETE CASCADE,
        shop_id         BIGINT NOT NULL REFERENCES shops(id),
        text            TEXT NOT NULL,
        edited_text     TEXT,
        llm_model       TEXT,
        llm_provider    TEXT,
        prompt_version  TEXT,
        input_tokens    INT,
        output_tokens   INT,
        latency_ms      INT,
        rag_product_ids BIGINT[],
        rag_faq_ids     BIGINT[],
        status          TEXT NOT NULL DEFAULT 'suggested'
                        CHECK (status IN ('suggested','sent','pasted_not_sent',
                                          'read','dismissed','edited')),
        action_at       TIMESTAMPTZ,
        audio_url       TEXT,
        created_at      TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX suggestions_comment_idx ON suggestions (comment_id)")
    op.execute("CREATE INDEX suggestions_session_idx ON suggestions (session_id)")
    op.execute("CREATE INDEX suggestions_shop_status_idx ON suggestions (shop_id, status)")

    # --- Scripts ---

    op.execute("""
    CREATE TABLE scripts (
        id                          BIGSERIAL PRIMARY KEY,
        shop_id                     BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        created_by                  BIGINT NOT NULL REFERENCES users(id),
        title                       TEXT NOT NULL,
        content                     TEXT NOT NULL,
        product_ids                 BIGINT[] NOT NULL,
        persona_id                  BIGINT REFERENCES personas(id),
        duration_target             INT,
        tone                        TEXT,
        special_notes               TEXT,
        word_count                  INT,
        estimated_duration_seconds  INT,
        cta_count                   INT,
        llm_model                   TEXT,
        llm_provider                TEXT,
        prompt_version              TEXT,
        generation_cost             NUMERIC(10, 6),
        parent_script_id            BIGINT REFERENCES scripts(id),
        version                     INT DEFAULT 1,
        created_at                  TIMESTAMPTZ DEFAULT now(),
        updated_at                  TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX scripts_shop_created_idx ON scripts (shop_id, created_at DESC)")
    op.execute("CREATE INDEX scripts_shop_products_idx ON scripts USING gin (product_ids)")

    op.execute("""
    CREATE TABLE script_samples (
        id              BIGSERIAL PRIMARY KEY,
        category        TEXT NOT NULL,
        persona_style   TEXT NOT NULL,
        title           TEXT,
        content         TEXT NOT NULL,
        quality_score   INT CHECK (quality_score BETWEEN 1 AND 5),
        tags            TEXT[],
        embedding       vector(768),
        created_by      TEXT,
        created_at      TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("""
    CREATE INDEX script_samples_embedding_idx ON script_samples
        USING hnsw (embedding vector_cosine_ops)
    """)
    op.execute("""
    CREATE INDEX script_samples_category_style_idx ON script_samples
        (category, persona_style, quality_score DESC)
    """)

    # --- Media ---

    op.execute("""
    CREATE TABLE dh_videos (
        id                      BIGSERIAL PRIMARY KEY,
        shop_id                 BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        created_by              BIGINT NOT NULL REFERENCES users(id),
        script_id               BIGINT REFERENCES scripts(id),
        source_text             TEXT NOT NULL,
        avatar_preset           TEXT,
        avatar_custom_url       TEXT,
        voice_clone_id          BIGINT,
        background              TEXT,
        provider                TEXT NOT NULL,
        provider_job_id         TEXT,
        video_url               TEXT,
        video_duration_seconds  INT,
        file_size_bytes         BIGINT,
        has_watermark           BOOLEAN DEFAULT true,
        status                  TEXT DEFAULT 'queued'
                                CHECK (status IN ('queued','processing','ready','failed','expired')),
        error_message           TEXT,
        credits_used            NUMERIC(10, 4),
        created_at              TIMESTAMPTZ DEFAULT now(),
        completed_at            TIMESTAMPTZ,
        expires_at              TIMESTAMPTZ
    )
    """)
    op.execute("CREATE INDEX dh_videos_shop_idx ON dh_videos (shop_id, created_at DESC)")
    op.execute("""
    CREATE INDEX dh_videos_status_idx ON dh_videos (status)
        WHERE status IN ('queued','processing')
    """)

    op.execute("""
    CREATE TABLE voice_clones (
        id                      BIGSERIAL PRIMARY KEY,
        shop_id                 BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        created_by              BIGINT NOT NULL REFERENCES users(id),
        name                    TEXT NOT NULL,
        description             TEXT,
        source_audio_url        TEXT NOT NULL,
        source_duration_seconds INT,
        consent_form_url        TEXT NOT NULL,
        consent_confirmed_at    TIMESTAMPTZ NOT NULL,
        consent_confirmed_by    BIGINT NOT NULL REFERENCES users(id),
        consent_person_name     TEXT NOT NULL,
        provider                TEXT NOT NULL,
        provider_voice_id       TEXT,
        status                  TEXT DEFAULT 'processing'
                                CHECK (status IN ('processing','ready','failed','deleted')),
        created_at              TIMESTAMPTZ DEFAULT now(),
        deleted_at              TIMESTAMPTZ
    )
    """)
    op.execute("""
    CREATE INDEX voice_clones_shop_idx ON voice_clones (shop_id)
        WHERE deleted_at IS NULL
    """)

    # --- Billing ---

    op.execute("""
    CREATE TABLE subscriptions (
        id                          BIGSERIAL PRIMARY KEY,
        shop_id                     BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        plan                        TEXT NOT NULL,
        status                      TEXT NOT NULL,
        provider                    TEXT NOT NULL,
        provider_customer_id        TEXT,
        provider_subscription_id    TEXT,
        current_period_start        TIMESTAMPTZ,
        current_period_end          TIMESTAMPTZ,
        cancel_at_period_end        BOOLEAN DEFAULT false,
        cancelled_at                TIMESTAMPTZ,
        trial_start                 TIMESTAMPTZ,
        trial_end                   TIMESTAMPTZ,
        amount                      NUMERIC(10, 2),
        currency                    TEXT DEFAULT 'USD',
        created_at                  TIMESTAMPTZ DEFAULT now(),
        updated_at                  TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX subscriptions_shop_idx ON subscriptions (shop_id)")
    op.execute("""
    CREATE INDEX subscriptions_provider_idx ON subscriptions
        (provider, provider_subscription_id)
    """)

    op.execute("""
    CREATE TABLE invoices (
        id                  BIGSERIAL PRIMARY KEY,
        shop_id             BIGINT NOT NULL REFERENCES shops(id),
        subscription_id     BIGINT REFERENCES subscriptions(id),
        invoice_number      TEXT UNIQUE NOT NULL,
        amount              NUMERIC(10, 2) NOT NULL,
        currency            TEXT DEFAULT 'USD',
        status              TEXT NOT NULL,
        provider            TEXT,
        provider_invoice_id TEXT,
        pdf_url             TEXT,
        issued_at           TIMESTAMPTZ DEFAULT now(),
        due_at              TIMESTAMPTZ,
        paid_at             TIMESTAMPTZ
    )
    """)
    op.execute("CREATE INDEX invoices_shop_idx ON invoices (shop_id, issued_at DESC)")

    op.execute("""
    CREATE TABLE usage_logs (
        id              BIGSERIAL PRIMARY KEY,
        shop_id         BIGINT NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
        user_id         BIGINT REFERENCES users(id),
        resource_type   TEXT NOT NULL,
        resource_id     BIGINT,
        quantity        NUMERIC(12, 4) NOT NULL,
        unit            TEXT NOT NULL,
        cost_usd        NUMERIC(10, 6),
        billing_period  DATE NOT NULL,
        metadata        JSONB DEFAULT '{}',
        created_at      TIMESTAMPTZ DEFAULT now()
    )
    """)
    op.execute("""
    CREATE INDEX usage_logs_shop_period_idx ON usage_logs
        (shop_id, billing_period, resource_type)
    """)
    op.execute(
        "CREATE INDEX usage_logs_resource_idx ON usage_logs (resource_type, created_at DESC)"
    )

    # --- RLS Policies ---

    for table in [
        "products", "product_faqs", "live_sessions", "comments",
        "suggestions", "scripts", "dh_videos", "voice_clones",
    ]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
        CREATE POLICY shop_isolation ON {table}
            FOR ALL
            USING (shop_id = current_setting('app.current_shop_id')::BIGINT)
        """)


def downgrade() -> None:
    tables = [
        "usage_logs", "invoices", "subscriptions",
        "voice_clones", "dh_videos",
        "script_samples", "scripts",
        "suggestions", "comments", "live_sessions",
        "personas", "product_faqs", "products",
        "shop_members", "users", "shops",
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
