from celery_app import app


@app.task(name="tasks.embed.embed_product")
def embed_product(product_id: int) -> dict:
    """Generate and store embedding for a product."""
    return {"status": "not_implemented", "product_id": product_id}


@app.task(name="tasks.embed.embed_faq")
def embed_faq(faq_id: int) -> dict:
    """Generate and store embedding for a product FAQ."""
    return {"status": "not_implemented", "faq_id": faq_id}
