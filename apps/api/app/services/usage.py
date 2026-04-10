from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import UsageLog
from app.models.tenant import Shop
from app.schemas.billing import PLAN_LIMITS


class QuotaStatus:
    def __init__(self, used: float, limit: int, remaining: float):
        self.used = used
        self.limit = limit
        self.remaining = remaining

    @property
    def exceeded(self) -> bool:
        return self.limit != -1 and self.remaining <= 0


async def track_usage(
    db: AsyncSession,
    shop_id: int,
    resource_type: str,
    quantity: float,
    unit: str,
    user_id: int | None = None,
    resource_id: int | None = None,
    cost_usd: float | None = None,
) -> UsageLog:
    log = UsageLog(
        shop_id=shop_id,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        quantity=quantity,
        unit=unit,
        cost_usd=cost_usd,
        billing_period=date.today().replace(day=1),
    )
    db.add(log)
    await db.flush()
    return log


async def check_quota(
    db: AsyncSession, shop_id: int, resource_type: str
) -> QuotaStatus:
    shop_result = await db.execute(select(Shop.plan).where(Shop.id == shop_id))
    plan = shop_result.scalar_one()
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["trial"])

    resource_limit_map = {
        "live_hours": "live_hours",
        "product": "products",
        "script": "scripts_per_month",
        "dh_video": "dh_videos",
        "voice_clone": "voice_clones",
    }
    limit_key = resource_limit_map.get(resource_type)
    limit = limits.get(limit_key, 0) if limit_key else 0

    if limit == -1:
        return QuotaStatus(used=0, limit=-1, remaining=float("inf"))

    billing_period = date.today().replace(day=1)
    result = await db.execute(
        select(func.coalesce(func.sum(UsageLog.quantity), 0)).where(
            UsageLog.shop_id == shop_id,
            UsageLog.resource_type == resource_type,
            UsageLog.billing_period == billing_period,
        )
    )
    used = float(result.scalar_one())
    return QuotaStatus(used=used, limit=limit, remaining=limit - used)


async def check_seat_limit(db: AsyncSession, shop_id: int) -> QuotaStatus:
    shop_result = await db.execute(select(Shop.plan).where(Shop.id == shop_id))
    plan = shop_result.scalar_one()
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["trial"])
    seat_limit = limits.get("team_seats", 1)

    from app.models.tenant import ShopMember

    result = await db.execute(
        select(func.count(ShopMember.id)).where(
            ShopMember.shop_id == shop_id,
            ShopMember.status.in_(["active", "pending"]),
        )
    )
    used = result.scalar_one()
    remaining = float("inf") if seat_limit == -1 else seat_limit - used
    return QuotaStatus(used=used, limit=seat_limit, remaining=remaining)
