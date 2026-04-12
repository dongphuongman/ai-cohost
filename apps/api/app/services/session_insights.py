"""AI-powered session insights — analyze a finished livestream and produce
actionable Vietnamese commentary. Cached in Redis to avoid LLM spam when
the user re-opens the session detail page.

Quality bar: every insight must
1. reference a specific number, product name, or quoted question from
   the session (enforced post-hoc by ``_is_generic_insight``), AND
2. only recommend actions that exist in the dashboard UI for the shop's
   plan tier (enforced by ``allowed_actions`` registry + forbidden-phrase
   list ``_validate_against_hallucination``).

Both checks share the same retry loop — if either fails, we re-prompt
the LLM up to ``_MAX_RETRIES`` times, then filter the offending items.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from google import genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.tenant import Shop
from app.schemas.analytics import InsightItem, SessionInsights
from app.services import analytics as analytics_svc
from app.services.insights.allowed_actions import (
    format_allowed_actions_for_prompt,
    get_allowed_actions_for_shop,
)

logger = logging.getLogger(__name__)

# Cached but short — after fixing the hallucination bug we want stale
# prompts to roll over fast. 10 minutes is enough to absorb repeated
# views of the same session-detail page without serving day-old content
# from a now-corrected prompt template.
_CACHE_TTL_SECONDS = 10 * 60
_MAX_RETRIES = 2
_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url)
    return _redis


def _cache_key(shop_id: int, session_id: int) -> str:
    # Scope by shop_id to prevent cross-tenant cache leaks: the cache read
    # runs before the ownership check in _gather_context, so a key without
    # shop_id would let shop B fetch shop A's cached insights by guessing
    # an integer session id.
    return f"session_insights:{shop_id}:{session_id}"


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds}s"
    total_minutes = seconds // 60
    if total_minutes < 60:
        return f"{total_minutes}m {seconds % 60}s"
    hours = total_minutes // 60
    remaining_minutes = total_minutes % 60
    return f"{hours}h {remaining_minutes}m"


# ────────────────────────────────────────────────────────────────────────────
# Prompt
# ────────────────────────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """Bạn là AI tư vấn cho shop owner Việt Nam đang livestream bán hàng trên AI Co-host.

NHIỆM VỤ: Phân tích 1 session livestream và đưa ra insights ACTIONABLE.

QUY TẮC NGHIÊM NGẶT:

1. CHỈ recommend các actions có trong DANH SÁCH ACTIONS được cho phép dưới đây.
2. KHÔNG bao giờ recommend tính năng KHÔNG có trong danh sách. Nếu vấn đề
   không thể fix bằng action có sẵn, NÓI THẲNG "hiện chưa có cách fix trực
   tiếp trong AI Co-host" và đặt action = null thay vì bịa.
3. Mọi action phải reference đường dẫn chính xác từ danh sách (ví dụ:
   "Sản phẩm > [tên] > tab 'FAQ' > nút 'Thêm FAQ'").
4. KHÔNG generic. Mọi insight PHẢI reference số liệu cụ thể HOẶC tên sản
   phẩm / câu hỏi cụ thể từ data session.
5. Mọi action phải làm được trong 5 phút. Format "vấn đề → tại sao →
   bước 1, bước 2, bước 3".
6. Tiếng Việt tự nhiên, tone tư vấn viên thân thiện, không sách vở.

═══════════════════════════════════════════
DANH SÁCH ACTIONS ĐƯỢC PHÉP RECOMMEND
(đã filter theo gói '{shop_plan}' của shop)
═══════════════════════════════════════════

{allowed_actions}

═══════════════════════════════════════════
CÁC TÍNH NĂNG KHÔNG TỒN TẠI — TUYỆT ĐỐI KHÔNG RECOMMEND
═══════════════════════════════════════════

