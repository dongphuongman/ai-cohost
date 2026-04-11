from datetime import datetime

from pydantic import BaseModel, Field


class AutoReplyToggleRequest(BaseModel):
    enabled: bool
    threshold: float = Field(default=0.9, ge=0.5, le=1.0)


class AutoReplyDecision(BaseModel):
    allowed: bool
    reason: str


class AutoReplyLogEntry(BaseModel):
    session_id: int
    suggestion_id: int
    comment_id: int
    decision: str  # "auto_replied" | "auto_cancelled" | "blocked"
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}
