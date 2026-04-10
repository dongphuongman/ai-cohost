"""RAG retrieval service — pgvector CTE query for products + FAQs."""

import logging
from dataclasses import dataclass, field

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

RAG_CTE_QUERY = sa_text("""
WITH relevant_products AS (
    SELECT id, name, description, highlights, price, currency,
           1 - (embedding <=> :embedding::vector) AS similarity
    FROM products
    WHERE shop_id = :shop_id
      AND is_active = true
      AND id = ANY(:product_ids::bigint[])
      AND embedding IS NOT NULL
    ORDER BY embedding <=> :embedding::vector
    LIMIT 2
),
relevant_faqs AS (
    SELECT f.id, f.question, f.answer, f.product_id,
           1 - (f.embedding <=> :embedding::vector) AS similarity
    FROM product_faqs f
    WHERE f.shop_id = :shop_id
      AND f.product_id IN (SELECT id FROM relevant_products)
      AND f.embedding IS NOT NULL
    ORDER BY f.embedding <=> :embedding::vector
    LIMIT 3
)
SELECT
    (SELECT json_agg(row_to_json(p)) FROM relevant_products p) AS products,
    (SELECT json_agg(row_to_json(f)) FROM relevant_faqs f) AS faqs
""")


@dataclass
class RAGContext:
    products: list[dict] = field(default_factory=list)
    faqs: list[dict] = field(default_factory=list)


async def query_rag(
    db: AsyncSession,
    *,
    embedding: list[float],
    shop_id: int,
    product_ids: list[int],
) -> RAGContext:
    """Execute pgvector CTE query for top 2 products + top 3 FAQs."""
    if not product_ids:
        return RAGContext()

    result = await db.execute(
        RAG_CTE_QUERY,
        {
            "embedding": str(embedding),
            "shop_id": shop_id,
            "product_ids": product_ids,
        },
    )
    row = result.mappings().first()
    if not row:
        return RAGContext()

    return RAGContext(
        products=row["products"] or [],
        faqs=row["faqs"] or [],
    )