❌ "Vào cài đặt AI, thêm intent ..."        — KHÔNG có UI cho user thêm intent
❌ "Thêm câu mẫu / training example cho intent" — KHÔNG có UI training data
❌ "Soạn sẵn câu trả lời / template cho intent" — AI tự generate, không có template library
❌ "Tạo workflow / automation rule"          — KHÔNG có workflow builder
❌ "Tích hợp với Zalo / Messenger / CRM"     — chỉ có FB, TikTok, YouTube, Shopee livestream
❌ "Bật/tắt notification email/Slack"        — KHÔNG có notification settings
❌ "Schedule post / lên lịch đăng"           — KHÔNG có scheduler

QUAN TRỌNG: AI Co-host KHÔNG có khái niệm "intent settings" cho user
config. AI tự classify intent ở backend, user không thấy và không edit
được. Đừng nhắc tới "intent" trong action cho user.

═══════════════════════════════════════════
GỢI Ý CHỌN ACTION THEO VẤN ĐỀ
═══════════════════════════════════════════

(Tham khảo — pick action key tương ứng từ danh sách trên)

- Vấn đề: AI không trả lời được câu hỏi cụ thể về sản phẩm
  → add_product_faq_manual, add_product_faq_ai, edit_product_description

- Vấn đề: Sản phẩm thiếu giá / mô tả → AI fallback chung chung
  → edit_product_price, edit_product_description, add_product_highlight_manual

- Vấn đề: Cùng một câu hỏi lặp lại nhiều lần (≥3) chưa có FAQ
  → add_product_faq_manual (chính), add_product_faq_ai (nếu có Pro)

- Vấn đề: Sản phẩm được nhắc nhiều nhưng chưa có trong catalog
  → add_product

- Vấn đề: Spam quá nhiều / comment rác chiếm budget AI
  → add_blocked_keyword, adjust_emoji_threshold, toggle_spam_filter

- Vấn đề: Comment không rõ intent bị xếp nhầm
  → toggle_llm_classify (nếu có Enterprise)

- Vấn đề: Auto-reply gửi quá nhiều câu sai (hoặc bỏ qua quá nhiều câu đúng)
  → adjust_auto_reply_threshold, toggle_auto_reply

- Vấn đề: Persona / tone không phù hợp với khách hôm nay
  → select_persona_per_session (lần sau), edit_script

- Vấn đề: Cần nhân bản session tốt cho lần sau
  → create_script_from_session, create_script

- Vấn đề: Cần data offline để phân tích sâu / chia sẻ với team
  → export_session_csv

NẾU vấn đề KHÔNG khớp gợi ý nào ở trên, hãy đối chiếu thẳng với danh
sách actions. Nếu vẫn không có action phù hợp, đặt action = null và
nói rõ "Hiện chưa có cách fix trực tiếp trong AI Co-host".

═══════════════════════════════════════════
VÍ DỤ INSIGHT TỐT (model theo style này)
═══════════════════════════════════════════

✅ title: "8 khách hỏi giá combo cho LUVIBA LO46 nhưng sản phẩm thiếu data combo"
   detail: "Có 8 comments hỏi 'mua 2 cái có giảm không' cho Loa LUVIBA LO46. Sản phẩm này chưa có thông tin combo trong mô tả nên AI fallback chung chung."
   action: "Bước 1: Vào Sản phẩm > Loa LUVIBA LO46 > field 'Mô tả' > thêm dòng 'Mua 2 giảm 10%'. Bước 2: Tab 'FAQ' > nút 'Thêm FAQ' > câu hỏi 'Mua combo có giảm không?' + câu trả lời cụ thể. AI sẽ reply chính xác lần sau."

✅ title: "Máy tính FX799 nhắc 28 lần nhưng thiếu 3 FAQ thường gặp"
   detail: "Sản phẩm 'Máy tính Thiên Long Fx799VN' được nhắc 28 lần, chỉ có 1 FAQ. 3 câu lặp chưa có FAQ: 'Pin dùng được bao lâu?', 'Có tính tích phân không?', 'Bảo hành ở nước ngoài không?'."
   action: "Bước 1: Vào Sản phẩm > Máy tính Thiên Long Fx799VN > tab 'FAQ'. Bước 2: Nút 'Thêm FAQ' > thêm 3 câu trên với answer chi tiết."

