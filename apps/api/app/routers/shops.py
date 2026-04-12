import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, ShopContext, get_current_shop, get_current_user, require_role
from app.core.database import get_db
from app.models.tenant import Shop, ShopMember, User
from app.services.email import send_invite_email
from app.services.personas import create_preset_personas
from app.services.usage import check_seat_limit
from app.schemas.shops import (
    CreateShopRequest,
    InviteMemberRequest,
    ShopMemberResponse,
    ShopResponse,
    UpdateMemberRoleRequest,
    UpdateShopRequest,
)

router = APIRouter(prefix="/shops", tags=["shops"])


INDUSTRIES = [
    "Mỹ phẩm",
    "Thời trang",
    "Đồ gia dụng",
    "Thực phẩm chức năng",
    "Mẹ và bé",
    "Điện tử",
    "Khác",
]

PLATFORMS = ["TikTok Live", "Shopee Live", "Facebook Live", "YouTube Live"]

TEAM_SIZES = ["1 người", "2-5 người", "6-10 người", "Hơn 10 người"]


@router.get("/config/options")
async def get_shop_options():
    """Return selector options for onboarding and shop creation forms."""
    return {
        "industries": INDUSTRIES,
        "platforms": PLATFORMS,
        "team_sizes": TEAM_SIZES,
    }


def _slugify(name: str, suffix: int) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return f"{slug}-{suffix}"


@router.get("", response_model=list[ShopResponse])
async def list_shops(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all shops the current user belongs to."""
    result = await db.execute(
        select(Shop)
        .join(ShopMember, ShopMember.shop_id == Shop.id)
        .where(ShopMember.user_id == user.user_id, ShopMember.status == "active")
    )
    return result.scalars().all()


@router.post("", response_model=ShopResponse, status_code=201)
async def create_shop(
    data: CreateShopRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    shop = Shop(
        name=data.name,
        slug="",  # placeholder, set after flush
        industry=data.industry,
        team_size=data.team_size,
        owner_user_id=user.user_id,
        plan="trial",
        plan_status="active",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db.add(shop)
    await db.flush()

    shop.slug = _slugify(data.name, shop.id)

    membership = ShopMember(
        shop_id=shop.id,
        user_id=user.user_id,
        role="owner",
        joined_at=datetime.now(timezone.utc),
        status="active",
    )
    db.add(membership)

    # Create 4 preset personas for the new shop
    await create_preset_personas(db, shop.id)

    await db.commit()
    await db.refresh(shop)
    return shop


@router.get("/current", response_model=ShopResponse)
async def get_current_shop_endpoint(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    """Get current shop (resolved from X-Shop-Id header)."""
    result = await db.execute(select(Shop).where(Shop.id == shop.shop_id))
    return result.scalar_one()


@router.patch("/current", response_model=ShopResponse)
async def update_current_shop(
    data: UpdateShopRequest,
    shop: ShopContext = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Shop).where(Shop.id == shop.shop_id))
    shop_obj = result.scalar_one()

    if data.name is not None:
        shop_obj.name = data.name
    if data.industry is not None:
        shop_obj.industry = data.industry
    if data.team_size is not None:
        shop_obj.team_size = data.team_size
    if data.timezone is not None:
        shop_obj.timezone = data.timezone
    if data.settings is not None:
        shop_obj.settings = data.settings
    shop_obj.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(shop_obj)
    return shop_obj


# --- Team Management ---


@router.get("/current/members", response_model=list[ShopMemberResponse])
async def list_members(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShopMember, User)
        .join(User, User.id == ShopMember.user_id)
        .where(ShopMember.shop_id == shop.shop_id)
    )
    return [
        ShopMemberResponse(
            id=member.id,
            user_id=member.user_id,
            email=u.email,
            full_name=u.full_name,
            avatar_url=u.avatar_url,
            role=member.role,
            status=member.status,
            joined_at=member.joined_at,
        )
        for member, u in result.all()
    ]


@router.post("/current/members", response_model=ShopMemberResponse, status_code=201)
async def invite_member(
    data: InviteMemberRequest,
    shop: ShopContext = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    # Check seat limit
    quota = await check_seat_limit(db, shop.shop_id)
    if quota.exceeded:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Đã đạt giới hạn {quota.limit} thành viên cho plan hiện tại. Vui lòng nâng cấp.",
        )

    # Find user by email
    result = await db.execute(select(User).where(User.email == data.email))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email chưa đăng ký tài khoản",
        )

    # Check not already a member
    existing = await db.execute(
        select(ShopMember).where(
            ShopMember.shop_id == shop.shop_id,
            ShopMember.user_id == target_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Người dùng đã là thành viên của shop",
        )

    member = ShopMember(
        shop_id=shop.shop_id,
        user_id=target_user.id,
        role=data.role,
        invited_by=shop.user_id,
        joined_at=datetime.now(timezone.utc),
        status="active",
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    # Send invite notification email (best-effort, don't fail on email error)
    inviter = await db.get(User, shop.user_id)
    shop_row = await db.get(Shop, shop.shop_id)
    if inviter and shop_row:
        await send_invite_email(
            to=target_user.email,
            shop_name=shop_row.name,
            inviter_name=inviter.full_name or inviter.email,
        )

    return ShopMemberResponse(
        id=member.id,
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        avatar_url=target_user.avatar_url,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
    )


@router.patch("/current/members/{member_id}", response_model=ShopMemberResponse)
async def update_member_role(
    member_id: int,
    data: UpdateMemberRoleRequest,
    shop: ShopContext = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShopMember, User)
        .join(User, User.id == ShopMember.user_id)
        .where(ShopMember.id == member_id, ShopMember.shop_id == shop.shop_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member không tồn tại")

    member, u = row
    if member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể thay đổi role của owner",
        )

    member.role = data.role
    await db.commit()

    return ShopMemberResponse(
        id=member.id,
        user_id=u.id,
        email=u.email,
        full_name=u.full_name,
        avatar_url=u.avatar_url,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
    )


@router.delete("/current/members/{member_id}", status_code=204)
async def remove_member(
    member_id: int,
    shop: ShopContext = Depends(require_role("owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ShopMember).where(
            ShopMember.id == member_id,
            ShopMember.shop_id == shop.shop_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa owner khỏi shop",
        )

    await db.delete(member)
    await db.commit()
