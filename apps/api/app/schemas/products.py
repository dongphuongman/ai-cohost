from datetime import datetime

from pydantic import BaseModel, Field


# --- Product ---


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    price: float | None = Field(None, ge=0)
    currency: str = "VND"
    highlights: list[str] = Field(default_factory=list)
    images: list[dict] = Field(default_factory=list)
    external_url: str | None = None
    category: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    price: float | None = Field(None, ge=0)
    currency: str | None = None
    highlights: list[str] | None = None
    images: list[dict] | None = None
    external_url: str | None = None
    category: str | None = None
    is_active: bool | None = None


class ProductResponse(BaseModel):
    id: int
    shop_id: int
    name: str
    description: str | None
    price: float | None
    currency: str
    highlights: list[str]
    images: list[dict]
    external_url: str | None
    category: str | None
    is_active: bool
    embedding_status: str  # "ready" | "indexing" | "error"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int


# --- Product FAQ ---


class FaqCreate(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=2000)
    source: str = "manual"


class FaqUpdate(BaseModel):
    question: str | None = Field(None, min_length=1, max_length=1000)
    answer: str | None = Field(None, min_length=1, max_length=2000)


class FaqResponse(BaseModel):
    id: int
    product_id: int
    question: str
    answer: str
    source: str
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- AI Generation ---


class AIHighlightRequest(BaseModel):
    count: int = Field(6, ge=1, le=20)


class AIHighlightResponse(BaseModel):
    highlights: list[str]


class AIFaqRequest(BaseModel):
    count: int = Field(5, ge=1, le=20)


class AIFaqResponse(BaseModel):
    faqs: list[FaqCreate]


# --- URL Extraction ---


class UrlExtractRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class UrlExtractResponse(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = None
    currency: str = "VND"
    images: list[str] = Field(default_factory=list)
    category: str | None = None
    platform: str | None = None  # "shopee" | "tiktok" | "unknown"
    partial: bool = False  # True if extraction was incomplete


# --- Persona ---


class PersonaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    tone: str | None = None
    quirks: list[str] | None = None
    sample_phrases: list[str] | None = None


class PersonaUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    tone: str | None = None
    quirks: list[str] | None = None
    sample_phrases: list[str] | None = None


class PersonaResponse(BaseModel):
    id: int
    shop_id: int
    name: str
    description: str | None
    tone: str | None
    quirks: list[str] | None
    sample_phrases: list[str] | None
    is_default: bool
    is_preset: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
