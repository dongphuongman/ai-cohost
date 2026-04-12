from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import UsageLog
from app.models.tenant import Shop
from app.schemas.billing import PLAN_LIMITS

# Subscription states that entitle the shop to its paid plan's quota.
# Anything else (past_due, cancelled, unpaid, expired, paused, None) collapses
# the shop back to the trial plan until billing is resolved.
HEALTHY_PLAN_STATUSES = frozenset({"active", "trialing", "on_trial"})


def _effective_plan(plan: str | None, plan_status: str | None) -> str:
    """Return the plan whose limits should be enforced for a given (plan, plan_status).

    A paid plan only entitles the shop to paid quota while the subscription is
    in a healthy state. On past_due, cancelled, unpaid, expired, paused, or any
    unknown status, the shop falls back to trial limits — preventing silent
    revenue leak when a card declines but the shop keeps the plan name.
    """
    if plan_status not in HEALTHY_PLAN_STATUSES:
        return "trial"
    return plan if plan in PLAN_LIMITS else "trial"


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
    shop_result = await db.execute(
        select(Shop.plan, Shop.plan_status).where(Shop.id == shop_id)
    )
    plan, plan_status = shop_result.one()
    limits = PLAN_LIMITS[_effective_plan(plan, plan_status)]

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
    shop_result = await db.execute(
        select(Shop.plan, Shop.plan_status).where(Shop.id == shop_id)
    )
    plan, plan_status = shop_result.one()
    limits = PLAN_LIMITS[_effective_plan(plan, plan_status)]
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
