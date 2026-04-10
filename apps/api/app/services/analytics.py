"""Analytics service — dashboard overview, session metrics, charts, exports."""

import csv
import io
from datetime import date, datetime, timezone

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import UsageLog
from app.models.session import Comment, LiveSession, Suggestion
from app.models.tenant import Shop
from app.schemas.analytics import (
    ChartPoint,
    CommentWithSuggestion,
    OverviewStats,
    ProductMention,
    RecentSession,
    SessionDetailResponse,
    SessionListItem,
    SessionListResponse,
    TopQuestion,
    UsageMeterOut,
)
from app.schemas.billing import PLAN_LIMITS


# --- Overview ---


async def get_overview(db: AsyncSession, shop_id: int) -> OverviewStats:
    billing_period = datetime.now(timezone.utc).date().replace(day=1)
    month_start = datetime(billing_period.year, billing_period.month, 1, tzinfo=timezone.utc)

    # Live hours this month
    hours_result = await db.execute(
        select(func.coalesce(func.sum(LiveSession.duration_seconds), 0))
        .where(
            LiveSession.shop_id == shop_id,
            LiveSession.started_at >= month_start,
        )
    )
    total_seconds = hours_result.scalar_one()
    live_hours = round(float(total_seconds) / 3600, 2)

    # Comments count this month (via session join)
    comments_result = await db.execute(
        select(func.count(Comment.id))
        .where(
            Comment.shop_id == shop_id,
            Comment.received_at >= month_start,
        )
    )
    comments_count = comments_result.scalar_one()

    # Used rate: sent suggestions / total suggestions * 100
    suggestion_counts = await db.execute(
        select(
            func.count(Suggestion.id),
            func.count(case((Suggestion.status == "sent", Suggestion.id))),
        )
        .where(
            Suggestion.shop_id == shop_id,
            Suggestion.created_at >= month_start,
        )
    )
    total_suggestions, sent_suggestions = suggestion_counts.one()
    used_rate = round((sent_suggestions / total_suggestions * 100) if total_suggestions > 0 else 0, 1)

    # Scripts count (from usage logs)
    scripts_result = await db.execute(
        select(func.coalesce(func.sum(UsageLog.quantity), 0))
        .where(
            UsageLog.shop_id == shop_id,
            UsageLog.resource_type == "script",
            UsageLog.billing_period == billing_period,
        )
    )
    scripts_count = int(scripts_result.scalar_one())

    # Recent sessions (last 5)
    recent_result = await db.execute(
        select(LiveSession)
        .where(LiveSession.shop_id == shop_id)
        .order_by(LiveSession.started_at.desc())
        .limit(5)
    )
    recent_sessions = [
        RecentSession.model_validate(s) for s in recent_result.scalars().all()
    ]

    # Usage meters
    usage = await _get_usage_meters(db, shop_id, billing_period)

    return OverviewStats(
        live_hours=live_hours,
        comments_count=comments_count,
        used_rate=used_rate,
        scripts_count=scripts_count,
        recent_sessions=recent_sessions,
        usage=usage,
    )


async def _get_usage_meters(
    db: AsyncSession, shop_id: int, billing_period: date
) -> list[UsageMeterOut]:
    shop_result = await db.execute(select(Shop.plan).where(Shop.id == shop_id))
    plan = shop_result.scalar_one_or_none() or "trial"
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["trial"])

    result = await db.execute(
        select(UsageLog.resource_type, UsageLog.unit, func.sum(UsageLog.quantity))
        .where(
            UsageLog.shop_id == shop_id,
            UsageLog.billing_period == billing_period,
        )
        .group_by(UsageLog.resource_type, UsageLog.unit)
    )

    resource_limit_map = {
        "live_hours": "live_hours",
        "product": "products",
        "script": "scripts_per_month",
        "dh_video": "dh_videos",
        "voice_clone": "voice_clones",
    }

    meters = []
    for resource_type, unit, total in result.all():
        limit_key = resource_limit_map.get(resource_type)
        meters.append(
            UsageMeterOut(
                resource_type=resource_type,
                used=float(total),
                limit=limits.get(limit_key, 0) if limit_key else 0,
                unit=unit,
            )
        )
    return meters


# --- Session list ---


async def list_sessions(
    db: AsyncSession,
    shop_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    platform: str | None = None,
    status_filter: str | None = None,
) -> SessionListResponse:
    base = select(LiveSession).where(LiveSession.shop_id == shop_id)

    if platform:
        base = base.where(LiveSession.platform == platform)
    if status_filter:
        base = base.where(LiveSession.status == status_filter)

    # Count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Paginate
    base = base.order_by(LiveSession.started_at.desc())
    base = base.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(base)

    items = [SessionListItem.model_validate(s) for s in result.scalars().all()]

    return SessionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# --- Session detail ---


