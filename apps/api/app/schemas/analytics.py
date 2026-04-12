from datetime import datetime

from pydantic import BaseModel


# --- Overview ---


class RecentSession(BaseModel):
    id: int
    uuid: str
    platform: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    comments_count: int
    suggestions_count: int
    sent_count: int

    model_config = {"from_attributes": True}


class UsageMeterOut(BaseModel):
    resource_type: str
    used: float
    limit: int  # -1 = unlimited
    unit: str


class OverviewStats(BaseModel):
    live_hours: float
    comments_count: int
    used_rate: float  # percentage 0-100
    scripts_count: int
    recent_sessions: list[RecentSession]
    usage: list[UsageMeterOut]


# --- Session list ---


class SessionListItem(BaseModel):
    id: int
    uuid: str
    platform: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    comments_count: int
    suggestions_count: int
    sent_count: int
    dismissed_count: int
    avg_latency_ms: int | None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    items: list[SessionListItem]
    total: int
    page: int
    page_size: int


# --- Session detail ---


class SessionDetailResponse(BaseModel):
    id: int
    uuid: str
    platform: str
    platform_url: str | None
    persona_id: int | None
    active_product_ids: list[int] | None
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    comments_count: int
    suggestions_count: int
    sent_count: int
    pasted_not_sent_count: int
    read_count: int
    dismissed_count: int
    avg_latency_ms: int | None

    model_config = {"from_attributes": True}


# --- Chart data ---


class ChartPoint(BaseModel):
    minute: datetime
    comment_count: int


# --- Product mentions ---


class ProductMention(BaseModel):
    name: str
    mention_count: int


# --- Top questions ---


class TopQuestion(BaseModel):
    text: str
    intent: str | None


# --- Comments with suggestions ---


class CommentWithSuggestion(BaseModel):
    id: int
    external_user_name: str | None
    text: str
    received_at: datetime | None
    intent: str | None
    suggestion_text: str | None = None
    suggestion_status: str | None = None
    suggestion_latency_ms: int | None = None


# --- Comparison vs 30-day average ---


class SessionComparison(BaseModel):
    """% diff of this session vs the shop's last-30-day average.

    ``None`` for any field means there isn't enough history to compare
    (e.g. fewer than 5 prior ended sessions).
    """

    duration: float | None = None
    comments: float | None = None
    suggestions: float | None = None
    adoption: float | None = None
    sample_size: int = 0


# --- AI insights ---


class InsightItem(BaseModel):
    """A single insight card. ``action`` is optional for ``positives`` (wins
    don't always need a follow-up); ``improvements`` and ``suggestions`` should
    always have one.
    """

    title: str
    detail: str
    action: str | None = None


class SessionInsights(BaseModel):
    positives: list[InsightItem]
    improvements: list[InsightItem]
    suggestions: list[InsightItem]
    generated_at: datetime
    cached: bool = False
    warning: str | None = None
