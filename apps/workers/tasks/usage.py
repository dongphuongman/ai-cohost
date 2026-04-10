from celery_app import app


@app.task(name="tasks.usage.log_usage")
def log_usage(
    shop_id: int,
    resource_type: str,
    quantity: float,
    unit: str,
    cost_usd: float | None = None,
) -> dict:
    """Log usage event for billing and analytics."""
    return {"status": "not_implemented", "shop_id": shop_id}
