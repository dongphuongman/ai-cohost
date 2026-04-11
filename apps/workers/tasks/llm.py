"""LLM suggestion generation for live comments.

Pipeline: classify intent → embed comment → RAG query → build prompt → stream LLM → publish to Redis.
"""

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone

import google.generativeai as genai
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from celery_app import app
from config import settings

logger = logging.getLogger(__name__)

_sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg2")
_engine = create_engine(_sync_db_url)
_redis = redis.from_url(settings.redis_url)

# --- Intent classification (inline, no LLM) ---

SKIP_INTENTS = frozenset({"greeting", "thanks", "praise", "spam"})

_GREETING = re.compile(
    r"\b(chào|hi|hello|hey|shop ơi|xin chào|alo|a lô)\b", re.IGNORECASE
)
_THANKS = re.compile(
    r"\b(cảm ơn|cam on|thank|tks|cám ơn|xinh quá|đẹp quá|tuyệt vời|hay quá|quá đỉnh)\b",
    re.IGNORECASE,
)
_PRICING = re.compile(
    r"\b(giá|bao nhiêu|bao nhieu|bn|giảm giá|khuyến mãi|khuyen mai|sale|mã|voucher|coupon|rẻ|đắt)\b",
    re.IGNORECASE,
)
_SHIPPING = re.compile(
    r"\b(ship|giao hàng|giao hang|vận chuyển|van chuyen|cod|freeship|free ship|phí ship)\b",
    re.IGNORECASE,
)
_COMPLAINT = re.compile(
    r"\b(lỗi|hỏng|bể|fake|giả|scam|tệ|kém|dở|chậm|trễ|sai|nhầm|hoàn|trả)\b",
    re.IGNORECASE,
)
_SPAM_PATTERNS = re.compile(r"(https?://|@@|###|t\.me/|bit\.ly)", re.IGNORECASE)
_QUESTION_MARKERS = re.compile(
    r"(\?|không|có|sao|thế nào|the nao|bao lâu|bao lau|khi nào|ở đâu|nào|gì|gi\b|hả|nhỉ|vậy)",
    re.IGNORECASE,
)


def _classify_intent(text_: str) -> tuple[str, float]:
    text_ = text_.strip()
    if not text_:
        return ("spam", 0.9)
    if _SPAM_PATTERNS.search(text_) or len(text_) > 500:
        return ("spam", 0.9)
    if len(text_) < 3:
        return ("praise", 0.7)
    emoji_count = sum(1 for c in text_ if ord(c) > 0x1F600)
    if emoji_count > 3 and emoji_count > len(text_) * 0.5:
        return ("praise", 0.7)
    if _GREETING.search(text_) and len(text_) < 30:
        return ("greeting", 0.8)
    if _THANKS.search(text_):
        return ("thanks", 0.8)
    if _COMPLAINT.search(text_):
        return ("complaint", 0.8)
    if _PRICING.search(text_):
        return ("pricing", 0.85)
    if _SHIPPING.search(text_):
        return ("shipping", 0.85)
    if _QUESTION_MARKERS.search(text_):
        return ("question", 0.7)
    return ("other", 0.5)


# --- Embedding ---


def _get_embedding(content: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    genai.configure(api_key=settings.gemini_api_key)
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=content,
        task_type=task_type,
    )
    return result["embedding"]


# --- RAG Query ---

RAG_QUERY = text("""
WITH relevant_products AS (
    SELECT id, name, description, highlights, price, currency,
           1 - (embedding <=> :embedding::vector) AS similarity
    FROM products
    WHERE shop_id = :shop_id
      AND is_active = true
      AND id = ANY(:product_ids::bigint[])
      AND embedding IS NOT NULL
    ORDER BY embedding <=> :embedding::vector
    LIMIT 2
),
relevant_faqs AS (
    SELECT f.id, f.question, f.answer, f.product_id,
           1 - (f.embedding <=> :embedding::vector) AS similarity
    FROM product_faqs f
    WHERE f.shop_id = :shop_id
      AND f.product_id IN (SELECT id FROM relevant_products)
      AND f.embedding IS NOT NULL
    ORDER BY f.embedding <=> :embedding::vector
    LIMIT 3
)
SELECT
    (SELECT json_agg(row_to_json(p)) FROM relevant_products p) AS products,
    (SELECT json_agg(row_to_json(f)) FROM relevant_faqs f) AS faqs
""")


