from datetime import datetime

from pydantic import BaseModel, Field, field_validator


MAX_TEXT_LENGTH = 5000

AVATAR_PRESETS = [
    "anna_costume1_cameraA",
    "josh_lite3_20230714",
    "santa_costume1_cameraA",
    "default_avatar",
]

BACKGROUND_PRESETS = ["#FFFFFF", "#000000", "#1a73e8", "#0f9d58"]


class VideoGenerateRequest(BaseModel):
    script_id: int | None = None
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    avatar_preset: str = Field(default="default_avatar", max_length=200)
    voice_clone_id: int | None = None
    background: str = Field(default="#FFFFFF", max_length=200)
    # Premium quality flag — forces HeyGen ($0.40/min) over LiteAvatar.
    # Đợt 1 has no UI toggle. Regardless of UI, the service layer gates this
    # on plan tier: only `pro` and `enterprise` shops can set it to True.
    # Lower tiers get a validation error at generate_video() time.
    prefer_quality: bool = False

    @field_validator("text")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Nội dung video không được để trống")
        return v


class VideoResponse(BaseModel):
    id: int
    shop_id: int
    created_by: int
    script_id: int | None
    source_text: str
    avatar_preset: str | None
    avatar_custom_url: str | None
    voice_clone_id: int | None
    background: str | None
    provider: str
    provider_job_id: str | None
    prefer_quality: bool
    video_url: str | None
    video_duration_seconds: int | None
    file_size_bytes: int | None
    has_watermark: bool
    status: str
    error_message: str | None
    credits_used: float | None
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class VideoShareResponse(BaseModel):
    share_url: str
    expires_at: datetime