✅ title: "Comments tụt 75% lúc chuyển sản phẩm phút 14:23"
   detail: "Phút 14:23 comments tụt từ 32 xuống 8, đúng lúc chuyển sang giới thiệu KEM VICTORY mà chưa có hook chốt sản phẩm trước."
   action: "Bước 1: Vào Kịch bản > tạo script mới. Bước 2: Trong textarea, thêm câu hook trước mỗi lần chuyển sản phẩm: 'Ai chốt LUVIBA LO46 giơ tay nha, mình chuẩn bị qua sản phẩm tiếp theo!'."

═══════════════════════════════════════════
VÍ DỤ INSIGHT TỆ (TUYỆT ĐỐI TRÁNH)
═══════════════════════════════════════════

❌ title: "Cài đặt intent greeting"
   action: "Vào cài đặt AI, thêm intent 'greeting' và soạn sẵn câu trả lời"
   → SAI: tính năng KHÔNG TỒN TẠI. AI Co-host không có intent settings cho user.

❌ title: "Tăng tương tác với khách"
   action: "Tập trung giới thiệu sản phẩm kỹ hơn"
   → SAI: generic, không reference data, không có action cụ thể.

❌ title: "Chuẩn bị FAQ cho session sau"
   action: "Hãy chuẩn bị câu trả lời cho các câu hỏi phổ biến"
   → SAI: không reference sản phẩm cụ thể nào, navigation thiếu.

═══════════════════════════════════════════
DỮ LIỆU SESSION
═══════════════════════════════════════════

Metrics tổng quan:
- Thời lượng: {duration}
- Tổng comments: {comments_count}{comparison_comments}
- Số gợi ý AI sinh ra: {suggestions_count}
- Đã gửi: {sent_count}
- Tỷ lệ dùng gợi ý: {adoption_rate}%{comparison_adoption}
- Latency trung bình: {avg_latency}

Top câu hỏi viewer (đã lọc spam/host):
{top_questions}

Comments KHÔNG có gợi ý AI (cơ hội cải thiện coverage):
{uncovered}

Câu hỏi LẶP nhiều lần (≥2 lần) — cơ hội thêm FAQ:
{repeated}

Sản phẩm được nhắc + trạng thái data:
{products}

Engagement drops (lúc nào comments tụt mạnh):
{drops}

YÊU CẦU OUTPUT:

JSON với 3 mảng. Mỗi item là object {{"title": str, "detail": str, "action": str | null}}.

{{
  "positives": [  // 1-3 điểm tốt cụ thể (action có thể null)
    {{"title": "...", "detail": "...", "action": null}}
  ],
  "improvements": [  // 1-3 vấn đề cụ thể, action BẮT BUỘC
    {{"title": "...", "detail": "...", "action": "Bước 1... Bước 2..."}}
  ],
  "suggestions": [  // 1-3 gợi ý cho session tiếp, action BẮT BUỘC
    {{"title": "...", "detail": "...", "action": "..."}}
  ]
}}

NẾU không có data đủ để đưa insight cụ thể, trả về mảng RỖNG cho phần đó. KHÔNG bịa generic content. Trả về JSON thuần, KHÔNG có markdown fence."""


_RETRY_SUFFIX_GENERIC = """

LƯU Ý LẦN RETRY: Lần trước bạn đã đưa insights generic. Lần này PHẢI quote
trực tiếp text comment hoặc tên sản phẩm trong "detail". Nếu data không đủ
specific, trả mảng RỖNG cho phần đó."""

_RETRY_SUFFIX_HALLUCINATION = """

LƯU Ý LẦN RETRY: Lần trước bạn recommend tính năng KHÔNG TỒN TẠI trong
AI Co-host. Cấm tuyệt đối nhắc tới: "intent settings", "thêm intent",
"câu mẫu cho intent", "soạn sẵn câu trả lời theo intent", "workflow",
"automation", "tích hợp Zalo/Messenger". Mọi action trong response
PHẢI lấy đường dẫn nguyên văn từ DANH SÁCH ACTIONS. Nếu vấn đề không
fix được bằng action có sẵn, đặt action = null và viết "Hiện chưa có
cách fix trực tiếp trong AI Co-host"."""


