from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.database import get_db
from app.models.content import Persona
from app.schemas.products import PersonaCreate, PersonaResponse, PersonaUpdate
from app.schemas.voices import VoiceLinkRequest

router = APIRouter(prefix="/personas", tags=["personas"])


@router.get("/", response_model=list[PersonaResponse])
async def list_personas(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Persona)
        .where(Persona.shop_id == shop.shop_id)
        .order_by(Persona.is_default.desc(), Persona.created_at.asc())
    )
    return result.scalars().all()


@router.post("/", response_model=PersonaResponse, status_code=201)
async def create_persona(
    data: PersonaCreate,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    persona = Persona(
        shop_id=shop.shop_id,
        name=data.name,
        description=data.description,
        tone=data.tone,
        quirks=data.quirks,
        sample_phrases=data.sample_phrases,
    )
    db.add(persona)
    await db.commit()
    await db.refresh(persona)
    return persona


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id, Persona.shop_id == shop.shop_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona không tồn tại")
    return persona


@router.patch("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: int,
    data: PersonaUpdate,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id, Persona.shop_id == shop.shop_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona không tồn tại")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(persona, field, value)
    persona.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(persona)
    return persona


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id, Persona.shop_id == shop.shop_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona không tồn tại")
    if persona.is_preset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa persona preset",
        )

    await db.delete(persona)
    await db.commit()


@router.patch("/{persona_id}/default", response_model=PersonaResponse)
async def set_default_persona(
    persona_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    # Verify target exists
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id, Persona.shop_id == shop.shop_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona không tồn tại")

    # Atomic: unset all defaults and set new one in single UPDATE
    from sqlalchemy import update
    await db.execute(
        update(Persona)
        .where(Persona.shop_id == shop.shop_id)
        .values(is_default=Persona.id == persona_id)
    )

    await db.commit()
    await db.refresh(persona)
    return persona


@router.patch("/{persona_id}/voice", response_model=PersonaResponse)
async def link_voice_to_persona(
    persona_id: int,
    data: VoiceLinkRequest,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    """Link or unlink a voice clone to a persona."""
    from app.services.voices import link_voice_to_persona as do_link

    try:
        persona = await do_link(db, persona_id, shop.shop_id, data.voice_clone_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return persona
