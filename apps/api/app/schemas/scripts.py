from datetime import datetime

from pydantic import BaseModel, Field


class ScriptConfig(BaseModel):
    product_ids: list[int] = Field(min_length=1, max_length=5)
    persona_id: int | None = None
    duration_target: int = Field(ge=5, le=30)
    tone: str = "thân thiện"
    special_notes: str | None = Field(None, max_length=2000)


class ScriptUpdate(BaseModel):
    content: str = Field(min_length=1)


class ScriptResponse(BaseModel):
    id: int
    shop_id: int
    title: str
    content: str
    product_ids: list[int]
    persona_id: int | None
    duration_target: int | None
    tone: str | None
    special_notes: str | None
    word_count: int | None
    estimated_duration_seconds: int | None
    cta_count: int | None
    llm_model: str | None
    version: int
    parent_script_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScriptListResponse(BaseModel):
    items: list[ScriptResponse]
    total: int
    page: int
    page_size: int


class GenerateResponse(BaseModel):
    job_id: str
    message: str = "Script đang được tạo..."
