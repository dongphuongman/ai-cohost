from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.service import change_password, get_me, login, refresh, signup, update_profile
from app.core.database import get_db
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup_endpoint(data: SignupRequest, db: AsyncSession = Depends(get_db)):
    return await signup(db, data)


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await login(db, data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_endpoint(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await refresh(db, data.refresh_token)


@router.post("/logout")
async def logout_endpoint(user: CurrentUser = Depends(get_current_user)):
    # Stateless JWT — client discards tokens. Server-side blocklist can be added via Redis later.
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
