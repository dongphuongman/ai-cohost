"""Script generation Celery task with LLM streaming and Redis pub/sub."""

import json
import logging
from datetime import datetime, timezone

import google.generativeai as genai
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from celery_app import app
from config import settings

logger = logging.getLogger(__name__)

_sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
    "postgresql+psycopg2", "postgresql+psycopg2"
)
_engine = create_engine(_sync_db_url)
_redis = redis.from_url(settings.redis_url)


def _get_embedding(content: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    genai.configure(api_key=settings.gemini_api_key)
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=content,
        task_type=task_type,
    )
    return result["embedding"]


def _count_ctas(content: str) -> int:
    cta_phrases = [
        "đặt hàng", "mua ngay", "inbox", "comment", "để lại",
        "link", "giỏ hàng", "add to cart", "nhấn", "bấm",
        "đừng bỏ lỡ", "nhanh tay", "số lượng có hạn", "chỉ còn",
        "giảm giá", "ưu đãi", "khuyến mãi", "flash sale",
        "free ship", "miễn phí vận chuyển",
    ]
    count = 0
    content_lower = content.lower()
    for phrase in cta_phrases:
        count += content_lower.count(phrase)
    return min(count, 20)


def _generate_title(products: list[dict], config: dict) -> str:
    product_names = [p["name"] for p in products[:2]]
    duration = config.get("duration_target", 10)
    if len(products) == 1:
        return f"{product_names[0]} — {duration} phút"
    elif len(products) == 2:
        return f"{product_names[0]} & {product_names[1]} — {duration} phút"
    else:
        return f"{product_names[0]} và {len(products) - 1} sản phẩm khác — {duration} phút"


def _build_script_prompt(
    persona: dict | None,
    products: list[dict],
    samples: list[str],
    duration_minutes: int,
    tone: str,
    special_notes: str | None = None,
) -> str:
    # Product details
    products_text = ""
    for i, p in enumerate(products, 1):
        products_text += f"\nSản phẩm {i}: {p['name']}\n"
        products_text += f"  Mô tả: {p.get('description') or 'Chưa có mô tả'}\n"
        price = p.get("price")
        currency = p.get("currency", "VND")
        products_text += f"  Giá: {f'{price:,.0f} {currency}' if price else 'Chưa có giá'}\n"
        highlights = p.get("highlights")
        if highlights:
            products_text += f"  Điểm nổi bật: {', '.join(highlights)}\n"

    # Few-shot samples
    samples_text = ""
    for i, s in enumerate(samples, 1):
        samples_text += f"\n--- Mẫu tham khảo {i} ---\n{s}\n"

    # Persona
    persona_text = "Phong cách mặc định: thân thiện, gần gũi"
    if persona:
        persona_text = f"Tên: {persona.get('name', 'Host')}\n"
        persona_text += f"Tone: {persona.get('tone', tone)}\n"
        quirks = persona.get("quirks")
        if quirks:
            persona_text += f"Đặc điểm: {', '.join(quirks)}\n"
        phrases = persona.get("sample_phrases")
        if phrases:
            persona_text += f"Câu mẫu: {', '.join(phrases[:3])}\n"

    special_section = ""
    if special_notes:
        special_section = f"\nCHÚ Ý ĐẶC BIỆT TỪ NGƯỜI DÙNG:\n{special_notes}\n"

    word_target = duration_minutes * 150

    return f"""Bạn là host livestream bán hàng chuyên nghiệp tại Việt Nam.

PHONG CÁCH:
{persona_text}

SẢN PHẨM CẦN GIỚI THIỆU:
{products_text}

CÁC SCRIPT MẪU THAM KHẢO (học phong cách, KHÔNG copy nội dung):
{samples_text}

YÊU CẦU:
Viết kịch bản livestream bán hàng {duration_minutes} phút với cấu trúc:

# Mở đầu (30 giây)
- Chào đón người xem, tạo không khí
- Nhắc follow và like

# Giới thiệu sản phẩm (chiếm 60% thời lượng)
- Giới thiệu từng sản phẩm với highlights
- Kết hợp storytelling thực tế
- Nhấn mạnh lợi ích cho khách hàng

# Xử lý phản đối (10%)
- Trả lời trước các câu hỏi hay gặp
- So sánh giá trị (không so sánh với đối thủ)

# Call to Action (10%)
- Tạo urgency (giới hạn thời gian/số lượng)
- Hướng dẫn cách đặt hàng
- Nhắc lại ưu đãi

# Kết thúc (30 giây)
- Cảm ơn người xem
- Nhắc lịch live tiếp theo
{special_section}
QUY TẮC BẮT BUỘC:
1. Viết bằng tiếng Việt tự nhiên, giọng {tone}
2. KHÔNG bịa thông tin sản phẩm — chỉ dùng dữ liệu đã cho
3. KHÔNG so sánh với sản phẩm hoặc thương hiệu đối thủ
4. KHÔNG hứa giảm giá hoặc khuyến mãi trừ khi có trong dữ liệu
5. Giữ đúng phong cách persona
6. Dùng heading markdown (#) cho mỗi section
7. Ước tính {duration_minutes} phút ≈ {word_target} từ"""


