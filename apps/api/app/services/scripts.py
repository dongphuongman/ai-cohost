"""Script CRUD and generation service."""

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scripts import Script
from app.schemas.scripts import ScriptConfig, ScriptResponse
from app.services.usage import check_quota, track_usage

logger = logging.getLogger(__name__)


def _count_ctas(content: str) -> int:
    """Count Call-to-Action phrases in script content."""
    cta_phrases = [
        "đặt hàng", "mua ngay", "inbox", "comment", "để lại",
        "link", "giỏ hàng", "add to cart", "nhấn", "bấm",
        "đừng bỏ lỡ", "nhanh tay", "số lượng có hạn", "chỉ còn",
        "giảm giá", "ưu đãi", "khuyến mãi", "flash sale",
        "free ship", "miễn phí vận chuyển",
    ]
    count = 0
    content_lower = content.lower()
    for phrase in cta_phrases:
        count += content_lower.count(phrase)
    return min(count, 20)


def _to_response(script: Script) -> ScriptResponse:
    return ScriptResponse(
        id=script.id,
        shop_id=script.shop_id,
        title=script.title,
        content=script.content,
        product_ids=script.product_ids or [],
        persona_id=script.persona_id,
        duration_target=script.duration_target,
        tone=script.tone,
        special_notes=script.special_notes,
        word_count=script.word_count,
        estimated_duration_seconds=script.estimated_duration_seconds,
        cta_count=script.cta_count,
        llm_model=script.llm_model,
        version=script.version,
        parent_script_id=script.parent_script_id,
        created_at=script.created_at,
        updated_at=script.updated_at,
    )


async def list_scripts(
    db: AsyncSession,
    shop_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    product_id: int | None = None,
    persona_id: int | None = None,
    tone: str | None = None,
    search: str | None = None,
) -> dict:
    base = select(Script).where(Script.shop_id == shop_id)

    if product_id is not None:
        base = base.where(Script.product_ids.any(product_id))
    if persona_id is not None:
        base = base.where(Script.persona_id == persona_id)
    if tone:
        base = base.where(Script.tone == tone)
    if search:
        escaped = search.replace("%", r"\%").replace("_", r"\_")
        base = base.where(Script.title.ilike(f"%{escaped}%"))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    base = base.order_by(Script.created_at.desc())
    base = base.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(base)
    scripts = result.scalars().all()

    return {
        "items": [_to_response(s) for s in scripts],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_script(
    db: AsyncSession, shop_id: int, script_id: int
) -> ScriptResponse | None:
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.shop_id == shop_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        return None
    return _to_response(script)


async def update_script(
    db: AsyncSession, shop_id: int, script_id: int, content: str
) -> ScriptResponse | None:
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.shop_id == shop_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        return None

    script.content = content
    script.word_count = len(content.split())
    script.estimated_duration_seconds = int(script.word_count / 150 * 60)
    script.cta_count = _count_ctas(content)
    script.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(script)
    return _to_response(script)


async def delete_script(db: AsyncSession, shop_id: int, script_id: int) -> bool:
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.shop_id == shop_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        return False
    await db.delete(script)
    await db.commit()
    return True


async def start_generation(
    db: AsyncSession,
    shop_id: int,
    user_id: int,
    config: ScriptConfig,
) -> str:
    """Validate inputs, check quota, and enqueue generation task. Returns job_id."""
    from app.models.content import Product
    from app.services.embed_client import enqueue_script_task

    # Validate product_ids belong to shop
    product_result = await db.execute(
        select(Product).where(
            Product.id.in_(config.product_ids),
            Product.shop_id == shop_id,
        )
    )
    products = product_result.scalars().all()
    if len(products) != len(config.product_ids):
        raise ValueError("Một số sản phẩm không tồn tại hoặc không thuộc shop của bạn")

    # Check quota
    quota = await check_quota(db, shop_id, "script")
    if quota.exceeded:
        raise PermissionError(
            "Bạn đã hết lượt tạo script trong tháng. Nâng cấp gói để tiếp tục."
        )

    # Build product data for the task
    product_data = []
    for p in products:
        product_data.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": float(p.price) if p.price is not None else None,
            "currency": p.currency,
            "highlights": p.highlights or [],
            "category": p.category,
        })

    # Get persona data
    persona_data = None
    if config.persona_id:
        from app.models.content import Persona

        persona_result = await db.execute(
            select(Persona).where(
                Persona.id == config.persona_id,
                Persona.shop_id == shop_id,
            )
        )
        persona = persona_result.scalar_one_or_none()
        if persona:
            persona_data = {
                "id": persona.id,
                "name": persona.name,
                "tone": persona.tone,
                "quirks": persona.quirks,
                "sample_phrases": persona.sample_phrases,
            }

    job_id = await enqueue_script_task(
        shop_id=shop_id,
        user_id=user_id,
        config=config.model_dump(),
        products=product_data,
        persona=persona_data,
    )
    return job_id


async def start_regeneration(
    db: AsyncSession,
    shop_id: int,
    user_id: int,
    script_id: int,
) -> tuple[str, int]:
    """Regenerate a script with same config. Returns (job_id, new_version)."""
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.shop_id == shop_id)
    )
    script = result.scalar_one_or_none()
    if not script:
        raise ValueError("Script không tồn tại")

    config = ScriptConfig(
        product_ids=script.product_ids,
        persona_id=script.persona_id,
        duration_target=script.duration_target or 10,
        tone=script.tone or "thân thiện",
        special_notes=script.special_notes,
    )

    job_id = await start_generation(db, shop_id, user_id, config)
    return job_id, script.version + 1