# ────────────────────────────────────────────────────────────────────────────
# Format helpers
# ────────────────────────────────────────────────────────────────────────────


def _format_top_questions(questions: list) -> str:
    if not questions:
        return "(không có)"
    return "\n".join(
        f"- \"{q.text[:120]}\" — intent: {q.intent or 'khác'}"
        for q in questions[:10]
    )


def _format_uncovered(uncovered: list[dict]) -> str:
    if not uncovered:
        return "(tất cả comments đều có gợi ý AI)"
    return "\n".join(
        f"- \"{c['text'][:120]}\" ({c['freq']} lần) — intent: {c['intent'] or 'khác'}"
        for c in uncovered
    )


def _format_repeated(repeated: list[dict]) -> str:
    if not repeated:
        return "(không có câu hỏi nào lặp ≥2 lần)"
    return "\n".join(
        f"- \"{r['text'][:120]}\" ({r['ask_count']} lần) — đã có gợi ý: {'có' if r['has_suggestion'] else 'KHÔNG'}"
        for r in repeated
    )


def _format_products(products: list[dict]) -> str:
    if not products:
        return "(không sản phẩm nào được nhắc)"
    lines = []
    for p in products:
        gaps: list[str] = []
        if not p["has_price"]:
            gaps.append("THIẾU GIÁ")
        if not p["has_description"]:
            gaps.append("THIẾU MÔ TẢ")
        if not p["has_highlights"]:
            gaps.append("THIẾU HIGHLIGHTS")
        if p["faq_count"] < 3:
            gaps.append(f"chỉ có {p['faq_count']} FAQ")
        gaps_text = f" [{', '.join(gaps)}]" if gaps else ""
        lines.append(f"- {p['name']}: nhắc {p['mention_count']} lần{gaps_text}")
    return "\n".join(lines)


def _format_drops(drops: list[dict]) -> str:
    if not drops:
        return "(không có drop đáng kể)"
    return "\n".join(
        f"- Phút {d['minute'].strftime('%H:%M')}: comments giảm từ {d['before']} xuống {d['after']}"
        for d in drops
    )


def _format_comparison(label: str, value: float | None) -> str:
    if value is None:
        return ""
    sign = "+" if value >= 0 else ""
    return f" (vs TB shop: {sign}{value}%)"


# ────────────────────────────────────────────────────────────────────────────
# Output validation
# ────────────────────────────────────────────────────────────────────────────


GENERIC_PHRASES = (
    "chuẩn bị câu trả lời",
    "tăng tương tác",
    "nâng cao chất lượng",
    "cải thiện chất lượng",
    "tăng cường",
    "phản hồi nhanh",
    "thu hút khách",
    "tạo điều kiện",
    "hỗ trợ tốt hơn",
    "kỹ hơn",
    "chi tiết hơn",
    "tập trung vào",
)

# Numbers, quoted strings (Vietnamese smart quotes too), or HH:MM timestamps
# all count as "specific". A bare digit isn't enough on its own — but combined
# with no generic phrases it's typically grounded.
_SPECIFIC_RE = re.compile(r"\d|[\"'“”‘’]|\d{1,2}:\d{2}")


def _is_generic_insight(item: InsightItem | dict) -> bool:
    """Detect generic/vague insights that don't reference specific data."""
    if isinstance(item, InsightItem):
        text = f"{item.title} {item.detail} {item.action or ''}"
    else:
        text = f"{item.get('title', '')} {item.get('detail', '')} {item.get('action') or ''}"
    text_lower = text.lower()

    generic_count = sum(1 for phrase in GENERIC_PHRASES if phrase in text_lower)
    has_specific = bool(_SPECIFIC_RE.search(text))

    # Two strikes and you're out — single soft phrase is OK if grounded.
    return generic_count >= 2 or (generic_count >= 1 and not has_specific)


