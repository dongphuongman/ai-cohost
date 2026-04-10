from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ShopContext, get_current_shop
from app.core.database import get_db
from app.services import sessions as session_svc

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/")
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    sessions = await session_svc.list_sessions(db, shop_id=shop.shop_id, limit=limit, offset=offset)
    return [
        {
            "id": s.id,
            "uuid": s.uuid,
            "platform": s.platform,
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "duration_seconds": s.duration_seconds,
            "comments_count": s.comments_count,
            "suggestions_count": s.suggestions_count,
            "sent_count": s.sent_count,
            "dismissed_count": s.dismissed_count,
        }
        for s in sessions
    ]


@router.get("/{session_uuid}")
async def get_session(
    session_uuid: str,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    session = await session_svc.get_session_by_uuid_and_shop(db, session_uuid, shop.shop_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session không tìm thấy")
    return {
        "id": session.id,
        "uuid": session.uuid,
        "platform": session.platform,
        "platform_url": session.platform_url,
        "persona_id": session.persona_id,
        "active_product_ids": session.active_product_ids,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "duration_seconds": session.duration_seconds,
        "comments_count": session.comments_count,
        "suggestions_count": session.suggestions_count,
        "sent_count": session.sent_count,
        "pasted_not_sent_count": session.pasted_not_sent_count,
        "read_count": session.read_count,
        "dismissed_count": session.dismissed_count,
        "avg_latency_ms": session.avg_latency_ms,
    }


@router.get("/{session_uuid}/comments")
async def list_session_comments(
    session_uuid: str,
    limit: int = 50,
    offset: int = 0,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    session = await session_svc.get_session_by_uuid_and_shop(db, session_uuid, shop.shop_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session không tìm thấy")

    comments = await session_svc.list_session_comments(db, session_id=session.id, limit=limit, offset=offset)
    return [
        {
            "id": c.id,
            "external_user_name": c.external_user_name,
            "text": c.text_,
            "received_at": c.received_at.isoformat() if c.received_at else None,
            "is_spam": c.is_spam,
            "is_processed": c.is_processed,
            "sentiment": c.sentiment,
            "intent": c.intent,
        }
        for c in comments
    ]


@router.get("/{session_uuid}/suggestions")
async def list_session_suggestions(
    session_uuid: str,
    limit: int = 50,
    offset: int = 0,
    shop: ShopContext = Depends(get_current_shop),
    db: AsyncSession = Depends(get_db),
):
    session = await session_svc.get_session_by_uuid_and_shop(db, session_uuid, shop.shop_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session không tìm thấy")

    suggestions = await session_svc.list_session_suggestions(db, session_id=session.id, limit=limit, offset=offset)
    return [
        {
            "id": s.id,
            "comment_id": s.comment_id,
            "text": s.text_,
            "edited_text": s.edited_text,
            "status": s.status,
            "action_at": s.action_at.isoformat() if s.action_at else None,
            "latency_ms": s.latency_ms,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in suggestions
    ]
