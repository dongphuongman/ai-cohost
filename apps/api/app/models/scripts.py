from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Index, Integer, Numeric, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    product_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=False)
    persona_id: Mapped[int | None] = mapped_column(BigInteger)
    duration_target: Mapped[int | None] = mapped_column(Integer)
    tone: Mapped[str | None] = mapped_column(Text)
    special_notes: Mapped[str | None] = mapped_column(Text)

    word_count: Mapped[int | None] = mapped_column(Integer)
    estimated_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    cta_count: Mapped[int | None] = mapped_column(Integer)

    llm_model: Mapped[str | None] = mapped_column(Text)
    llm_provider: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    generation_cost: Mapped[float | None] = mapped_column(Numeric(10, 6))

    parent_script_id: Mapped[int | None] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(Integer, server_default="1")

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("scripts_shop_created_idx", "shop_id", created_at.desc()),
    )


class ScriptSample(Base):
    __tablename__ = "script_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    persona_style: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    quality_score: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))

    created_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("script_samples_category_style_idx", "category", "persona_style", quality_score.desc()),
    )
