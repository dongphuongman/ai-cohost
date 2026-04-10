import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_expiry_seconds,
    hash_password,
    verify_password,
)
from app.models.tenant import Shop, ShopMember, User
from app.schemas.auth import (
    MeResponse,
    ShopMembershipResponse,
    SignupRequest,
    TokenResponse,
    UserResponse,
)


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


async def signup(db: AsyncSession, data: SignupRequest) -> TokenResponse:
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
    await db.flush()

    # Auto-create a personal shop
    slug = _slugify(data.full_name) + f"-{user.id}"
    shop = Shop(
        name=f"Shop của {data.full_name}",
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
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email đã được đăng ký",
        )

    return await _build_token_response(db, user)


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
