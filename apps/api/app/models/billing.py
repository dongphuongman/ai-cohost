from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, Index, Integer, Numeric, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    plan: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_customer_id: Mapped[str | None] = mapped_column(Text)
    provider_subscription_id: Mapped[str | None] = mapped_column(Text)

    current_period_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, server_default="false")
    cancelled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    trial_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    trial_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(Text, server_default="USD")

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("subscriptions_shop_idx", "shop_id"),
        Index("subscriptions_provider_idx", "provider", "provider_subscription_id"),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    subscription_id: Mapped[int | None] = mapped_column(BigInteger)

    invoice_number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, server_default="USD")
    status: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str | None] = mapped_column(Text)
    provider_invoice_id: Mapped[str | None] = mapped_column(Text)

    pdf_url: Mapped[str | None] = mapped_column(Text)

    issued_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    due_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        Index("invoices_shop_idx", "shop_id", issued_at.desc()),
    )


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger)

    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[int | None] = mapped_column(BigInteger)

    quantity: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False)

    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))

    billing_period: Mapped[date] = mapped_column(Date, nullable=False)

    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("usage_logs_shop_period_idx", "shop_id", "billing_period", "resource_type"),
        Index("usage_logs_resource_idx", "resource_type", created_at.desc()),
    )
