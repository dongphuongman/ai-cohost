import re
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    get_token_expiry_seconds,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.models.tenant import Shop, ShopMember, User
from app.schemas.auth import (
    MeResponse,
    ShopMembershipResponse,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.services.email import send_otp_email, send_reset_password_email
from app.services.otp import generate_otp, store_otp, verify_otp


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


async def _get_user_shop_ids(db: AsyncSession, user_id: int) -> list[int]:
    result = await db.execute(
        select(ShopMember.shop_id).where(
            ShopMember.user_id == user_id,
            ShopMember.status == "active",
        )
    )
    return list(result.scalars().all())


async def _build_token_response(db: AsyncSession, user: User) -> TokenResponse:
    shop_ids = await _get_user_shop_ids(db, user.id)
    return TokenResponse(
        access_token=create_access_token(user.id, shop_ids),
        refresh_token=create_refresh_token(user.id),
        token_type="bearer",
        expires_in=get_token_expiry_seconds(),
    )


async def signup(db: AsyncSession, data: SignupRequest) -> dict:
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký",
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        email_verified=False,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký",
        )

    # Send OTP for email verification
    otp = generate_otp()
    await store_otp(user.id, otp)
    await send_otp_email(data.email, otp)

    await db.commit()

    return {"user_id": user.id, "message": "Vui lòng kiểm tra email để xác thực"}


async def login(db: AsyncSession, email: str, password: str) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return await _build_token_response(db, user)


async def refresh(db: AsyncSession, refresh_token: str) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token type không hợp lệ",
        )

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User không tồn tại",
        )

    return await _build_token_response(db, user)


async def get_me(db: AsyncSession, user_id: int) -> MeResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User không tồn tại")

    # Load shop memberships
    memberships_result = await db.execute(
        select(ShopMember, Shop)
        .join(Shop, Shop.id == ShopMember.shop_id)
        .where(ShopMember.user_id == user_id, ShopMember.status == "active")
    )
    shops = [
        ShopMembershipResponse(
            shop_id=shop.id,
            shop_uuid=shop.uuid,
            shop_name=shop.name,
            shop_slug=shop.slug,
            role=member.role,
            plan=shop.plan,
            plan_status=shop.plan_status,
        )
        for member, shop in memberships_result.all()
    ]

    return MeResponse(user=UserResponse.model_validate(user), shops=shops)


async def change_password(
    db: AsyncSession, user_id: int, current_password: str, new_password: str
) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if not verify_password(current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không đúng",
        )

    user.password_hash = hash_password(new_password)
    await db.commit()


async def update_profile(
    db: AsyncSession, user_id: int, full_name: str | None, phone: str | None, avatar_url: str | None
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if full_name is not None:
        user.full_name = full_name
    if phone is not None:
        user.phone = phone
    if avatar_url is not None:
        user.avatar_url = avatar_url
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


async def verify_email(db: AsyncSession, user_id: int, otp_code: str) -> TokenResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User không tồn tại")

    is_valid = await verify_otp(user_id, otp_code)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã OTP không đúng hoặc đã hết hạn",
        )

    user.email_verified = True
    user.updated_at = datetime.now(timezone.utc)

    # Auto-create a personal shop on first verification
    existing_membership = await db.execute(
        select(ShopMember).where(ShopMember.user_id == user.id)
    )
    if not existing_membership.scalar_one_or_none():
        slug = _slugify(user.full_name or user.email.split("@")[0]) + f"-{user.id}"
        shop = Shop(
            name=f"Shop của {user.full_name or 'Tôi'}",
            slug=slug,
            owner_user_id=user.id,
            plan="trial",
            plan_status="active",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
        )
        db.add(shop)
        await db.flush()

        membership = ShopMember(
            shop_id=shop.id,
            user_id=user.id,
            role="owner",
            joined_at=datetime.now(timezone.utc),
            status="active",
        )
        db.add(membership)

    await db.commit()

    return await _build_token_response(db, user)


async def resend_otp(db: AsyncSession, user_id: int) -> dict:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User không tồn tại")
    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được xác thực",
        )

    otp = generate_otp()
    await store_otp(user.id, otp)
    await send_otp_email(user.email, otp)
    return {"message": "Đã gửi lại mã OTP"}


async def forgot_password(db: AsyncSession, email: str) -> dict:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    # Always return success to prevent email enumeration
    if user and user.password_hash:
        token = create_reset_token(user.id)
        await send_reset_password_email(email, token)
    return {"message": "Nếu email tồn tại, chúng tôi đã gửi link đặt lại mật khẩu"}


async def reset_password(db: AsyncSession, token: str, new_password: str) -> dict:
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn",
        )

    if payload.get("type") != "reset":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token không hợp lệ",
        )

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User không tồn tại")

    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Mật khẩu đã được đặt lại thành công"}


async def google_oauth(db: AsyncSession, credential: str) -> TokenResponse:
    """Handle Google OAuth — verify ID token and login/register user."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}",
                timeout=10.0,
            )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google token không hợp lệ",
                )
            google_data = resp.json()
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể xác thực với Google",
        )

    email = google_data.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không lấy được email từ Google",
        )

    google_id = google_data.get("sub", "")
    full_name = google_data.get("name", "")
    avatar_url = google_data.get("picture", "")

    # Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if user:
        # Link OAuth if not already linked
        if not user.oauth_provider:
            user.oauth_provider = "google"
            user.oauth_id = google_id
        if not user.avatar_url and avatar_url:
            user.avatar_url = avatar_url
        user.email_verified = True
        user.last_login_at = now
        await db.commit()
    else:
        # Register new user via Google
        user = User(
            email=email,
            full_name=full_name,
            avatar_url=avatar_url,
            email_verified=True,
            oauth_provider="google",
            oauth_id=google_id,
            last_login_at=now,
        )
        db.add(user)
        await db.flush()

        slug = _slugify(full_name or email.split("@")[0]) + f"-{user.id}"
        shop = Shop(
            name=f"Shop của {full_name or 'Tôi'}",
            slug=slug,
            owner_user_id=user.id,
            plan="trial",
            plan_status="active",
            trial_ends_at=now + timedelta(days=14),
        )
        db.add(shop)
        await db.flush()

        membership = ShopMember(
            shop_id=shop.id,
            user_id=user.id,
            role="owner",
            joined_at=now,
            status="active",
        )
        db.add(membership)
        await db.commit()

    return await _build_token_response(db, user)
