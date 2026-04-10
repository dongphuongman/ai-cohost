from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.database import get_db
from app.schemas.products import FaqCreate, FaqResponse, FaqUpdate
from app.services import faqs as faq_svc

router = APIRouter(prefix="/products/{product_id}/faqs", tags=["faqs"])


@router.get("/", response_model=list[FaqResponse])
async def list_faqs(
    product_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await faq_svc.list_faqs(db, shop.shop_id, product_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")
    return result


@router.post("/", response_model=FaqResponse, status_code=201)
async def create_faq(
    product_id: int,
    data: FaqCreate,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await faq_svc.create_faq(db, shop.shop_id, product_id, data)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")
    return result


@router.post("/bulk", response_model=list[FaqResponse], status_code=201)
async def create_faqs_bulk(
    product_id: int,
    data: list[FaqCreate],
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await faq_svc.create_faqs_bulk(db, shop.shop_id, product_id, data)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")
    return result


@router.patch("/{faq_id}", response_model=FaqResponse)
async def update_faq(
    product_id: int,
    faq_id: int,
    data: FaqUpdate,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await faq_svc.update_faq(db, shop.shop_id, faq_id, data)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ không tồn tại")
    return result


@router.delete("/{faq_id}", status_code=204)
async def delete_faq(
    product_id: int,
    faq_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    if not await faq_svc.delete_faq(db, shop.shop_id, faq_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ không tồn tại")
