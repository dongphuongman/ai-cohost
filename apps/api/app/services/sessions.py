from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Comment, LiveSession, Suggestion


async def start_session(
    db: AsyncSession,
    *,
    shop_id: int,
    user_id: int,
    platform: str,
    product_ids: list[int] | None = None,
    persona_id: int | None = None,
    platform_url: str | None = None,
) -> LiveSession:
    session = LiveSession(
        shop_id=shop_id,
        started_by=user_id,
        platform=platform,
        platform_url=platform_url,
        persona_id=persona_id,
        active_product_ids=product_ids,
        status="running",
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def end_session(db: AsyncSession, session_uuid: str, shop_id: int | None = None) -> LiveSession:
    filters = [LiveSession.uuid == session_uuid, LiveSession.status == "running"]
    if shop_id is not None:
        filters.append(LiveSession.shop_id == shop_id)
    result = await db.execute(select(LiveSession).where(*filters))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session không tìm thấy hoặc đã kết thúc",
        )

    now = datetime.now(timezone.utc)
    duration = int((now - session.started_at).total_seconds()) if session.started_at else 0

    session.ended_at = now
    session.duration_seconds = duration
    session.status = "ended"
    await db.flush()
    await db.refresh(session)
    return session


async def mark_session_interrupted(db: AsyncSession, session_uuid: str) -> None:
    await db.execute(
        update(LiveSession)
        .where(LiveSession.uuid == session_uuid, LiveSession.status == "running")
        .values(
            status="interrupted",
            ended_at=datetime.now(timezone.utc),
        )
    )


async def ingest_comment(
    db: AsyncSession,
    *,
    session_id: int,
    shop_id: int,
    external_user_name: str,
    text: str,
    external_user_id: str | None = None,
    intent: str | None = None,
    confidence: float | None = None,
    is_spam: bool = False,
    is_from_host: bool = False,
) -> Comment:
    comment = Comment(
        session_id=session_id,
        shop_id=shop_id,
        external_user_id=external_user_id,
        external_user_name=external_user_name,
        text_=text,
        intent=intent,
        confidence=confidence,
        is_spam=is_spam,
        is_from_host=is_from_host,
    )
    db.add(comment)
    await db.flush()

    # Increment session comments_count
    await db.execute(
        update(LiveSession)
        .where(LiveSession.id == session_id)
        .values(comments_count=LiveSession.comments_count + 1)
    )

    await db.refresh(comment)
    return comment


async def update_suggestion_action(
    db: AsyncSession,
    *,
    suggestion_id: int,
    shop_id: int,
    action: str,
    edited_text: str | None = None,
) -> Suggestion:
    result = await db.execute(
        select(Suggestion).where(Suggestion.id == suggestion_id, Suggestion.shop_id == shop_id)
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion không tìm thấy",
        )

    suggestion.status = action
    suggestion.action_at = datetime.now(timezone.utc)
    if edited_text is not None:
        suggestion.edited_text = edited_text
    await db.flush()

    # Update session action counts
    count_col = {
        "sent": LiveSession.sent_count,
        "auto_sent": LiveSession.sent_count,
        "pasted_not_sent": LiveSession.pasted_not_sent_count,
        "read": LiveSession.read_count,
        "dismissed": LiveSession.dismissed_count,
        "auto_cancelled": LiveSession.dismissed_count,
    }.get(action)

    if count_col is not None:
        await db.execute(
            update(LiveSession)
            .where(LiveSession.id == suggestion.session_id)
            .values({count_col.key: count_col + 1})
        )

    await db.refresh(suggestion)
    return suggestion


async def list_sessions(
    db: AsyncSession, *, shop_id: int, limit: int = 20, offset: int = 0
) -> list[LiveSession]:
    result = await db.execute(
        select(LiveSession)
        .where(LiveSession.shop_id == shop_id)
        .order_by(LiveSession.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_session(db: AsyncSession, session_uuid: str) -> LiveSession | None:
    result = await db.execute(
        select(LiveSession).where(LiveSession.uuid == session_uuid)
    )
    return result.scalar_one_or_none()


async def get_session_by_uuid_and_shop(
    db: AsyncSession, session_uuid: str, shop_id: int
) -> LiveSession | None:
    result = await db.execute(
        select(LiveSession).where(
            LiveSession.uuid == session_uuid,
            LiveSession.shop_id == shop_id,
        )
    )
    return result.scalar_one_or_none()


async def list_session_comments(
    db: AsyncSession, *, session_id: int, limit: int = 50, offset: int = 0
) -> list[Comment]:
    result = await db.execute(
        select(Comment)
        .where(Comment.session_id == session_id)
        .order_by(Comment.received_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_session_suggestions(
    db: AsyncSession, *, session_id: int, limit: int = 50, offset: int = 0
) -> list[Suggestion]:
    result = await db.execute(
        select(Suggestion)
        .where(Suggestion.session_id == session_id)
        .order_by(Suggestion.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