# --- Prompt ---

COMMENT_RESPONDER_PROMPT = """Bạn là {persona_name}, trợ lý bán hàng livestream.

PHONG CÁCH:
{persona_tone}
{persona_quirks}

SẢN PHẨM ĐANG BÁN:
{product_context}

FAQ LIÊN QUAN:
{faq_context}

CUỘC TRÒ CHUYỆN GẦN ĐÂY:
{history_context}

KHÁCH VỪA HỎI: "{comment_text}"

QUY TẮC BẮT BUỘC:
1. Trả lời ngắn gọn, dưới 40 từ, bằng tiếng Việt
2. Thân thiện, dùng phong cách đã cho ở trên
3. KHÔNG bịa thông tin sản phẩm — chỉ dùng thông tin trong FAQ và mô tả
4. Nếu không biết câu trả lời, nói "Để em check rồi báo lại ạ"
5. KHÔNG đề cập giá cụ thể trừ khi giá có trong thông tin sản phẩm
6. KHÔNG hứa hẹn về khuyến mãi, giảm giá trừ khi được nêu rõ trong dữ liệu

CHỈ trả lời nội dung reply, không thêm prefix hay label."""


def _build_prompt(
    persona: dict,
    comment_text: str,
    products: list[dict],
    faqs: list[dict],
    history: list[dict],
) -> str:
    # Product context
    product_lines = []
    for p in products:
        line = f"- {p['name']}"
        if p.get("price"):
            line += f" ({p['price']} {p.get('currency', 'VND')})"
        if p.get("description"):
            line += f": {p['description'][:200]}"
        if p.get("highlights"):
            hl = p["highlights"]
            if isinstance(hl, list):
                line += " | " + ", ".join(hl[:3])
        product_lines.append(line)
    product_context = "\n".join(product_lines) if product_lines else "(không có sản phẩm nào khớp)"

    # FAQ context
    faq_lines = []
    for f in faqs:
        faq_lines.append(f"Q: {f['question']}\nA: {f['answer']}")
    faq_context = "\n".join(faq_lines) if faq_lines else "(không có FAQ liên quan)"

    # History context
    history_lines = []
    for h in history:
        history_lines.append(f"Khách: {h['question']}\nShop: {h['answer']}")
    history_context = "\n".join(history_lines) if history_lines else "(chưa có)"

    # Persona
    persona_name = persona.get("name", "AI Co-host")
    persona_tone = persona.get("tone", "Thân thiện, nhiệt tình")
    quirks = persona.get("quirks") or []
    persona_quirks = ", ".join(quirks) if quirks else "(không có)"

    return COMMENT_RESPONDER_PROMPT.format(
        persona_name=persona_name,
        persona_tone=persona_tone,
        persona_quirks=persona_quirks,
        product_context=product_context,
        faq_context=faq_context,
        history_context=history_context,
        comment_text=comment_text,
    )


# --- Cache ---


def _cache_key(shop_id: int, comment_text: str) -> str:
    normalized = comment_text.strip().lower()[:100]
    h = hashlib.md5(normalized.encode()).hexdigest()
    return f"suggestion_cache:{shop_id}:{h}"


# --- LLM with fallback ---


