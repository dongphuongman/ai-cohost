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
    SessionComparison,
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


async def _compute_duration_seconds(
    db: AsyncSession, session: LiveSession
) -> int | None:
    """Calculate session duration in seconds with fallback chain.

    Priority:
        1. Stored ``duration_seconds`` (set by ``end_session``).
        2. ``ended_at - started_at`` (if both exist but stored value is null).
        3. ``last_comment.received_at - started_at`` (session not ended cleanly).
        4. ``None`` if there is no usable signal.
    """
    if session.duration_seconds:
        return session.duration_seconds

    if session.started_at and session.ended_at:
        return int((session.ended_at - session.started_at).total_seconds())

    if session.started_at:
        last = await db.execute(
            select(func.max(Comment.received_at)).where(
                Comment.session_id == session.id
            )
        )
        last_at = last.scalar_one_or_none()
        if last_at:
            seconds = int((last_at - session.started_at).total_seconds())
            return seconds if seconds > 0 else None

    return None


async def _compute_avg_latency_ms(
    db: AsyncSession, session_id: int
) -> int | None:
    """Aggregate average suggestion latency for a session.

    Stored ``LiveSession.avg_latency_ms`` is not currently maintained by the
    worker, so we compute on-the-fly from ``suggestions.latency_ms``.
    """
    result = await db.execute(
        select(func.avg(Suggestion.latency_ms)).where(
            Suggestion.session_id == session_id,
            Suggestion.latency_ms.isnot(None),
        )
    )
    avg = result.scalar_one_or_none()
    return int(avg) if avg is not None else None


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

    detail = SessionDetailResponse.model_validate(session)
    # Override with freshly computed values — stored columns can drift if the
    # session was interrupted or the worker never wrote latency back.
    detail.duration_seconds = await _compute_duration_seconds(db, session)
    if detail.avg_latency_ms is None:
        detail.avg_latency_ms = await _compute_avg_latency_ms(db, session_id)
    return detail


# --- Chart: comments per minute ---


