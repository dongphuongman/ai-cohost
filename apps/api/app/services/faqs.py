from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Product, ProductFaq
from app.schemas.products import FaqCreate, FaqResponse, FaqUpdate
from app.services.embed_client import enqueue_faq_embedding


def _to_response(faq: ProductFaq) -> FaqResponse:
    return FaqResponse(
        id=faq.id,
        product_id=faq.product_id,
        question=faq.question,
        answer=faq.answer,
        source=faq.source,
        order_index=faq.order_index,
        created_at=faq.created_at,
        updated_at=faq.updated_at,
    )


async def _verify_product_ownership(
    db: AsyncSession, shop_id: int, product_id: int
) -> bool:
    result = await db.execute(
        select(Product.id).where(Product.id == product_id, Product.shop_id == shop_id)
    )
    return result.scalar_one_or_none() is not None


async def list_faqs(
    db: AsyncSession, shop_id: int, product_id: int
) -> list[FaqResponse]:
    if not await _verify_product_ownership(db, shop_id, product_id):
        return None

    result = await db.execute(
        select(ProductFaq)
        .where(ProductFaq.product_id == product_id, ProductFaq.shop_id == shop_id)
        .order_by(ProductFaq.order_index.asc(), ProductFaq.id.asc())
    )
    return [_to_response(f) for f in result.scalars().all()]


async def create_faq(
    db: AsyncSession, shop_id: int, product_id: int, data: FaqCreate
) -> FaqResponse | None:
    if not await _verify_product_ownership(db, shop_id, product_id):
        return None

    # Get next order_index
    result = await db.execute(
        select(func.coalesce(func.max(ProductFaq.order_index), -1)).where(
            ProductFaq.product_id == product_id
        )
    )
    next_index = result.scalar_one() + 1

    faq = ProductFaq(
        product_id=product_id,
        shop_id=shop_id,
        question=data.question,
        answer=data.answer,
        source=data.source,
        order_index=next_index,
    )
    db.add(faq)
    await db.commit()
    await db.refresh(faq)

    await enqueue_faq_embedding(faq.id)
    return _to_response(faq)


async def create_faqs_bulk(
    db: AsyncSession, shop_id: int, product_id: int, faqs: list[FaqCreate]
) -> list[FaqResponse]:
    """Create multiple FAQs at once (used by AI generation)."""
    if not await _verify_product_ownership(db, shop_id, product_id):
        return None

    result = await db.execute(
        select(func.coalesce(func.max(ProductFaq.order_index), -1)).where(
            ProductFaq.product_id == product_id
        )
    )
    next_index = result.scalar_one() + 1

    created = []
    for i, data in enumerate(faqs):
        faq = ProductFaq(
            product_id=product_id,
            shop_id=shop_id,
            question=data.question,
            answer=data.answer,
            source=data.source,
            order_index=next_index + i,
        )
        db.add(faq)
        created.append(faq)

    await db.commit()
    for faq in created:
        await db.refresh(faq)
        await enqueue_faq_embedding(faq.id)

    return [_to_response(f) for f in created]


async def update_faq(
    db: AsyncSession, shop_id: int, faq_id: int, data: FaqUpdate
) -> FaqResponse | None:
    result = await db.execute(
        select(ProductFaq).where(ProductFaq.id == faq_id, ProductFaq.shop_id == shop_id)
    )
    faq = result.scalar_one_or_none()
    if not faq:
        return None

    need_reindex = False
    if data.question is not None and data.question != faq.question:
        faq.question = data.question
        need_reindex = True
    if data.answer is not None:
        faq.answer = data.answer

    faq.updated_at = datetime.now(timezone.utc)

    if need_reindex:
        faq.embedding = None
        faq.embedding_updated_at = None

    await db.commit()
    await db.refresh(faq)

    if need_reindex:
        await enqueue_faq_embedding(faq.id)

    return _to_response(faq)


async def delete_faq(db: AsyncSession, shop_id: int, faq_id: int) -> bool:
    result = await db.execute(
        select(ProductFaq).where(ProductFaq.id == faq_id, ProductFaq.shop_id == shop_id)
    )
    faq = result.scalar_one_or_none()
    if not faq:
        return False

    await db.delete(faq)
    await db.commit()
    return True