def _fetch_few_shot_samples(products: list[dict], persona_style: str) -> list[str]:
    """Fetch relevant script samples using pgvector similarity search."""
    category = (products[0].get("category") or "general") if products else "general"
    query_text = " ".join(p["name"] for p in products) + " " + category

    try:
        query_embedding = _get_embedding(query_text)
    except Exception:
        logger.warning("Failed to generate embedding for few-shot query, skipping samples")
        return []

    with Session(_engine) as session:
        # Try category + style match first
        rows = session.execute(
            text("""
                SELECT content FROM script_samples
                WHERE category = :category AND persona_style = :style
                  AND quality_score >= 4
                ORDER BY embedding <=> :embedding::vector
                LIMIT 3
            """),
            {
                "category": category,
                "style": persona_style,
                "embedding": str(query_embedding),
            },
        ).fetchall()

        # Fallback: cross-category if not enough
        if len(rows) < 2:
            more = session.execute(
                text("""
                    SELECT content FROM script_samples
                    WHERE quality_score >= 4
                    ORDER BY embedding <=> :embedding::vector
                    LIMIT 3
                """),
                {"embedding": str(query_embedding)},
            ).fetchall()
            seen = {r[0] for r in rows}
            for r in more:
                if r[0] not in seen:
                    rows.append(r)
                    seen.add(r[0])
                if len(rows) >= 3:
                    break

    return [r[0] for r in rows]


@app.task(
    name="tasks.script.generate_script",
    soft_time_limit=120,
    max_retries=2,
    default_retry_delay=10,
)
def generate_script(
    shop_id: int,
    user_id: int,
    config: dict,
    products: list[dict],
    persona: dict | None,
) -> dict:
    """Generate a livestream script using LLM with streaming."""
    task = generate_script
    job_id = generate_script.request.id or "unknown"
    channel = f"script_gen:{shop_id}"

    try:
        # 1. Fetch few-shot samples
        persona_style = (persona.get("tone") if persona else None) or config.get("tone", "thân thiện")
        samples = _fetch_few_shot_samples(products, persona_style)

        # 2. Build prompt
        prompt = _build_script_prompt(
            persona=persona,
            products=products,
            samples=samples,
            duration_minutes=config["duration_target"],
            tone=config["tone"],
            special_notes=config.get("special_notes"),
        )

        # 3. Call Gemini Flash (streaming)
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt, stream=True)

        full_response = ""
        for chunk in response:
            if chunk.text:
                full_response += chunk.text
                _redis.publish(channel, json.dumps({
                    "type": "script.chunk",
                    "job_id": job_id,
                    "chunk": chunk.text,
                }))

        if not full_response.strip():
            raise ValueError("LLM returned empty response")

        # 4. Post-process
        word_count = len(full_response.split())
        estimated_duration_seconds = int(word_count / 150 * 60)
        cta_count = _count_ctas(full_response)
        title = _generate_title(products, config)

        # 5. Save to DB
        with Session(_engine) as session:
            result = session.execute(
                text("""
                    INSERT INTO scripts (
                        shop_id, created_by, title, content,
                        product_ids, persona_id, duration_target, tone, special_notes,
                        word_count, estimated_duration_seconds, cta_count,
                        llm_model, llm_provider, prompt_version,
                        version, created_at, updated_at
                    ) VALUES (
                        :shop_id, :created_by, :title, :content,
                        :product_ids, :persona_id, :duration_target, :tone, :special_notes,
                        :word_count, :estimated_duration_seconds, :cta_count,
                        :llm_model, :llm_provider, :prompt_version,
                        1, :now, :now
                    ) RETURNING id
                """),
                {
                    "shop_id": shop_id,
                    "created_by": user_id,
                    "title": title,
                    "content": full_response,
                    "product_ids": config["product_ids"],
                    "persona_id": config.get("persona_id"),
                    "duration_target": config["duration_target"],
                    "tone": config["tone"],
                    "special_notes": config.get("special_notes"),
                    "word_count": word_count,
                    "estimated_duration_seconds": estimated_duration_seconds,
                    "cta_count": cta_count,
                    "llm_model": "gemini-2.0-flash",
                    "llm_provider": "google",
                    "prompt_version": "v1",
                    "now": datetime.now(timezone.utc),
                },
            )
            script_id = result.scalar_one()
            session.commit()

        # 6. Track usage
        with Session(_engine) as session:
            session.execute(
                text("""
                    INSERT INTO usage_logs (
                        shop_id, user_id, resource_type, resource_id,
                        quantity, unit, billing_period
                    ) VALUES (
                        :shop_id, :user_id, 'script', :resource_id,
                        1, 'count', :billing_period
                    )
                """),
                {
                    "shop_id": shop_id,
                    "user_id": user_id,
                    "resource_id": script_id,
                    "billing_period": datetime.now(timezone.utc).date().replace(day=1),
                },
            )
            session.commit()

        # 7. Publish completion
        _redis.publish(channel, json.dumps({
            "type": "script.complete",
            "job_id": job_id,
            "script_id": script_id,
            "script": {
                "id": script_id,
                "title": title,
                "word_count": word_count,
                "estimated_duration_seconds": estimated_duration_seconds,
                "cta_count": cta_count,
            },
        }))

        return {
            "status": "ok",
            "script_id": script_id,
            "word_count": word_count,
        }

    except Exception as exc:
        logger.exception("Script generation failed for shop %s", shop_id)
        _redis.publish(channel, json.dumps({
            "type": "script.error",
            "job_id": job_id,
            "error": "Có lỗi khi tạo script. Vui lòng thử lại.",
        }))
        raise task.retry(exc=exc, countdown=10)