# Phrases that signal the LLM is recommending a feature that does NOT exist
# in the dashboard. Sourced from real hallucination incidents + audit of
# missing features. When you REMOVE a UI feature, add its label here so
# cached prompts can't sneak it back.
FORBIDDEN_PHRASES: tuple[str, ...] = (
    # Intent management — there is no intent UI for users.
    "thêm intent",
    "tạo intent",
    "cài đặt intent",
    "intent setting",
    "intent settings",
    "thêm câu mẫu",
    "training example",
    "training data",
    # Reply templates — AI auto-generates, no template library.
    "soạn sẵn câu trả lời",
    "template trả lời",
    "câu trả lời mặc định",
    "preset reply",
    "reply template",
    # Workflow / automation — no workflow builder.
    "tạo workflow",
    "thiết lập automation",
    "thiết lập workflow",
    "kích hoạt rule",
    "trigger condition",
    "automation rule",
    # Integrations not available — only FB / TikTok / YouTube / Shopee live.
    "tích hợp với zalo",
    "tích hợp zalo",
    "kết nối messenger",
    "tích hợp messenger",
    "tích hợp crm",
    # Notification settings — none exist (no email/Slack/push UI at all).
    "notification",
    "thông báo qua email",
    "thông báo email",
    "thông báo slack",
    # Generic catch-all — there is no "AI settings" page.
    "cài đặt ai",
    "ai config",
    "ai settings",
)


def _validate_against_hallucination(
    item: InsightItem | dict,
) -> list[str]:
    """Return the list of forbidden phrases that appear in this item.

    Empty list ⇒ item is clean. Used both for retry triggering and for
    the post-retry filter pass.
    """
    if isinstance(item, InsightItem):
        text = f"{item.title} {item.detail} {item.action or ''}"
    else:
        text = f"{item.get('title', '')} {item.get('detail', '')} {item.get('action') or ''}"
    text_lower = text.lower()
    return [p for p in FORBIDDEN_PHRASES if p in text_lower]


def validate_insight_actions(
    insights: SessionInsights | dict,
) -> tuple[bool, list[dict]]:
    """Public validator — accepts a payload and returns (is_valid, violations).

    Each violation is ``{"section": str, "title": str, "phrase": str}``.
    Used by tests and by the retry loop.
    """
    if isinstance(insights, SessionInsights):
        sections = {
            "positives": insights.positives,
            "improvements": insights.improvements,
            "suggestions": insights.suggestions,
        }
    else:
        sections = {
            "positives": insights.get("positives", []) or [],
            "improvements": insights.get("improvements", []) or [],
            "suggestions": insights.get("suggestions", []) or [],
        }

    violations: list[dict] = []
    for section_name, items in sections.items():
        for item in items:
            for phrase in _validate_against_hallucination(item):
                title = item.title if isinstance(item, InsightItem) else item.get("title", "")
                violations.append({
                    "section": section_name,
                    "title": title[:80],
                    "phrase": phrase,
                })
    return len(violations) == 0, violations


def _parse_insights_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def _coerce_items(raw_items: Any, *, action_required: bool) -> list[InsightItem]:
    """Tolerant coercion: LLM may return strings (legacy), dicts, or mixed.

    Strings are wrapped as ``title=str, detail=""`` so they don't crash —
    these will then fail the generic-check and trigger a retry.
    """
    out: list[InsightItem] = []
    if not isinstance(raw_items, list):
        return out
    for raw in raw_items:
        if isinstance(raw, str):
            out.append(InsightItem(title=raw[:120], detail=raw, action=None))
        elif isinstance(raw, dict):
            title = str(raw.get("title", "")).strip()
            detail = str(raw.get("detail", "")).strip()
            action_raw = raw.get("action")
            action = str(action_raw).strip() if action_raw else None
            if not title and not detail:
                continue
            if action_required and not action:
                # Skip improvements/suggestions missing the required action.
                continue
            out.append(InsightItem(
                title=title or detail[:80],
                detail=detail or title,
                action=action,
            ))
    return out


# ────────────────────────────────────────────────────────────────────────────
# Context gathering
# ────────────────────────────────────────────────────────────────────────────


async def _resolve_shop_plan(db: AsyncSession, shop_id: int) -> str:
    """Look up the shop's plan column. Falls back to ``starter`` if missing."""
    row = await db.execute(select(Shop.plan).where(Shop.id == shop_id))
    plan = row.scalar_one_or_none()
    return (plan or "starter").lower()


