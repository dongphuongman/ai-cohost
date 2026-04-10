from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# --- Requests ---


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=200)
    phone: str | None = None
    avatar_url: str | None = None


class VerifyEmailRequest(BaseModel):
    user_id: int
    otp: str = Field(min_length=6, max_length=6)


class ResendOtpRequest(BaseModel):
    user_id: int


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class GoogleOAuthRequest(BaseModel):
    credential: str


# --- Responses ---


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    uuid: str
    email: str
    email_verified: bool
    full_name: str | None
    avatar_url: str | None
    phone: str | None
    two_fa_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ShopMembershipResponse(BaseModel):
    shop_id: int
    shop_uuid: str
    shop_name: str
    shop_slug: str
    role: str
    plan: str
    plan_status: str


class MeResponse(BaseModel):
    user: UserResponse
    shops: list[ShopMembershipResponse]
