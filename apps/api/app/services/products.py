from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Product, ProductFaq
from app.schemas.products import ProductCreate, ProductResponse, ProductUpdate
from app.services.usage import check_quota, track_usage


def _embedding_status(product: Product) -> str:
    if product.embedding is not None:
        return "ready"
    if product.embedding_updated_at is None and product.created_at:
        return "indexing"
    return "error"


def _to_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        shop_id=product.shop_id,
        name=product.name,
        description=product.description,
        price=float(product.price) if product.price is not None else None,
        currency=product.currency,
        highlights=product.highlights or [],
        images=product.images or [],
        external_url=product.external_url,
        category=product.category,
        is_active=product.is_active,
        embedding_status=_embedding_status(product),
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


async def list_products(
    db: AsyncSession,
    shop_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    status_filter: str | None = None,
    sort: str = "newest",
) -> dict:
    base = select(Product).where(Product.shop_id == shop_id)

    if search:
        escaped = search.replace("%", r"\%").replace("_", r"\_")
        base = base.where(Product.name.ilike(f"%{escaped}%"))

    if status_filter == "ready":
        base = base.where(Product.embedding.isnot(None))
    elif status_filter == "indexing":
        base = base.where(Product.embedding.is_(None), Product.embedding_updated_at.is_(None))
    elif status_filter == "error":
        base = base.where(Product.embedding.is_(None), Product.embedding_updated_at.isnot(None))

    # Count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Sort
    if sort == "oldest":
        base = base.order_by(Product.created_at.asc())
    elif sort == "name_asc":
        base = base.order_by(Product.name.asc())
    elif sort == "price_desc":
        base = base.order_by(Product.price.desc().nulls_last())
    else:  # newest
        base = base.order_by(Product.created_at.desc())

    # Paginate
    base = base.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(base)
    products = result.scalars().all()

    return {
        "items": [_to_response(p) for p in products],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_product(db: AsyncSession, shop_id: int, product_id: int) -> ProductResponse:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return None
    return _to_response(product)


async def create_product(
    db: AsyncSession, shop_id: int, data: ProductCreate, user_id: int
) -> ProductResponse:
    from app.services.embed_client import enqueue_product_embedding

    # Check quota
    quota = await check_quota(db, shop_id, "product")
    if quota.exceeded:
        return None  # caller raises 429

    product = Product(
        shop_id=shop_id,
        name=data.name,
        description=data.description,
        price=data.price,
        currency=data.currency,
        highlights=data.highlights,
        images=data.images,
        external_url=data.external_url,
        category=data.category,
    )
    db.add(product)
    await db.flush()

    # Track usage
    await track_usage(db, shop_id, "product", 1, "count", user_id=user_id, resource_id=product.id)

    await db.commit()
    await db.refresh(product)

    # Enqueue embedding generation (fire-and-forget)
    await enqueue_product_embedding(product.id)

    return _to_response(product)


async def update_product(
    db: AsyncSession, shop_id: int, product_id: int, data: ProductUpdate
) -> ProductResponse | None:
    from app.services.embed_client import enqueue_product_embedding

    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return None

    need_reindex = False
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field in ("name", "description", "highlights") and getattr(product, field) != value:
            need_reindex = True
        setattr(product, field, value)

    product.updated_at = datetime.now(timezone.utc)

    # Remove from RAG index when deactivated
    if "is_active" in update_data and not update_data["is_active"]:
        product.embedding = None
        product.embedding_updated_at = None
        need_reindex = False  # no point re-indexing a deactivated product

    if need_reindex:
        product.embedding = None
        product.embedding_updated_at = None

    await db.commit()
    await db.refresh(product)

    if need_reindex:
        await enqueue_product_embedding(product.id)

    return _to_response(product)


async def delete_product(db: AsyncSession, shop_id: int, product_id: int) -> bool:
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return False

    # Cascade delete FAQs
    await db.execute(delete(ProductFaq).where(ProductFaq.product_id == product_id))
    await db.delete(product)
    await db.commit()
    return True


async def reindex_product(db: AsyncSession, shop_id: int, product_id: int) -> bool:
    from app.services.embed_client import enqueue_product_embedding

    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.shop_id == shop_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        return False

    product.embedding = None
    product.embedding_updated_at = None
    product.updated_at = datetime.now(timezone.utc)
    await db.commit()

    await enqueue_product_embedding(product.id)
    return True
