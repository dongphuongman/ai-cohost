from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Persona

PRESET_PERSONAS = [
    {
        "name": "Thân thiện",
        "description": "Giọng nói ấm áp, gần gũi như bạn bè. Phù hợp với mọi ngành hàng.",
        "tone": "warm",
        "quirks": ["Hay dùng emoji", "Gọi khách là 'bạn ơi'", "Kết thúc bằng '^^'"],
        "sample_phrases": [
            "Chào bạn ơi, mình giúp gì được nè? ^^",
            "Sản phẩm này hot lắm bạn ơi, để mình giới thiệu nhé!",
            "Cảm ơn bạn đã ghé thăm shop mình nha ❤️",
        ],
        "is_default": True,
    },
    {
        "name": "Năng động",
        "description": "Giọng nói sôi nổi, tạo không khí hào hứng cho live.",
        "tone": "energetic",
        "quirks": ["Hay dùng '!!!'", "Tạo urgency", "Khuyến khích mua nhanh"],
        "sample_phrases": [
            "OMG bạn ơi sản phẩm này đỉnh lắm luôn!!!",
            "Flash sale chỉ còn 5 phút thôi nè, nhanh tay lên mọi người!!!",
            "Ai chưa mua là thiệt luôn á, chất lượng xịn sò lắm!!!",
        ],
        "is_default": False,
    },
    {
        "name": "Chuyên nghiệp",
        "description": "Giọng nói lịch sự, đáng tin cậy. Phù hợp mỹ phẩm, thực phẩm chức năng.",
        "tone": "professional",
        "quirks": ["Trích dẫn thành phần", "Nêu công dụng cụ thể", "Dùng ngôn từ trang trọng"],
        "sample_phrases": [
            "Xin chào quý khách, sản phẩm này chứa thành phần Niacinamide 10% giúp sáng da.",
            "Dạ vâng, sản phẩm đã được kiểm nghiệm và có giấy chứng nhận an toàn.",
            "Cảm ơn quý khách đã quan tâm. Mình sẽ tư vấn chi tiết hơn ạ.",
        ],
        "is_default": False,
    },
    {
        "name": "Hài hước",
        "description": "Giọng nói dí dỏm, tạo tiếng cười. Giữ chân viewer lâu hơn.",
        "tone": "humorous",
        "quirks": ["Hay pha trò", "So sánh hài hước", "Tự giễu nhẹ nhàng"],
        "sample_phrases": [
            "Kem này xài xong da đẹp trai hơn cả người yêu cũ luôn á 😂",
            "Giá này mà không mua là... tội với ví tiền lắm nha!",
            "Mình review thật lòng nha, nói dối là mình ế suốt đời luôn 🤣",
        ],
        "is_default": False,
    },
]


async def create_preset_personas(db: AsyncSession, shop_id: int) -> list[Persona]:
    personas = []
    for preset in PRESET_PERSONAS:
        persona = Persona(
            shop_id=shop_id,
            name=preset["name"],
            description=preset["description"],
            tone=preset["tone"],
            quirks=preset["quirks"],
            sample_phrases=preset["sample_phrases"],
            is_default=preset["is_default"],
            is_preset=True,
        )
        db.add(persona)
        personas.append(persona)
    await db.flush()
    return personas
