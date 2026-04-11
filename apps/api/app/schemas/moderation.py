from pydantic import BaseModel, Field


class ModerationRulesResponse(BaseModel):
    blocked_keywords: list[str] = []
    blocked_patterns: list[str] = []
    whitelisted_users: list[str] = []
    blacklisted_users: list[str] = []
    auto_hide_spam: bool = True
    auto_hide_links: bool = True
    auto_flag_toxic: bool = True
    emoji_flood_threshold: int = 6
    min_comment_length: int = 2
    use_llm_classify: bool = False
    llm_classify_rate_limit: int = 10


class ModerationRulesUpdate(BaseModel):
    blocked_keywords: list[str] | None = None
    blocked_patterns: list[str] | None = None
    whitelisted_users: list[str] | None = None
    blacklisted_users: list[str] | None = None
    auto_hide_spam: bool | None = None
    auto_hide_links: bool | None = None
    auto_flag_toxic: bool | None = None
    emoji_flood_threshold: int | None = Field(None, ge=3, le=20)
    min_comment_length: int | None = Field(None, ge=1, le=10)
    use_llm_classify: bool | None = None
    llm_classify_rate_limit: int | None = Field(None, ge=1, le=60)


class FlaggedCommentResponse(BaseModel):
    id: int
    comment_id: int
    external_user_name: str | None = None
    text: str = ""
    reason: str | None = None
    status: str = "pending"
    created_at: str | None = None


class BulkActionRequest(BaseModel):
    comment_ids: list[int]
    action: str  # "approve" or "dismiss"
