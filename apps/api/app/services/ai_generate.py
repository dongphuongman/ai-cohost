"""AI content generation services using Gemini Flash."""

import json
import logging

from google import genai

from app.core.config import settings

logger = logging.getLogger(__name__)

HIGHLIGHT_PROMPT = """Bạn là chuyên gia marketing sản phẩm Việt Nam.

Dựa trên thông tin sản phẩm sau, hãy sinh ra {count} điểm nổi bật ngắn gọn (mỗi điểm 5-15 từ).
Mỗi điểm phải hấp dẫn, cụ thể, và giúp khách hàng muốn mua.

Tên sản phẩm: {name}
Mô tả: {description}
Giá: {price}
Ngành hàng: {category}

Trả về JSON array of strings. Chỉ trả JSON, không có text khác.
Ví dụ: ["SPF50 PA++++ bảo vệ tối đa", "Kết cấu lỏng nhẹ thấm trong 30 giây"]"""

FAQ_PROMPT = """Bạn là chuyên viên CSKH cho shop bán hàng online Việt Nam.

Dựa trên thông tin sản phẩm, hãy sinh ra {count} cặp câu hỏi-trả lời mà khách hàng hay hỏi nhất khi xem live.

Tên sản phẩm: {name}
Mô tả: {description}
Điểm nổi bật: {highlights}
Giá: {price}

Trả về JSON array of objects: [{{"question": "...", "answer": "..."}}]
Câu trả lời phải thân thiện, xưng "em/mình" với khách, dưới 50 từ mỗi câu.
Chỉ trả JSON."""


def _get_client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


def _parse_json_response(text: str) -> list:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


async def generate_highlights(
    name: str,
    description: str | None,
    price: float | None,
    category: str | None,
    count: int = 6,
) -> list[str]:
    prompt = HIGHLIGHT_PROMPT.format(
        count=count,
        name=name,
        description=description or "(không có)",
        price=f"{price:,.0f} VND" if price else "(không rõ)",
        category=category or "(không rõ)",
    )

    client = _get_client()
    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    highlights = _parse_json_response(response.text)

    if not isinstance(highlights, list):
        raise ValueError("Expected JSON array")

    return [str(h) for h in highlights[:count]]


async def generate_faqs(
    name: str,
    description: str | None,
    highlights: list[str],
    price: float | None,
    count: int = 5,
) -> list[dict]:
    prompt = FAQ_PROMPT.format(
        count=count,
        name=name,
        description=description or "(không có)",
        highlights=", ".join(highlights) if highlights else "(chưa có)",
        price=f"{price:,.0f} VND" if price else "(không rõ)",
    )

    client = _get_client()
    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    faqs = _parse_json_response(response.text)

    if not isinstance(faqs, list):
        raise ValueError("Expected JSON array")

    result = []
    for item in faqs[:count]:
        if isinstance(item, dict) and "question" in item and "answer" in item:
            result.append({"question": str(item["question"]), "answer": str(item["answer"])})

    return result