async def _gather_context(
    db: AsyncSession, shop_id: int, session_id: int
) -> dict | None:
    # Ownership gate runs first — every later fetch is cheap-ish but we
    # must not reveal that the session exists to a foreign shop. This is
    # also the ownership check that the Redis cache key intentionally
    # does NOT cover (see _cache_key docstring), so it is load-bearing.
    detail = await analytics_svc.get_session_detail(db, shop_id, session_id)
    if detail is None:
        return None

    # Reads are sequential, NOT gathered. SQLAlchemy's AsyncSession is not
    # concurrency-safe — a single session holds one connection and one
    # transaction, so ``asyncio.gather`` on the same ``db`` raises
    # "another operation is in progress". Parallelising properly requires
    # a session factory and seven short-lived sessions, which is a bigger
    # refactor than this review wants to land. Tracked as follow-up.
    #
    # The one optimisation we DO keep is passing the already-fetched
    # ``detail`` into get_session_comparison so it skips the duplicate
    # get_session_detail call (kills 3 extra roundtrips per insight
    # request: main SELECT + _compute_duration_seconds +
    # _compute_avg_latency_ms).
    top_questions = await analytics_svc.get_session_top_questions(db, shop_id, session_id)
    uncovered = await analytics_svc.get_uncovered_comments(db, shop_id, session_id)
    repeated = await analytics_svc.get_repeated_questions(db, shop_id, session_id)
    products = await analytics_svc.get_mentioned_products_with_gaps(db, shop_id, session_id)
    drops = await analytics_svc.get_engagement_drops(db, shop_id, session_id)
    comparison = await analytics_svc.get_session_comparison(
        db, shop_id, session_id, detail=detail
    )
    shop_plan = await _resolve_shop_plan(db, shop_id)

    adoption_rate = (
        round(detail.sent_count / detail.suggestions_count * 100, 1)
        if detail.suggestions_count > 0
        else 0
    )

    # Allowed-actions list is rendered fresh per request so a plan upgrade
    # is reflected immediately on next insight refresh.
    allowed_actions_text = format_allowed_actions_for_prompt(shop_plan)

    return {
        "shop_plan": shop_plan,
        "allowed_actions": allowed_actions_text,
        "duration": _format_duration(detail.duration_seconds),
        "comments_count": detail.comments_count,
        "suggestions_count": detail.suggestions_count,
        "sent_count": detail.sent_count,
        "adoption_rate": adoption_rate,
        "avg_latency": f"{detail.avg_latency_ms}ms" if detail.avg_latency_ms else "N/A",
        "top_questions": _format_top_questions(top_questions),
        "uncovered": _format_uncovered(uncovered),
        "repeated": _format_repeated(repeated),
        "products": _format_products(products),
        "drops": _format_drops(drops),
        "comparison_comments": _format_comparison("comments", comparison.comments),
        "comparison_adoption": _format_comparison("adoption", comparison.adoption),
    }


# ────────────────────────────────────────────────────────────────────────────
# Main entry
# ────────────────────────────────────────────────────────────────────────────


