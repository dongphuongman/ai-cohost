"""AI-powered session insights — analyze a finished livestream and produce
actionable Vietnamese commentary. Cached in Redis for 1 hour to avoid LLM
spam when the user re-opens the session detail page.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis
from google import genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.analytics import SessionInsights
from app.services import analytics as analytics_svc

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 60 * 60  # 1 hour
_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url)
    return _redis


def _cache_key(session_id: int) -> str:
    return f"session_insights:{session_id}"


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    return f"{minutes // 60}h {minutes % 60}m"


PROMPT_TEMPLATE = """Bạn là tư vấn viên chuyên nghiệp cho shop bán hàng livestream.
Phân tích dữ liệu phiên livestream dưới đây và đưa ra insights actionable bằng tiếng Việt tự nhiên.

DỮ LIỆU PHIÊN LIVE
- Platform: {platform}
- Thời lượng: {duration}
- Tổng bình luận: {comments_count}
- Gợi ý AI sinh ra: {suggestions_count}
- Gợi ý đã gửi: {sent_count}
- Tỷ lệ dùng gợi ý: {adoption_rate}%
- Latency trung bình: {avg_latency}

TOP CÂU HỎI TỪ KHÁCH (đã lọc bỏ comment của host/bot)
{top_questions}

SẢN PHẨM ĐƯỢC NHẮC NHIỀU NHẤT
{products}

YÊU CẦU
Trả về JSON đúng format dưới (KHÔNG có markdown, KHÔNG có text thừa):
{{
  "positives": ["...", "..."],
  "improvements": ["...", "..."],
  "suggestions": ["...", "..."]
}}

Quy tắc:
- positives: 2-4 điểm tốt
- improvements: 2-4 vấn đề cần cải thiện
- suggestions: 2-3 gợi ý cho lần live tiếp theo
- Mỗi item dưới 100 từ
- KHÔNG viết chung chung — phải reference cụ thể số liệu hoặc sản phẩm cụ thể trong dữ liệu
- Tone thân thiện, tự nhiên, dùng "anh/chị" với host
"""


def _format_top_questions(questions: list) -> str:
    if not questions:
        return "(không có câu hỏi nào được phân loại)"
    return "\n".join(f"- [{q.intent or 'khác'}] {q.text}" for q in questions[:5])


def _format_products(products: list) -> str:
    if not products:
        return "(không có sản phẩm nào được nhắc)"
    return "\n".join(f"- {p.name}: {p.mention_count} lần" for p in products[:8])


def _parse_insights_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


async def generate_session_insights(
    db: AsyncSession, shop_id: int, session_id: int, *, force: bool = False
) -> SessionInsights | None:
    """Generate or fetch cached insights for a session.

    Returns ``None`` if the session doesn't exist or doesn't belong to the shop.
    """
    cache_key = _cache_key(session_id)
    redis_client = _get_redis()

    if not force:
        cached = await redis_client.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                return SessionInsights(**data, cached=True)
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning("Stale insights cache for session %s", session_id)

    detail = await analytics_svc.get_session_detail(db, shop_id, session_id)
    if detail is None:
        return None

    top_questions = await analytics_svc.get_session_top_questions(db, shop_id, session_id)
    products = await analytics_svc.get_session_products(db, shop_id, session_id)

    adoption_rate = (
        round(detail.sent_count / detail.suggestions_count * 100, 1)
        if detail.suggestions_count > 0
        else 0
    )

    prompt = PROMPT_TEMPLATE.format(
        platform=detail.platform,
        duration=_format_duration(detail.duration_seconds),
        comments_count=detail.comments_count,
        suggestions_count=detail.suggestions_count,
        sent_count=detail.sent_count,
        adoption_rate=adoption_rate,
        avg_latency=f"{detail.avg_latency_ms}ms" if detail.avg_latency_ms else "N/A",
        top_questions=_format_top_questions(top_questions),
        products=_format_products(products),
    )

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        parsed = _parse_insights_json(response.text)
    except Exception:
        logger.exception("LLM insights generation failed for session %s", session_id)
        # Graceful fallback so the UI doesn't break entirely.
        return SessionInsights(
            positives=[],
            improvements=["Không thể phân tích phiên này. Thử làm mới sau."],
            suggestions=[],
            generated_at=datetime.now(timezone.utc),
            cached=False,
        )

    insights = SessionInsights(
        positives=[str(x) for x in parsed.get("positives", [])][:4],
        improvements=[str(x) for x in parsed.get("improvements", [])][:4],
        suggestions=[str(x) for x in parsed.get("suggestions", [])][:3],
        generated_at=datetime.now(timezone.utc),
        cached=False,
    )

    # Cache without the cached flag (it's set fresh on retrieval).
    payload = insights.model_dump(mode="json", exclude={"cached"})
    await redis_client.setex(cache_key, _CACHE_TTL_SECONDS, json.dumps(payload))

    return insights