def _call_llm_with_fallback(
    prompt: str, comment_id: int, session_id: int,
) -> tuple[str, str, str]:
    """Call LLM with Gemini Flash primary, DeepSeek V3 fallback.

    Returns (response_text, model_used, provider_used).
    """
    channel = f"suggestion_stream:{session_id}"
    last_error = None

    # Provider 1: Gemini Flash
    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        full_response = ""
        response = model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                full_response += chunk.text
                _redis.publish(channel, json.dumps({
                    "type": "suggestion.stream",
                    "comment_id": comment_id,
                    "chunk": chunk.text,
                }))
        if full_response.strip():
            return full_response, "gemini-2.0-flash", "google"
    except Exception as e:
        last_error = e
        logger.warning("Gemini Flash failed for comment %s: %s. Trying DeepSeek...", comment_id, e)

    # Provider 2: DeepSeek V3
    if settings.deepseek_api_key:
        try:
            import httpx
            resp = httpx.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "stream": False,
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text_out = data["choices"][0]["message"]["content"]
            if text_out.strip():
                _redis.publish(channel, json.dumps({
                    "type": "suggestion.stream",
                    "comment_id": comment_id,
                    "chunk": text_out,
                }))
                return text_out, "deepseek-chat", "deepseek"
        except Exception as e:
            last_error = e
            logger.warning("DeepSeek also failed for comment %s: %s", comment_id, e)

    # Both failed
    logger.error("All LLM providers failed for comment %s. Last error: %s", comment_id, last_error)
    return "", "none", "none"


# --- Main task ---


@app.task(
    name="tasks.llm.generate_suggestion",
    max_retries=2,
    soft_time_limit=30,
    acks_late=True,
)
def generate_suggestion(comment_id: int, session_id: int, shop_id: int) -> dict:
    """Generate AI suggestion for a live comment.

    Full pipeline: classify → embed → RAG → prompt → stream LLM → Redis pub/sub → save.
    """
    try:
        return _do_generate(comment_id, session_id, shop_id)
    except Exception:
        logger.exception(
            "generate_suggestion failed for comment=%s session=%s",
            comment_id,
            session_id,
        )
        # Publish error so WS can inform client
        _redis.publish(
            f"suggestion_stream:{session_id}",
            json.dumps({
                "type": "suggestion.error",
                "comment_id": comment_id,
                "error": "generation_failed",
            }),
        )
        raise


