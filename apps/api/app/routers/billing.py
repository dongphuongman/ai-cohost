from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop, require_role
from app.core.database import get_db
from app.models.billing import Invoice, Subscription, UsageLog
from app.models.tenant import Shop
from app.schemas.billing import (
    PLAN_LIMITS,
    InvoiceResponse,
    PlanLimitsResponse,
    SubscriptionResponse,
    UsageMeter,
    UsageSummaryResponse,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/subscription", response_model=SubscriptionResponse | None)
async def get_subscription(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subscription)
        .where(Subscription.shop_id == shop.shop_id)
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):
    result = await db.execute(
        select(Invoice)
        .where(Invoice.shop_id == shop.shop_id)
        .order_by(Invoice.issued_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/usage", response_model=UsageSummaryResponse)
async def get_usage(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
    period: date | None = None,
):
    billing_period = period or date.today().replace(day=1)

    # Get current plan
    shop_result = await db.execute(select(Shop.plan).where(Shop.id == shop.shop_id))
    plan = shop_result.scalar_one()
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["trial"])

    # Aggregate usage for the period
    result = await db.execute(
        select(UsageLog.resource_type, UsageLog.unit, func.sum(UsageLog.quantity))
        .where(
            UsageLog.shop_id == shop.shop_id,
            UsageLog.billing_period == billing_period,
        )
        .group_by(UsageLog.resource_type, UsageLog.unit)
    )

    resource_limit_map = {
        "live_hours": "live_hours",
        "product": "products",
        "script": "scripts_per_month",
        "dh_video": "dh_videos",
        "voice_clone": "voice_clones",
    }

    meters = []
    for resource_type, unit, total in result.all():
        limit_key = resource_limit_map.get(resource_type)
        meters.append(
            UsageMeter(
                resource_type=resource_type,
                used=float(total),
                limit=limits.get(limit_key, 0) if limit_key else 0,
                unit=unit,
            )
        )

    return UsageSummaryResponse(billing_period=billing_period, meters=meters)


@router.get("/plans", response_model=list[PlanLimitsResponse])
async def list_plans():
    return [
        PlanLimitsResponse(plan=plan, limits=limits)
        for plan, limits in PLAN_LIMITS.items()
    ]


@router.post("/cancel", status_code=200)
async def cancel_subscription(
    shop: ShopContext = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subscription)
        .where(Subscription.shop_id == shop.shop_id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
        .limit(1)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy subscription đang hoạt động",
        )

    sub.cancel_at_period_end = True
    sub.cancelled_at = datetime.now(timezone.utc)
    sub.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Subscription sẽ hết hạn vào cuối kỳ thanh toán"}
