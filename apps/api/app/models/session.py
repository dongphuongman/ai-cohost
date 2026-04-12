from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, Index, Integer, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LiveSession(Base):
    __tablename__ = "live_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[str] = mapped_column(
        UUID(as_uuid=False), server_default=text("uuid_generate_v4()"), unique=True, nullable=False
    )
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    started_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    platform_url: Mapped[str | None] = mapped_column(Text)
    persona_id: Mapped[int | None] = mapped_column(BigInteger)
    active_product_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))

    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default="running")

    comments_count: Mapped[int] = mapped_column(Integer, server_default="0")
    suggestions_count: Mapped[int] = mapped_column(Integer, server_default="0")
    sent_count: Mapped[int] = mapped_column(Integer, server_default="0")
    pasted_not_sent_count: Mapped[int] = mapped_column(Integer, server_default="0")
    read_count: Mapped[int] = mapped_column(Integer, server_default="0")
    dismissed_count: Mapped[int] = mapped_column(Integer, server_default="0")
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer)

    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("live_sessions_shop_started_idx", "shop_id", started_at.desc()),
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    external_user_id: Mapped[str | None] = mapped_column(Text)
    external_user_name: Mapped[str | None] = mapped_column(Text)
    text_: Mapped[str] = mapped_column("text", Text, nullable=False)

    received_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    language: Mapped[str] = mapped_column(Text, server_default="vi")
    sentiment: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)

    is_spam: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_from_host: Mapped[bool] = mapped_column(Boolean, server_default="false")
    is_processed: Mapped[bool] = mapped_column(Boolean, server_default="false")

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("comments_session_received_idx", "session_id", received_at.desc()),
        Index("comments_shop_idx", "shop_id", received_at.desc()),
    )


class Suggestion(Base):
    __tablename__ = "suggestions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    text_: Mapped[str] = mapped_column("text", Text, nullable=False)
    edited_text: Mapped[str | None] = mapped_column(Text)

    llm_model: Mapped[str | None] = mapped_column(Text)
    llm_provider: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    rag_product_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    rag_faq_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="suggested")
    action_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    audio_url: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("suggestions_comment_idx", "comment_id"),
        Index("suggestions_session_idx", "session_id"),
        Index("suggestions_shop_status_idx", "shop_id", "status"),
    )
