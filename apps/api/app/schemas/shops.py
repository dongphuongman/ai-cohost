from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# --- Requests ---


class CreateShopRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    industry: str | None = None
    team_size: str | None = None


class UpdateShopRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    industry: str | None = None
    team_size: str | None = None
    timezone: str | None = None
    settings: dict | None = None


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(pattern=r"^(admin|member)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(pattern=r"^(admin|member)$")


# --- Responses ---


class ShopResponse(BaseModel):
    id: int
    uuid: str
    name: str
    slug: str
    industry: str | None
    team_size: str | None
    owner_user_id: int
    plan: str
    plan_status: str
    trial_ends_at: datetime | None
    timezone: str
    settings: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ShopMemberResponse(BaseModel):
    id: int
    user_id: int
    email: str
    full_name: str | None
    avatar_url: str | None
    role: str
    status: str
    joined_at: datetime | None
