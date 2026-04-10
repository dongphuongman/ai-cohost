from celery_app import app


@app.task(name="tasks.script.generate_script")
def generate_script(
    shop_id: int,
    product_ids: list[int],
    persona_id: int,
    duration_target: int,
    tone: str,
    special_notes: str,
) -> dict:
    """Generate livestream script from products and persona."""
    return {"status": "not_implemented", "shop_id": shop_id}