async def get_session_chart(
    db: AsyncSession, shop_id: int, session_id: int
) -> list[ChartPoint]:
    # Use raw SQL: SQLAlchemy binds `'minute'` as a separate parameter each
    # time it's emitted, so func.date_trunc(...) in SELECT vs. GROUP BY
    # becomes `date_trunc($1, ...)` vs `date_trunc($4, ...)` — PostgreSQL
    # treats those as distinct expressions and raises a GROUP BY error.
    result = await db.execute(
        text("""
            SELECT date_trunc('minute', received_at) AS minute,
                   COUNT(id) AS comment_count
            FROM comments
            WHERE session_id = :session_id
              AND shop_id = :shop_id
            GROUP BY 1
            ORDER BY 1
        """),
        {"session_id": session_id, "shop_id": shop_id},
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
    """Top frequently-asked questions FROM VIEWERS ONLY.

    Filters out:
        - host/bot comments (``is_from_host = true``)
        - spam (``is_spam = true``)
        - very short noise (length <= 5)
    Groups by exact text + intent and orders by frequency.
    """
    result = await db.execute(
        text("""
            SELECT
                c.text  AS text,
                c.intent AS intent,
                COUNT(*) AS occurrences
            FROM comments c
            WHERE c.session_id = :session_id
              AND c.shop_id = :shop_id
              AND c.is_from_host = false
              AND c.is_spam = false
              AND c.intent IN ('question', 'pricing', 'shipping', 'complaint')
              AND length(c.text) > 5
            GROUP BY c.text, c.intent
            ORDER BY occurrences DESC, c.text
            LIMIT 10
        """),
        {"session_id": session_id, "shop_id": shop_id},
    )
    return [
        TopQuestion(text=row.text, intent=row.intent)
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


# --- Comparison vs 30-day average ---


_COMPARISON_MIN_SAMPLES = 5


async def get_session_comparison(
    db: AsyncSession,
    shop_id: int,
    session_id: int,
    *,
    detail: SessionDetailResponse | None = None,
) -> SessionComparison:
    """Compare a session against the shop's last-30-day average.

    Returns a per-metric percentage diff. If the shop has fewer than
    ``_COMPARISON_MIN_SAMPLES`` prior ended sessions in the window, all diffs
    are returned as ``None`` so the UI can hide noisy indicators.

    Callers that already have a ``SessionDetailResponse`` for this session
    (e.g. the insights service's ``_gather_context``) may pass it via the
    ``detail`` kwarg to avoid the extra ``get_session_detail`` roundtrip
    (1 main SELECT + 2 aggregate subqueries).
    """
    if detail is None:
        detail = await get_session_detail(db, shop_id, session_id)
    if detail is None:
        return SessionComparison()

    result = await db.execute(
        text("""
            SELECT
                COUNT(*) AS sample,
                AVG(COALESCE(
                    duration_seconds,
                    EXTRACT(EPOCH FROM (ended_at - started_at))::INT
                )) AS avg_duration,
                AVG(comments_count) AS avg_comments,
                AVG(suggestions_count) AS avg_suggestions,
                AVG(CASE
                    WHEN suggestions_count > 0
                    THEN sent_count::FLOAT / suggestions_count * 100
                    ELSE NULL
                END) AS avg_adoption
            FROM live_sessions
            WHERE shop_id = :shop_id
              AND id != :session_id
              AND ended_at IS NOT NULL
              AND ended_at > NOW() - INTERVAL '30 days'
        """),
        {"shop_id": shop_id, "session_id": session_id},
    )
    row = result.first()
    sample = int(row.sample or 0) if row else 0

    if sample < _COMPARISON_MIN_SAMPLES:
        return SessionComparison(sample_size=sample)

    def diff(current: float | int | None, baseline: float | None) -> float | None:
        if current is None or baseline is None or baseline == 0:
            return None
        return round((float(current) - float(baseline)) / float(baseline) * 100, 1)

    current_adoption = (
        (detail.sent_count / detail.suggestions_count * 100)
        if detail.suggestions_count > 0
        else None
    )

    return SessionComparison(
        duration=diff(detail.duration_seconds, row.avg_duration),
        comments=diff(detail.comments_count, row.avg_comments),
        suggestions=diff(detail.suggestions_count, row.avg_suggestions),
        adoption=diff(current_adoption, row.avg_adoption),
        sample_size=sample,
    )


# --- Insight context (rich data for LLM grounding) ---


async def get_uncovered_comments(
    db: AsyncSession, shop_id: int, session_id: int, limit: int = 10
) -> list[dict]:
    """Viewer comments that received NO suggestion — opportunities for the AI
    to cover next time. Filters spam, host messages, and very short noise.
    Groups by exact text so repeated identical asks bubble up.
    """
    result = await db.execute(
        text("""
            SELECT c.text, c.intent, COUNT(*) AS freq
            FROM comments c
            LEFT JOIN suggestions s ON s.comment_id = c.id
            WHERE c.session_id = :session_id
              AND c.shop_id = :shop_id
              AND c.is_from_host = false
              AND c.is_spam = false
              AND s.id IS NULL
              AND length(c.text) > 5
            GROUP BY c.text, c.intent
            ORDER BY freq DESC, c.text
            LIMIT :lim
        """),
        {"session_id": session_id, "shop_id": shop_id, "lim": limit},
    )
    return [
        {"text": r.text, "intent": r.intent, "freq": int(r.freq)}
        for r in result.all()
    ]


async def get_repeated_questions(
    db: AsyncSession, shop_id: int, session_id: int, limit: int = 10
) -> list[dict]:
    """Questions asked ≥2 times in the session. ``has_suggestion`` flags
    whether the AI replied to ANY occurrence — if False, this is a clear FAQ
    candidate.
    """
    result = await db.execute(
        text("""
            SELECT
                c.text,
                c.intent,
                COUNT(*) AS ask_count,
                BOOL_OR(s.id IS NOT NULL) AS has_suggestion
            FROM comments c
            LEFT JOIN suggestions s ON s.comment_id = c.id
            WHERE c.session_id = :session_id
              AND c.shop_id = :shop_id
              AND c.is_from_host = false
              AND c.is_spam = false
              AND length(c.text) > 8
            GROUP BY c.text, c.intent
            HAVING COUNT(*) >= 2
            ORDER BY ask_count DESC, c.text
            LIMIT :lim
        """),
        {"session_id": session_id, "shop_id": shop_id, "lim": limit},
    )
    return [
        {
            "text": r.text,
            "intent": r.intent,
            "ask_count": int(r.ask_count),
            "has_suggestion": bool(r.has_suggestion),
        }
        for r in result.all()
    ]


async def get_mentioned_products_with_gaps(
    db: AsyncSession, shop_id: int, session_id: int, limit: int = 5
) -> list[dict]:
    """Products linked to this session via the suggestion RAG ids, with data
    completeness flags so the LLM can recommend filling specific gaps.

    Joining via ``rag_product_ids`` (rather than fuzzy text matching against
    comments) keeps the signal high and avoids false matches.
    """
    result = await db.execute(
        text("""
            SELECT
                p.id,
                p.name,
                p.price,
                p.description,
                p.highlights,
                COUNT(*) AS mention_count,
                (SELECT COUNT(*) FROM product_faqs pf
                 WHERE pf.product_id = p.id AND pf.shop_id = :shop_id) AS faq_count,
                (p.price IS NOT NULL) AS has_price,
                (p.description IS NOT NULL AND length(p.description) > 20) AS has_description,
                (p.highlights IS NOT NULL AND array_length(p.highlights, 1) > 0) AS has_highlights
            FROM suggestions s
            CROSS JOIN LATERAL unnest(s.rag_product_ids) AS pid
            JOIN products p ON p.id = pid AND p.shop_id = :shop_id
            WHERE s.session_id = :session_id
              AND s.shop_id = :shop_id
              AND s.rag_product_ids IS NOT NULL
            GROUP BY p.id, p.name, p.price, p.description, p.highlights
            ORDER BY mention_count DESC
            LIMIT :lim
        """),
        {"session_id": session_id, "shop_id": shop_id, "lim": limit},
    )
    return [
        {
            "id": int(r.id),
            "name": r.name,
            "price": float(r.price) if r.price is not None else None,
            "mention_count": int(r.mention_count),
            "faq_count": int(r.faq_count),
            "has_price": bool(r.has_price),
            "has_description": bool(r.has_description),
            "has_highlights": bool(r.has_highlights),
        }
        for r in result.all()
    ]


async def get_engagement_drops(
    db: AsyncSession, shop_id: int, session_id: int
) -> list[dict]:
    """Detect minutes where comment volume dropped >60% from the previous
    minute. Useful for the LLM to point at exact moments engagement dipped.
    Returns at most 3 drops to keep the prompt focused.
    """
    result = await db.execute(
        text("""
            SELECT date_trunc('minute', received_at) AS minute,
                   COUNT(*) AS count
            FROM comments
            WHERE session_id = :session_id
              AND shop_id = :shop_id
              AND is_from_host = false
            GROUP BY 1
            ORDER BY 1
        """),
        {"session_id": session_id, "shop_id": shop_id},
    )
    timeline = [(r.minute, int(r.count)) for r in result.all()]

    drops: list[dict] = []
    for i in range(1, len(timeline)):
        prev_min, prev_n = timeline[i - 1]
        curr_min, curr_n = timeline[i]
        if prev_n >= 5 and curr_n < prev_n * 0.4:
            drops.append({
                "minute": curr_min,
                "before": prev_n,
                "after": curr_n,
            })
    drops.sort(key=lambda d: d["before"] - d["after"], reverse=True)
    return drops[:3]


# --- Monthly usage summary ---


async def get_usage_summary(
    db: AsyncSession, shop_id: int, period: date | None = None
) -> list[UsageMeterOut]:
    billing_period = (period or datetime.now(timezone.utc).date()).replace(day=1)
    return await _get_usage_meters(db, shop_id, billing_period)