async def generate_session_insights(
    db: AsyncSession, shop_id: int, session_id: int, *, force: bool = False
) -> SessionInsights | None:
    """Generate or fetch cached insights for a session.

    Returns ``None`` if the session doesn't exist or doesn't belong to the shop.
    """
    cache_key = _cache_key(shop_id, session_id)
    redis_client = _get_redis()

    if not force:
        cached = await redis_client.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                return SessionInsights(**data, cached=True)
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning("Stale insights cache for session %s", session_id)

    context = await _gather_context(db, shop_id, session_id)
    if context is None:
        return None

    base_prompt = PROMPT_TEMPLATE.format(**context)

    insights: SessionInsights | None = None
    warning: str | None = None

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
    except Exception:
        logger.exception("Failed to init Gemini client for session %s", session_id)
        return SessionInsights(
            positives=[],
            improvements=[InsightItem(
                title="Không thể phân tích phiên này",
                detail="LLM provider chưa sẵn sàng. Thử làm mới sau.",
                action=None,
            )],
            suggestions=[],
            generated_at=datetime.now(timezone.utc),
            cached=False,
        )

    last_violations: list[dict] = []

    for attempt in range(_MAX_RETRIES + 1):
        # Build retry instructions: if last attempt hallucinated, prioritise
        # the hallucination warning; otherwise nudge against generics.
        suffix = ""
        if attempt > 0:
            if last_violations:
                suffix = _RETRY_SUFFIX_HALLUCINATION
            else:
                suffix = _RETRY_SUFFIX_GENERIC
        prompt = base_prompt + suffix

        try:
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            parsed = _parse_insights_json(response.text)
        except Exception:
            logger.exception(
                "LLM insights generation failed for session %s (attempt %d)",
                session_id, attempt + 1,
            )
            continue

        positives = _coerce_items(parsed.get("positives", []), action_required=False)[:3]
        improvements = _coerce_items(parsed.get("improvements", []), action_required=True)[:3]
        suggestions = _coerce_items(parsed.get("suggestions", []), action_required=True)[:3]

        all_items = positives + improvements + suggestions
        generic_count = sum(1 for it in all_items if _is_generic_insight(it))

        # Detect hallucinations item-by-item so we can filter precisely on the
        # final attempt instead of dropping the whole payload.
        #
        # We previously keyed hallucinated items by ``id(it)``. Python only
        # guarantees ``id()`` uniqueness for the lifetime of the object — if an
        # item were GC'd its address could be reused, producing a false-positive
        # match. Items here are actually held alive for the whole block, but
        # ``is``-identity via a parallel list is strictly correct and costs
        # nothing at these sizes (≤9 items).
        hallucinated_items: list[InsightItem] = []
        last_violations = []
        for it in all_items:
            phrases = _validate_against_hallucination(it)
            if phrases:
                hallucinated_items.append(it)
                last_violations.append(
                    {"title": it.title[:80], "phrases": phrases}
                )

        def _not_hallucinated(item: InsightItem) -> bool:
            return not any(h is item for h in hallucinated_items)

        ok_generic = generic_count <= 1
        ok_hallucination = not hallucinated_items
        is_last_attempt = attempt == _MAX_RETRIES

        if (ok_generic and ok_hallucination) or is_last_attempt:
            warnings: list[str] = []

            if hallucinated_items:
                # Filter out items that recommend non-existent features. Better
                # to show fewer cards than to lie about the product surface.
                positives = [it for it in positives if _not_hallucinated(it)]
                improvements = [it for it in improvements if _not_hallucinated(it)]
                suggestions = [it for it in suggestions if _not_hallucinated(it)]
                warnings.append(
                    f"Đã ẩn {len(hallucinated_items)} gợi ý nhắc tới tính năng không có thật."
                )
                logger.warning(
                    "[insights] session=%s: filtered %d hallucinated items after %d retries: %s",
                    session_id, len(hallucinated_items), attempt, last_violations,
                )

            if generic_count > 1:
                warnings.append("Một số insights có thể chung chung do data session ít.")
                logger.warning(
                    "[insights] session=%s: %d generic items remain after %d retries",
                    session_id, generic_count, attempt,
                )

            insights = SessionInsights(
                positives=positives,
                improvements=improvements,
                suggestions=suggestions,
                generated_at=datetime.now(timezone.utc),
                cached=False,
                warning=" ".join(warnings) or None,
            )
            break

        logger.info(
            "[insights] session=%s attempt %d retrying — generic=%d hallucinated=%d",
            session_id, attempt + 1, generic_count, len(hallucinated_items),
        )

    if insights is None:
        # All attempts crashed.
        return SessionInsights(
            positives=[],
            improvements=[InsightItem(
                title="Không thể phân tích phiên này",
                detail="LLM trả về lỗi sau nhiều lần thử. Thử lại sau.",
                action=None,
            )],
            suggestions=[],
            generated_at=datetime.now(timezone.utc),
            cached=False,
        )

    payload = insights.model_dump(mode="json", exclude={"cached"})
    await redis_client.setex(cache_key, _CACHE_TTL_SECONDS, json.dumps(payload))

    return insights
