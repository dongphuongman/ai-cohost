from celery_app import app


@app.task(name="tasks.llm.generate_suggestion")
def generate_suggestion(comment_id: int, session_id: int, shop_id: int) -> dict:
    """Generate AI suggestion for a live comment. Priority: high."""
    return {"status": "not_implemented", "comment_id": comment_id}


@app.task(name="tasks.llm.classify_intent")
def classify_intent(comment_id: int, text: str) -> dict:
    """Classify comment intent (question, complaint, praise, etc.)."""
    return {"status": "not_implemented", "comment_id": comment_id}
