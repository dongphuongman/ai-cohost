from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Integer, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ShopModerationRules(Base):
    __tablename__ = "shop_moderation_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Keyword filters
    blocked_keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    blocked_patterns: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))

    # User filters
    whitelisted_users: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    blacklisted_users: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))

    # Behavior settings
    auto_hide_spam: Mapped[bool] = mapped_column(Boolean, server_default="true")
    auto_hide_links: Mapped[bool] = mapped_column(Boolean, server_default="true")
    auto_flag_toxic: Mapped[bool] = mapped_column(Boolean, server_default="true")
    emoji_flood_threshold: Mapped[int] = mapped_column(Integer, server_default="6")
    min_comment_length: Mapped[int] = mapped_column(Integer, server_default="2")

    # LLM classification
    use_llm_classify: Mapped[bool] = mapped_column(Boolean, server_default="false")
    llm_classify_rate_limit: Mapped[int] = mapped_column(Integer, server_default="10")

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("shop_id"),
    )


class FlaggedComment(Base):
    """Comments flagged for manual review (toxic, uncertain, etc.)."""
    __tablename__ = "flagged_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")  # pending, approved, dismissed
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("comment_id"),
    )
