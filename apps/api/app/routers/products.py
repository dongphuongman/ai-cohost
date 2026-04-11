from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.database import get_db
from app.schemas.products import (
    AIFaqRequest,
    AIFaqResponse,
    AIHighlightRequest,
    AIHighlightResponse,
    FaqCreate,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    UrlExtractRequest,
    UrlExtractResponse,
)
from app.services import ai_generate, faqs as faq_svc, products as product_svc, url_extract

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    sort: str = "newest",
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    return await product_svc.list_products(
        db, shop.shop_id,
        page=page, page_size=page_size,
        search=search, status_filter=status_filter, sort=sort,
    )


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(
    data: ProductCreate,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await product_svc.create_product(db, shop.shop_id, data, shop.user_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Đã đạt giới hạn số lượng sản phẩm cho plan hiện tại. Vui lòng nâng cấp.",
        )
    return result


@router.post("/extract-url", response_model=UrlExtractResponse)
async def extract_url(
    data: UrlExtractRequest,
    shop: ShopContext = Depends(get_current_shop),
):
    return await url_extract.extract_from_url(data.url)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await product_svc.get_product(db, shop.shop_id, product_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")
    return result


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await product_svc.update_product(db, shop.shop_id, product_id, data)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")
    return result


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    if not await product_svc.delete_product(db, shop.shop_id, product_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")


@router.post("/{product_id}/reindex", status_code=202)
async def reindex_product(
    product_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    if not await product_svc.reindex_product(db, shop.shop_id, product_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")
    return {"message": "Đang re-index sản phẩm"}


@router.post("/{product_id}/ai/highlights", response_model=AIHighlightResponse)
async def ai_highlights(
    product_id: int,
    data: AIHighlightRequest = AIHighlightRequest(),
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    product = await product_svc.get_product(db, shop.shop_id, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")

    try:
        highlights = await ai_generate.generate_highlights(
            name=product.name,
            description=product.description,
            price=product.price,
            category=product.category,
            count=data.count,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("AI highlight generation failed for product %s", product_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Tạo nội dung AI thất bại, vui lòng thử lại",
        )
    return AIHighlightResponse(highlights=highlights)


@router.post("/{product_id}/ai/faqs", response_model=AIFaqResponse)
async def ai_faqs(
    product_id: int,
    data: AIFaqRequest = AIFaqRequest(),
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    product = await product_svc.get_product(db, shop.shop_id, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sản phẩm không tồn tại")

    try:
        faqs_raw = await ai_generate.generate_faqs(
            name=product.name,
            description=product.description,
            highlights=product.highlights,
            price=product.price,
            count=data.count,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("AI FAQ generation failed for product %s", product_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Tạo nội dung AI thất bại, vui lòng thử lại",
        )
    return AIFaqResponse(
        faqs=[FaqCreate(question=f["question"], answer=f["answer"], source="ai") for f in faqs_raw]
    )
