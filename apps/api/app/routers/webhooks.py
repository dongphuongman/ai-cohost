import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import async_session
from app.models.billing import Invoice, Subscription
from app.models.tenant import Shop

_redis = aioredis.from_url(settings.redis_url if hasattr(settings, 'redis_url') else "redis://localhost:6379/0")


async def _redis_check_event(event_id: str) -> bool:
    return await _redis.exists(f"webhook_event:{event_id}")


async def _redis_mark_event(event_id: str) -> None:
    await _redis.setex(f"webhook_event:{event_id}", 86400, "1")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify LemonSqueezy webhook HMAC-SHA256 signature."""
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


@router.post("/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Signature", "")

    if not settings.lemonsqueezy_webhook_secret:
        logger.warning("LemonSqueezy webhook secret not configured")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if not _verify_signature(payload, signature, settings.lemonsqueezy_webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    data = json.loads(payload)
    event_name = data.get("meta", {}).get("event_name", "")
    attrs = data.get("data", {}).get("attributes", {})

    # Idempotency: check event_id to avoid duplicate processing
    event_id = data.get("meta", {}).get("event_id", "")
    if event_id:
        already = await _redis_check_event(event_id)
        if already:
            logger.info("Duplicate event %s, skipping", event_id)
            return {"status": "ok", "duplicate": True}

    async with async_session() as db:
        if event_name in ("subscription_created", "subscription_updated"):
            await _handle_subscription(db, attrs)
        elif event_name == "subscription_cancelled":
            await _handle_subscription_cancelled(db, attrs)
        elif event_name == "subscription_payment_failed":
            await _handle_payment_failed(db, attrs)
        elif event_name in ("order_created", "order_refunded"):
            await _handle_invoice(db, event_name, attrs)
        else:
            logger.info("Unhandled LemonSqueezy event: %s", event_name)

    # Mark event as processed (24h TTL)
    if event_id:
        await _redis_mark_event(event_id)

    return {"status": "ok"}


async def _handle_subscription(db, attrs: dict) -> None:
    shop_id = int(attrs.get("custom_data", {}).get("shop_id", 0))
    if not shop_id:
        logger.warning("No shop_id in subscription webhook custom_data")
        return

    provider_sub_id = str(attrs.get("first_subscription_item", {}).get("subscription_id", ""))
    plan = attrs.get("variant_name", "starter").lower()
    ls_status = attrs.get("status", "active")

    # Map LemonSqueezy status to our status
    status_map = {
        "active": "active",
        "past_due": "past_due",
        "paused": "paused",
        "cancelled": "cancelled",
        "expired": "expired",
        "on_trial": "trialing",
    }
    mapped_status = status_map.get(ls_status, ls_status)

    result = await db.execute(
        select(Subscription).where(
            Subscription.shop_id == shop_id,
            Subscription.provider == "lemonsqueezy",
        )
    )
    sub = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if sub:
        sub.plan = plan
        sub.status = mapped_status
        sub.provider_subscription_id = provider_sub_id
        sub.current_period_start = _parse_dt(attrs.get("renews_at"))
        sub.current_period_end = _parse_dt(attrs.get("ends_at"))
        sub.updated_at = now
    else:
        sub = Subscription(
            shop_id=shop_id,
            plan=plan,
            status=mapped_status,
            provider="lemonsqueezy",
            provider_customer_id=str(attrs.get("customer_id", "")),
            provider_subscription_id=provider_sub_id,
            current_period_start=now,
            amount=float(attrs.get("first_subscription_item", {}).get("price", 0)) / 100,
            currency="USD",
        )
        db.add(sub)

    # Update shop plan
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    if shop:
        shop.plan = plan
        shop.plan_status = mapped_status
        shop.updated_at = now

    await db.commit()


async def _handle_subscription_cancelled(db, attrs: dict) -> None:
    shop_id = int(attrs.get("custom_data", {}).get("shop_id", 0))
    if not shop_id:
        return

    result = await db.execute(
        select(Subscription).where(
            Subscription.shop_id == shop_id,
            Subscription.provider == "lemonsqueezy",
        )
    )
    sub = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if sub:
        sub.status = "cancelled"
        sub.cancel_at_period_end = True
        sub.cancelled_at = now
        sub.updated_at = now

    # Also update shop plan_status
    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    if shop:
        shop.plan_status = "cancelled"
        shop.updated_at = now

    await db.commit()


async def _handle_payment_failed(db, attrs: dict) -> None:
    shop_id = int(attrs.get("custom_data", {}).get("shop_id", 0))
    if not shop_id:
        return

    result = await db.execute(
        select(Subscription).where(
            Subscription.shop_id == shop_id,
            Subscription.provider == "lemonsqueezy",
        )
    )
    sub = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if sub:
        sub.status = "past_due"
        sub.updated_at = now

    shop_result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = shop_result.scalar_one_or_none()
    if shop:
        shop.plan_status = "past_due"
        shop.updated_at = now

    await db.commit()
    logger.warning("Payment failed for shop %s", shop_id)


async def _handle_invoice(db, event_name: str, attrs: dict) -> None:
    shop_id = int(attrs.get("custom_data", {}).get("shop_id", 0))
    if not shop_id:
        return

    order_number = str(attrs.get("order_number", ""))
    invoice_status = "paid" if event_name == "order_created" else "refunded"

    # Check if invoice exists
    result = await db.execute(
        select(Invoice).where(Invoice.invoice_number == order_number)
    )
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing:
        existing.status = invoice_status
        if invoice_status == "paid":
            existing.paid_at = now
    else:
        invoice = Invoice(
            shop_id=shop_id,
            invoice_number=order_number,
            amount=float(attrs.get("total", 0)) / 100,
            currency=attrs.get("currency", "USD"),
            status=invoice_status,
            provider="lemonsqueezy",
            provider_invoice_id=str(attrs.get("id", "")),
            issued_at=now,
            paid_at=now if invoice_status == "paid" else None,
        )
        db.add(invoice)

    await db.commit()


def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
