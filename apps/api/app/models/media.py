from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Index, Integer, Numeric, Text, TIMESTAMP, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DhVideo(Base):
    __tablename__ = "dh_videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)

    script_id: Mapped[int | None] = mapped_column(BigInteger)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)

    avatar_preset: Mapped[str | None] = mapped_column(Text)
    avatar_custom_url: Mapped[str | None] = mapped_column(Text)
    voice_clone_id: Mapped[int | None] = mapped_column(BigInteger)
    background: Mapped[str | None] = mapped_column(Text)

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_job_id: Mapped[str | None] = mapped_column(Text)

    video_url: Mapped[str | None] = mapped_column(Text)
    video_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    has_watermark: Mapped[bool] = mapped_column(Boolean, server_default="true")

    status: Mapped[str] = mapped_column(Text, server_default="queued")
    error_message: Mapped[str | None] = mapped_column(Text)

    credits_used: Mapped[float | None] = mapped_column(Numeric(10, 4))

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        Index("dh_videos_shop_idx", "shop_id", created_at.desc()),
    )


class VoiceClone(Base):
    __tablename__ = "voice_clones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    source_audio_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_duration_seconds: Mapped[int | None] = mapped_column(Integer)

    consent_form_url: Mapped[str] = mapped_column(Text, nullable=False)
    consent_confirmed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    consent_confirmed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    consent_person_name: Mapped[str] = mapped_column(Text, nullable=False)

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_voice_id: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(Text, server_default="processing")

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    __table_args__ = (
        Index("voice_clones_shop_idx", "shop_id"),
    )