async def get_session_detail(
    db: AsyncSession, shop_id: int, session_id: int
) -> SessionDetailResponse | None:
    result = await db.execute(
        select(LiveSession).where(
            LiveSession.id == session_id,
            LiveSession.shop_id == shop_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        return None
    return SessionDetailResponse.model_validate(session)


# --- Chart: comments per minute ---


async def get_session_chart(
    db: AsyncSession, shop_id: int, session_id: int
) -> list[ChartPoint]:
    result = await db.execute(
        select(
            func.date_trunc("minute", Comment.received_at).label("minute"),
            func.count(Comment.id).label("comment_count"),
        )
        .where(
            Comment.session_id == session_id,
            Comment.shop_id == shop_id,
        )
        .group_by(func.date_trunc("minute", Comment.received_at))
        .order_by(func.date_trunc("minute", Comment.received_at))
    )
    return [
        ChartPoint(minute=row.minute, comment_count=row.comment_count)
        for row in result.all()
    ]


# --- Product mentions ---


async def get_session_products(
    db: AsyncSession, shop_id: int, session_id: int
) -> list[ProductMention]:
    # Unnest rag_product_ids from suggestions, join to products for names
    result = await db.execute(
        text("""
            SELECT p.name, COUNT(*) AS mention_count
            FROM suggestions s
            CROSS JOIN LATERAL unnest(s.rag_product_ids) AS pid
            JOIN products p ON p.id = pid
            WHERE s.session_id = :session_id
              AND s.shop_id = :shop_id
              AND p.shop_id = :shop_id
              AND s.rag_product_ids IS NOT NULL
            GROUP BY p.name
            ORDER BY mention_count DESC
            LIMIT 20
        """),
        {"session_id": session_id, "shop_id": shop_id},
    )
    return [
        ProductMention(name=row.name, mention_count=row.mention_count)
        for row in result.all()
    ]


# --- Top questions ---


async def get_session_top_questions(
    db: AsyncSession, shop_id: int, session_id: int
) -> list[TopQuestion]:
    result = await db.execute(
        select(Comment.text_, Comment.intent)
        .where(
            Comment.session_id == session_id,
            Comment.shop_id == shop_id,
            Comment.intent.in_(["question", "pricing", "shipping", "complaint"]),
        )
        .order_by(Comment.received_at.desc())
        .limit(10)
    )
    return [
        TopQuestion(text=row.text_, intent=row.intent)
        for row in result.all()
    ]


# --- Comments with suggestions ---


async def get_session_comments(
    db: AsyncSession,
    shop_id: int,
    session_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
) -> list[CommentWithSuggestion]:
    result = await db.execute(
        text("""
            SELECT
                c.id,
                c.external_user_name,
                c.text,
                c.received_at,
                c.intent,
                s.text AS suggestion_text,
                s.status AS suggestion_status,
                s.latency_ms AS suggestion_latency_ms
            FROM comments c
            LEFT JOIN LATERAL (
                SELECT s2.text, s2.status, s2.latency_ms
                FROM suggestions s2
                WHERE s2.comment_id = c.id
                ORDER BY s2.created_at DESC
                LIMIT 1
            ) s ON true
            WHERE c.session_id = :session_id
              AND c.shop_id = :shop_id
            ORDER BY c.received_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "session_id": session_id,
            "shop_id": shop_id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        },
    )
    return [
        CommentWithSuggestion(
            id=row.id,
            external_user_name=row.external_user_name,
            text=row.text,
            received_at=row.received_at,
            intent=row.intent,
            suggestion_text=row.suggestion_text,
            suggestion_status=row.suggestion_status,
            suggestion_latency_ms=row.suggestion_latency_ms,
        )
        for row in result.all()
    ]


# --- CSV export ---


async def export_session_csv(db: AsyncSession, shop_id: int, session_id: int) -> str:
    result = await db.execute(
        text("""
            SELECT
                c.external_user_name,
                c.text AS comment_text,
                c.received_at,
                c.intent,
                s.text AS suggestion_text,
                s.status AS suggestion_status,
                s.latency_ms
            FROM comments c
            LEFT JOIN LATERAL (
                SELECT s2.text, s2.status, s2.latency_ms
                FROM suggestions s2
                WHERE s2.comment_id = c.id
                ORDER BY s2.created_at DESC
                LIMIT 1
            ) s ON true
            WHERE c.session_id = :session_id
              AND c.shop_id = :shop_id
            ORDER BY c.received_at ASC
            LIMIT 100000
        """),
        {"session_id": session_id, "shop_id": shop_id},
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Người bình luận",
        "Bình luận",
        "Thời gian",
        "Phân loại",
        "Gợi ý AI",
        "Trạng thái gợi ý",
        "Độ trễ (ms)",
    ])

    for row in result.all():
        writer.writerow([
            row.external_user_name or "",
            row.comment_text,
            row.received_at.strftime("%Y-%m-%d %H:%M:%S") if row.received_at else "",
            row.intent or "",
            row.suggestion_text or "",
            row.suggestion_status or "",
            row.latency_ms if row.latency_ms is not None else "",
        ])

    return output.getvalue()


# --- Monthly usage summary ---


async def get_usage_summary(
    db: AsyncSession, shop_id: int, period: date | None = None
) -> list[UsageMeterOut]:
    billing_period = (period or datetime.now(timezone.utc).date()).replace(day=1)
    return await _get_usage_meters(db, shop_id, billing_period)
