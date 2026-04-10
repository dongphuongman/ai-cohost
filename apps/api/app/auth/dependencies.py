from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.utils import decode_token
from app.core.database import get_db
from app.models.tenant import ShopMember

security = HTTPBearer()


class CurrentUser:
    """Authenticated user context extracted from JWT."""

    def __init__(self, user_id: int, shop_ids: list[int]):
        self.user_id = user_id
        self.shop_ids = shop_ids


class ShopContext:
    """Resolved shop context for a request — user + shop_id with role."""

    def __init__(self, user_id: int, shop_id: int, role: str):
        self.user_id = user_id
        self.shop_id = shop_id
        self.role = role


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    """Decode JWT and return authenticated user context."""
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token type không hợp lệ",
        )

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload không hợp lệ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    shop_ids = payload.get("shop_ids", [])
    return CurrentUser(user_id=user_id, shop_ids=shop_ids)


async def get_current_shop(
    current_user: CurrentUser = Depends(get_current_user),
    x_shop_id: int = Header(..., alias="X-Shop-Id"),
    db: AsyncSession = Depends(get_db),
) -> ShopContext:
    """Resolve shop context from X-Shop-Id header. Verifies membership and sets RLS."""
    if x_shop_id not in current_user.shop_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập shop này",
        )

    # Load role from DB for authorization checks
    result = await db.execute(
        select(ShopMember.role).where(
            ShopMember.shop_id == x_shop_id,
            ShopMember.user_id == current_user.user_id,
            ShopMember.status == "active",
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership không hợp lệ",
        )

    # Set PostgreSQL session variable for RLS
    await db.execute(text("SET LOCAL app.current_shop_id = :sid"), {"sid": x_shop_id})

    return ShopContext(user_id=current_user.user_id, shop_id=x_shop_id, role=role)


def require_role(*allowed_roles: str):
    """Dependency factory: require the current user to have one of the specified roles."""

    async def _check(shop: ShopContext = Depends(get_current_shop)) -> ShopContext:
        if shop.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Chức năng này yêu cầu role: {', '.join(allowed_roles)}",
            )
        return shop

    return _check
