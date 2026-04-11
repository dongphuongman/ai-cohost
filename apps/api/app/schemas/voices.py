from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class VoiceCloneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    consent_person_name: str = Field(min_length=2, max_length=200)
    consent_confirmed: bool = False

    @field_validator("consent_confirmed")
    @classmethod
    def must_confirm_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "Bạn phải xác nhận đã có sự đồng ý của người sở hữu giọng nói"
            )
        return v

    @field_validator("consent_person_name")
    @classmethod
    def strip_person_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Vui lòng nhập tên người sở hữu giọng nói")
        return v


class VoiceCloneResponse(BaseModel):
    id: int
    shop_id: int
    created_by: int
    name: str
    description: str | None
    source_audio_url: str
    source_duration_seconds: int | None
    consent_form_url: str
    consent_confirmed_at: datetime
    consent_confirmed_by: int
    consent_person_name: str
    provider: str
    provider_voice_id: str | None
    status: str
    created_at: datetime
    deleted_at: datetime | None

    model_config = {"from_attributes": True}


class VoiceTestRequest(BaseModel):
    text: str = Field(
        default="Xin chào! Đây là giọng nói test từ AI Co-host.",
        min_length=1,
        max_length=500,
    )


class VoiceLinkRequest(BaseModel):
    voice_clone_id: int | None = None