def _do_generate(comment_id: int, session_id: int, shop_id: int) -> dict:
    with Session(_engine) as db:
        # 1. Fetch comment
        comment_row = db.execute(
            text("SELECT id, text, session_id FROM comments WHERE id = :id"),
            {"id": comment_id},
        ).mappings().first()
        if not comment_row:
            return {"status": "comment_not_found"}

        comment_text = comment_row["text"]

        # 2. Classify intent
        intent, confidence = _classify_intent(comment_text)
        db.execute(
            text("UPDATE comments SET intent = :intent, confidence = :conf, is_processed = true WHERE id = :id"),
            {"intent": intent, "conf": confidence, "id": comment_id},
        )
        db.commit()

        # 3. Skip non-actionable intents
        if intent in SKIP_INTENTS:
            logger.info("Skipping %s intent for comment %s", intent, comment_id)
            return {"status": "skipped", "intent": intent}

        # 4. Fetch session data (persona_id, active_product_ids)
        session_row = db.execute(
            text("SELECT persona_id, active_product_ids FROM live_sessions WHERE id = :id"),
            {"id": session_id},
        ).mappings().first()
        if not session_row:
            return {"status": "session_not_found"}

        persona_id = session_row["persona_id"]
        product_ids = session_row["active_product_ids"] or []

        # 5. Fetch persona
        persona = {"name": "AI Co-host", "tone": "Thân thiện, nhiệt tình", "quirks": []}
        if persona_id:
            persona_row = db.execute(
                text("SELECT name, tone, quirks, sample_phrases FROM personas WHERE id = :id"),
                {"id": persona_id},
            ).mappings().first()
            if persona_row:
                persona = dict(persona_row)

        # 6. Embed comment text
        embedding = _get_embedding(comment_text, task_type="RETRIEVAL_QUERY")

        # 7. RAG query
        rag_row = db.execute(
            RAG_QUERY,
            {
                "embedding": str(embedding),
                "shop_id": shop_id,
                "product_ids": product_ids,
            },
        ).mappings().first()

        products = (rag_row["products"] or []) if rag_row else []
        faqs = (rag_row["faqs"] or []) if rag_row else []

        # 8. Get conversation history from Redis (last 5 Q&A pairs)
        history_key = f"history:{session_id}"
        raw_history = _redis.lrange(history_key, 0, 4)
        history = [json.loads(h) for h in raw_history] if raw_history else []

        # 9. Build prompt
        prompt = _build_prompt(persona, comment_text, products, faqs, history)

        # 10. Call LLM with fallback: Gemini Flash → DeepSeek V3
        full_response, llm_model_used, llm_provider_used = _call_llm_with_fallback(
            prompt, comment_id, session_id,
        )
        start_time = time.time()
        latency_ms = int((time.time() - start_time) * 1000)

        if not full_response.strip():
            full_response = "Để em check rồi báo lại ạ"
        # Sanitize: strip any HTML tags from LLM output
        full_response = re.sub(r"<[^>]+>", "", full_response).strip()

        # 11. Save suggestion to DB
        result = db.execute(
            text(
                "INSERT INTO suggestions "
                "(comment_id, session_id, shop_id, text, llm_model, llm_provider, "
                "latency_ms, rag_product_ids, rag_faq_ids, prompt_version, status) "
                "VALUES (:comment_id, :session_id, :shop_id, :text, :llm_model, "
                ":llm_provider, :latency_ms, :rag_product_ids, :rag_faq_ids, "
                ":prompt_version, 'suggested') "
                "RETURNING id, created_at"
            ),
            {
                "comment_id": comment_id,
                "session_id": session_id,
                "shop_id": shop_id,
                "text": full_response,
                "llm_model": llm_model_used,
                "llm_provider": llm_provider_used,
                "latency_ms": latency_ms,
                "rag_product_ids": [p["id"] for p in products] if products else None,
                "rag_faq_ids": [f["id"] for f in faqs] if faqs else None,
                "prompt_version": "v1",
            },
        )
        suggestion_row = result.mappings().first()
        suggestion_id = suggestion_row["id"]
        created_at = suggestion_row["created_at"]

        # Increment session suggestions_count
        db.execute(
            text(
                "UPDATE live_sessions SET suggestions_count = suggestions_count + 1 "
                "WHERE id = :id"
            ),
            {"id": session_id},
        )
        db.commit()

        # 12. Publish completion via Redis
        _redis.publish(
            channel,
            json.dumps({
                "type": "suggestion.complete",
                "comment_id": comment_id,
                "suggestion_id": suggestion_id,
                "suggestion": {
                    "id": str(suggestion_id),
                    "replyText": full_response,
                    "originalComment": {
                        "externalUserName": "",  # filled by WS handler
                        "text": comment_text,
                        "receivedAt": "",
                    },
                    "confidence": confidence,
                    "createdAt": str(created_at) if created_at else "",
                },
            }),
        )

        # 13. Cache for similar future comments (5 min TTL)
        cache_val = json.dumps({
            "id": str(suggestion_id),
            "replyText": full_response,
            "confidence": confidence,
        })
        _redis.setex(_cache_key(shop_id, comment_text), 300, cache_val)

        # 14. Save to conversation history in Redis
        _redis.lpush(
            history_key,
            json.dumps({"question": comment_text, "answer": full_response}),
        )
        _redis.ltrim(history_key, 0, 4)  # keep last 5

        return {
            "status": "ok",
            "suggestion_id": suggestion_id,
            "intent": intent,
            "latency_ms": latency_ms,
        }


@app.task(name="tasks.llm.classify_intent")
def classify_intent(comment_id: int, text_: str) -> dict:
    """Classify comment intent (standalone task, rarely used — inline is preferred)."""
    intent, confidence = _classify_intent(text_)
    with Session(_engine) as db:
        db.execute(
            text("UPDATE comments SET intent = :intent, confidence = :conf WHERE id = :id"),
            {"intent": intent, "conf": confidence, "id": comment_id},
        )
        db.commit()
    return {"intent": intent, "confidence": confidence}
