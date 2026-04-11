import logging
from datetime import datetime, timezone

import google.generativeai as genai
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from celery_app import app
from config import settings

logger = logging.getLogger(__name__)

# Use sync engine for Celery tasks (Celery workers are sync)
_sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
    "postgresql+psycopg2", "postgresql+psycopg2"
)
_engine = create_engine(_sync_db_url)


def _get_embedding(content: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    genai.configure(api_key=settings.gemini_api_key)
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=content,
        task_type=task_type,
    )
    return result["embedding"]  # 768 dimensions


@app.task(name="tasks.embed.embed_product", max_retries=3, default_retry_delay=10, soft_time_limit=30)
def embed_product(product_id: int) -> dict:
    """Generate and store embedding for a product."""
    try:
        with Session(_engine) as session:
            row = session.execute(
                text("SELECT id, name, description, highlights FROM products WHERE id = :id"),
                {"id": product_id},
            ).mappings().first()

            if not row:
                return {"status": "not_found", "product_id": product_id}

            # Build embedding text
            parts = [row["name"] or ""]
            if row["description"]:
                parts.append(row["description"])
            highlights = row["highlights"]
            if highlights:
                parts.append(". ".join(highlights))

            embed_text = ". ".join(p for p in parts if p)
            if not embed_text.strip():
                return {"status": "empty_content", "product_id": product_id}

            embedding = _get_embedding(embed_text)

            # Store embedding
            session.execute(
                text(
                    "UPDATE products SET embedding = :emb, "
                    "embedding_model = :model, embedding_updated_at = :ts "
                    "WHERE id = :id"
                ),
                {
                    "emb": str(embedding),
                    "model": "gemini-text-embedding-004",
                    "ts": datetime.now(timezone.utc),
                    "id": product_id,
                },
            )
            session.commit()

        return {"status": "ok", "product_id": product_id, "dim": len(embedding)}

    except Exception as exc:
        logger.exception("embed_product failed for %s", product_id)
        # Mark as error by setting embedding_updated_at but leaving embedding NULL
        try:
            with Session(_engine) as session:
                session.execute(
                    text(
                        "UPDATE products SET embedding_updated_at = :ts WHERE id = :id"
                    ),
                    {"ts": datetime.now(timezone.utc), "id": product_id},
                )
                session.commit()
        except Exception:
            pass
        raise embed_product.retry(exc=exc)


@app.task(name="tasks.embed.embed_faq", max_retries=3, default_retry_delay=10, soft_time_limit=30)
def embed_faq(faq_id: int) -> dict:
    """Generate and store embedding for a product FAQ."""
    try:
        with Session(_engine) as session:
            row = session.execute(
                text("SELECT id, question FROM product_faqs WHERE id = :id"),
                {"id": faq_id},
            ).mappings().first()

            if not row:
                return {"status": "not_found", "faq_id": faq_id}

            question = row["question"]
            if not question or not question.strip():
                return {"status": "empty_content", "faq_id": faq_id}

            embedding = _get_embedding(question)

            session.execute(
                text(
                    "UPDATE product_faqs SET embedding = :emb, "
                    "embedding_model = :model, embedding_updated_at = :ts "
                    "WHERE id = :id"
                ),
                {
                    "emb": str(embedding),
                    "model": "gemini-text-embedding-004",
                    "ts": datetime.now(timezone.utc),
                    "id": faq_id,
                },
            )
            session.commit()

        return {"status": "ok", "faq_id": faq_id, "dim": len(embedding)}

    except Exception as exc:
        logger.exception("embed_faq failed for %s", faq_id)
        raise embed_faq.retry(exc=exc)
