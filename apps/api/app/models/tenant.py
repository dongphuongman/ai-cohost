from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Index, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[str] = mapped_column(
        UUID(as_uuid=False), server_default=text("uuid_generate_v4()"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    industry: Mapped[str | None] = mapped_column(Text)
    team_size: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    plan: Mapped[str] = mapped_column(Text, nullable=False, server_default="trial")
    plan_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    trial_ends_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    timezone: Mapped[str] = mapped_column(Text, server_default="Asia/Ho_Chi_Minh")
    settings: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("shops_owner_idx", "owner_user_id"),
        Index("shops_plan_idx", "plan", "plan_status"),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[str] = mapped_column(
        UUID(as_uuid=False), server_default=text("uuid_generate_v4()"), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, server_default="false")
    password_hash: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    oauth_provider: Mapped[str | None] = mapped_column(Text)
    oauth_id: Mapped[str | None] = mapped_column(Text)
    two_fa_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    last_login_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("users_email_idx", "email"),
        Index("users_oauth_idx", "oauth_provider", "oauth_id"),
    )


class ShopMember(Base):
    __tablename__ = "shop_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    invited_by: Mapped[int | None] = mapped_column(BigInteger)
    invited_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    joined_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="active")

    __table_args__ = (
        UniqueConstraint("shop_id", "user_id"),
        Index("shop_members_user_idx", "user_id"),
        Index("shop_members_shop_idx", "shop_id"),
    )
