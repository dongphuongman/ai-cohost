"""Analytics router — dashboard overview, session drill-down, exports."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.database import get_db
from app.schemas.analytics import (
    ChartPoint,
    CommentWithSuggestion,
    OverviewStats,
    ProductMention,
    SessionComparison,
    SessionDetailResponse,
    SessionInsights,
    SessionListResponse,
    TopQuestion,
    UsageMeterOut,
)
from app.services import analytics as svc
from app.services import session_insights as insights_svc

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=OverviewStats)
async def overview(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    return await svc.get_overview(db, shop.shop_id)


@router.get("/sessions", response_model=SessionListResponse)
async def session_list(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    platform: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
):
    return await svc.list_sessions(
        db,
        shop.shop_id,
        page=page,
        page_size=page_size,
        platform=platform,
        status_filter=status_filter,
    )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def session_detail(
    session_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    result = await svc.get_session_detail(db, shop.shop_id, session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session không tồn tại",
        )
    return result


@router.get("/sessions/{session_id}/chart", response_model=list[ChartPoint])
async def session_chart(
    session_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    # Verify session belongs to shop
    session = await svc.get_session_detail(db, shop.shop_id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session không tồn tại",
        )
    return await svc.get_session_chart(db, shop.shop_id, session_id)


@router.get("/sessions/{session_id}/products", response_model=list[ProductMention])
async def session_products(
    session_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    session = await svc.get_session_detail(db, shop.shop_id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session không tồn tại",
        )
    return await svc.get_session_products(db, shop.shop_id, session_id)


@router.get("/sessions/{session_id}/questions", response_model=list[TopQuestion])
async def session_questions(
    session_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    session = await svc.get_session_detail(db, shop.shop_id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session không tồn tại",
        )
    return await svc.get_session_top_questions(db, shop.shop_id, session_id)


@router.get(
    "/sessions/{session_id}/comments",
    response_model=list[CommentWithSuggestion],
)
async def session_comments(
    session_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    session = await svc.get_session_detail(db, shop.shop_id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session không tồn tại",
        )
    return await svc.get_session_comments(db, shop.shop_id, session_id, page=page, page_size=page_size)


@router.get("/sessions/{session_id}/export")
async def session_export(
    session_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    session = await svc.get_session_detail(db, shop.shop_id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session không tồn tại",
        )
    csv_content = await svc.export_session_csv(db, shop.shop_id, session_id)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=session_{session_id}.csv",
        },
    )


@router.get(
    "/sessions/{session_id}/comparison",
    response_model=SessionComparison,
)
async def session_comparison(
    session_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    session = await svc.get_session_detail(db, shop.shop_id, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session không tồn tại",
        )
    return await svc.get_session_comparison(db, shop.shop_id, session_id)


@router.get(
    "/sessions/{session_id}/insights",
    response_model=SessionInsights,
)
async def session_insights(
    session_id: int,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
    refresh: bool = Query(False),
):
    result = await insights_svc.generate_session_insights(
        db, shop.shop_id, session_id, force=refresh
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session không tồn tại",
        )
    return result


@router.get("/usage", response_model=list[UsageMeterOut])
async def usage_summary(
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
    period: date | None = None,
):
    return await svc.get_usage_summary(db, shop.shop_id, period)
