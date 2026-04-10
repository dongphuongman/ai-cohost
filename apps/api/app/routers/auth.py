from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.service import (
    change_password,
    forgot_password,
    get_me,
    google_oauth,
    login,
    refresh,
    resend_otp,
    reset_password,
    signup,
    update_profile,
    verify_email,
)
from app.core.database import get_db
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GoogleOAuthRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.rate_limit import rate_limit_by_ip, rate_limit_by_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201)
async def signup_endpoint(data: SignupRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await rate_limit_by_ip(request, "signup", max_requests=3, window_seconds=3600)
    return await signup(db, data)


@router.post("/verify-email", response_model=TokenResponse)
async def verify_email_endpoint(
    data: VerifyEmailRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    await rate_limit_by_ip(request, "verify_email", max_requests=5, window_seconds=600)
    await rate_limit_by_user(data.user_id, "verify_email", max_requests=5, window_seconds=600)
    return await verify_email(db, data.user_id, data.otp)


@router.post("/resend-otp")
async def resend_otp_endpoint(data: ResendOtpRequest, db: AsyncSession = Depends(get_db)):
    await rate_limit_by_user(data.user_id, "resend_otp", max_requests=3, window_seconds=600)
    return await resend_otp(db, data.user_id)


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(data: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await rate_limit_by_ip(request, "login", max_requests=5, window_seconds=60)
    return await login(db, data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_endpoint(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await refresh(db, data.refresh_token)


@router.post("/forgot-password")
async def forgot_password_endpoint(
    data: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    await rate_limit_by_ip(request, "forgot_password", max_requests=3, window_seconds=3600)
    return await forgot_password(db, data.email)


@router.post("/reset-password")
async def reset_password_endpoint(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    return await reset_password(db, data.token, data.new_password)


@router.post("/google", response_model=TokenResponse)
async def google_oauth_endpoint(data: GoogleOAuthRequest, db: AsyncSession = Depends(get_db)):
    return await google_oauth(db, data.credential)


@router.post("/logout")
async def logout_endpoint(user: CurrentUser = Depends(get_current_user)):
    return {"message": "Đăng xuất thành công"}


@router.get("/me", response_model=MeResponse)
async def me_endpoint(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_me(db, user.user_id)


@router.patch("/me", response_model=UserResponse)
async def update_profile_endpoint(
    data: UpdateProfileRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_profile(db, user.user_id, data.full_name, data.phone, data.avatar_url)


@router.post("/change-password", status_code=204)
async def change_password_endpoint(
    data: ChangePasswordRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await change_password(db, user.user_id, data.current_password, data.new_password)
