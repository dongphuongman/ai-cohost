import logging
from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop, require_role
from app.core.config import settings
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

logger = logging.getLogger(__name__)

LEMONSQUEEZY_API = "https://api.lemonsqueezy.com/v1"

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


@router.post("/checkout")
async def create_checkout(
    plan: str = Query(..., pattern=r"^(starter|pro|enterprise)$"),
    shop: ShopContext = Depends(require_role("owner")),
):
    if not settings.lemonsqueezy_api_key or not settings.lemonsqueezy_store_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing chưa được cấu hình",
        )

    # Map plan to LemonSqueezy variant ID (configured per environment)
    plan_variant_map = {
        "starter": "starter",
        "pro": "pro",
        "enterprise": "enterprise",
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LEMONSQUEEZY_API}/checkouts",
                headers={
                    "Authorization": f"Bearer {settings.lemonsqueezy_api_key}",
                    "Content-Type": "application/vnd.api+json",
                    "Accept": "application/vnd.api+json",
                },
                json={
                    "data": {
                        "type": "checkouts",
                        "attributes": {
                            "custom_data": {"shop_id": str(shop.shop_id)},
                            "checkout_data": {
                                "custom": {"shop_id": str(shop.shop_id)},
                            },
                        },
                        "relationships": {
                            "store": {
                                "data": {"type": "stores", "id": settings.lemonsqueezy_store_id}
                            },
                            "variant": {
                                "data": {
                                    "type": "variants",
                                    "id": plan_variant_map[plan],
                                }
                            },
                        },
                    }
                },
                timeout=15.0,
            )
            if resp.status_code >= 400:
                logger.error("LemonSqueezy checkout error: %s", resp.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Không thể tạo checkout",
                )
            data = resp.json()
            checkout_url = data["data"]["attributes"]["url"]
            return {"checkout_url": checkout_url}
    except httpx.HTTPError as e:
        logger.error("LemonSqueezy API error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Không thể kết nối đến billing provider",
        )


@router.post("/portal")
async def billing_portal(
    shop: ShopContext = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Subscription.provider_customer_id).where(
            Subscription.shop_id == shop.shop_id,
            Subscription.provider == "lemonsqueezy",
        )
    )
    customer_id = result.scalar_one_or_none()
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chưa có subscription. Vui lòng đăng ký gói trước.",
        )

    # LemonSqueezy customer portal URL pattern
    portal_url = f"https://app.lemonsqueezy.com/my-orders"
    return {"portal_url": portal_url}
