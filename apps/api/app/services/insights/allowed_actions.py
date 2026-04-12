"""Registry of dashboard actions that AI Insights is allowed to recommend.

WHY THIS EXISTS
───────────────
The LLM that generates session insights used to hallucinate features that
don't exist in the dashboard ("Vào cài đặt AI > thêm intent...", "Soạn sẵn
câu trả lời cho intent..."). Shop owners read those recommendations,
hunted for the buttons, found nothing, and lost trust.

This module is the SOURCE OF TRUTH for actions the LLM may suggest. Every
entry here corresponds to a real button/form/page in
``apps/dashboard/src/app/(dashboard)/**`` or the Chrome extension popup.

WHEN ADDING A NEW UI FEATURE
────────────────────────────
1. Add an entry here with the exact navigation path (Vietnamese).
2. Set ``plan_required`` to the cheapest plan that unlocks it.
3. If you're REMOVING a UI feature, also add the disappearing label to
   ``FORBIDDEN_PHRASES`` in ``app.services.session_insights`` so cached
   prompts can't sneak it back.

The registry is intentionally narrow: only actions a shop owner could
plausibly take in response to *session analytics* findings. Login,
billing, profile editing, team management, etc. are excluded — they're
real features but they don't fix livestream data quality problems.
"""

from __future__ import annotations

from typing import Literal, TypedDict

PlanTier = Literal["starter", "pro", "enterprise"]

# Plan rank — higher means more inclusive. ``trial`` is treated as
# ``starter`` (trial users see the same surface area, just with quotas).
_PLAN_RANK: dict[str, int] = {
    "trial": 1,
    "starter": 1,
    "pro": 2,
    "enterprise": 3,
}


class AllowedAction(TypedDict):
    label: str
    navigation: str
    when: str
    plan_required: PlanTier


# ────────────────────────────────────────────────────────────────────────────
# Registry — organized by dashboard page for maintainability.
# Every key appears EXACTLY ONCE across all sections.
# ────────────────────────────────────────────────────────────────────────────


# Products page — primary lever for "AI couldn't answer because product
# data was missing". Most insight actions land here.
_PRODUCTS: dict[str, AllowedAction] = {
    "add_product": {
        "label": "Thêm sản phẩm mới",
        "navigation": "Sản phẩm > nút 'Thêm sản phẩm' (nhập tay hoặc dán URL Shopee/TikTok)",
        "when": "Khi viewer nhắc một sản phẩm chưa có trong catalog",
        "plan_required": "starter",
    },
    "edit_product_description": {
        "label": "Cập nhật mô tả sản phẩm",
        "navigation": "Sản phẩm > [tên sản phẩm] > field 'Mô tả'",
        "when": "Khi mô tả thiếu thông tin khách đang hỏi (chất liệu, kích thước, combo, v.v.)",
        "plan_required": "starter",
    },
    "edit_product_price": {
        "label": "Cập nhật giá sản phẩm",
        "navigation": "Sản phẩm > [tên sản phẩm] > field 'Giá'",
        "when": "Khi sản phẩm thiếu giá hoặc giá trong data lệch với giá đang chốt",
        "plan_required": "starter",
    },
    "add_product_highlight_manual": {
        "label": "Thêm điểm nổi bật cho sản phẩm (nhập tay)",
        "navigation": "Sản phẩm > [tên sản phẩm] > mục 'Điểm nổi bật' > nút 'Thêm'",
        "when": "Khi sản phẩm chưa có highlights để AI dùng làm context khi reply",
        "plan_required": "starter",
    },
    "add_product_highlight_ai": {
        "label": "AI gợi ý điểm nổi bật cho sản phẩm",
        "navigation": "Sản phẩm > [tên sản phẩm] > mục 'Điểm nổi bật' > nút 'AI gợi ý'",
        "when": "Khi cần highlights nhanh và đã có mô tả sản phẩm cho AI dựa vào",
        "plan_required": "pro",
    },
    "add_product_faq_manual": {
        "label": "Thêm câu hỏi thường gặp cho sản phẩm (nhập tay)",
        "navigation": "Sản phẩm > [tên sản phẩm] > tab 'FAQ' > nút 'Thêm FAQ'",
        "when": "Khi viewer hỏi cùng một câu nhiều lần mà sản phẩm chưa có FAQ trả lời",
        "plan_required": "starter",
    },
    "add_product_faq_ai": {
        "label": "AI tạo FAQ từ mô tả sản phẩm",
        "navigation": "Sản phẩm > [tên sản phẩm] > tab 'FAQ' > nút 'AI tạo FAQ'",
        "when": "Khi sản phẩm có ít FAQ và cần sinh nhanh một loạt từ mô tả",
        "plan_required": "pro",
    },
    "edit_product_faq": {
        "label": "Sửa FAQ hiện có",
        "navigation": "Sản phẩm > [tên sản phẩm] > tab 'FAQ' > icon sửa",
        "when": "Khi câu trả lời FAQ cũ bị sai hoặc lỗi thời",
        "plan_required": "starter",
    },
    "reindex_product": {
        "label": "Re-index sản phẩm cho search",
        "navigation": "Sản phẩm > [tên sản phẩm] > nút 'Re-index'",
        "when": "Khi đã update mô tả/highlights nhưng AI vẫn dùng context cũ",
        "plan_required": "enterprise",
    },
}


# Scripts page — fix coverage by preparing better content for next session.
_SCRIPTS: dict[str, AllowedAction] = {
    "create_script": {
        "label": "Tạo kịch bản livestream",
        "navigation": "Kịch bản > nút 'Tạo script mới' > chọn 1-5 sản phẩm + persona + thời lượng + tone",
        "when": "Khi shop chưa có kịch bản chuẩn cho live, hoặc cần thử persona khác",
        "plan_required": "starter",
    },
    "edit_script": {
        "label": "Chỉnh sửa nội dung kịch bản",
        "navigation": "Kịch bản > [tên kịch bản] > textarea chỉnh sửa > nút 'Lưu'",
        "when": "Khi kịch bản đã sinh nhưng cần điều chỉnh wording",
        "plan_required": "starter",
    },
    "regenerate_script": {
        "label": "Sinh lại kịch bản với cấu hình hiện tại",
        "navigation": "Kịch bản > [tên kịch bản] > nút 'Sinh lại'",
        "when": "Khi kịch bản hiện tại không phù hợp và muốn AI tạo bản khác",
        "plan_required": "pro",
    },
    "create_script_from_session": {
        "label": "Tạo script mới dựa trên session này",
        "navigation": "Phiên live > [session] > nút 'Tạo script từ session'",
        "when": "Khi muốn nhân bản nội dung của một session đã chạy tốt cho lần sau",
        "plan_required": "pro",
    },
}


# Live session page — adjust mid-session behavior or extract data.
_SESSIONS: dict[str, AllowedAction] = {
    "review_top_questions": {
        "label": "Xem top câu hỏi của khách trong session",
        "navigation": "Phiên live > [session] > section 'Câu hỏi của khách'",
        "when": "Khi muốn biết viewer hỏi gì nhiều nhất để chuẩn bị nội dung lần sau",
        "plan_required": "starter",
    },
    "export_session_csv": {
        "label": "Xuất dữ liệu session ra CSV",
        "navigation": "Phiên live > [session] > nút 'Xuất CSV'",
        "when": "Khi cần dữ liệu offline để phân tích sâu hoặc chia sẻ với team",
        "plan_required": "starter",
    },
    "toggle_auto_reply": {
        "label": "Bật/tắt auto-reply trong session đang chạy",
        "navigation": "Phiên live > [session đang chạy] > toggle 'Auto-reply'",
        "when": "Khi muốn AI tự động gửi reply có confidence cao thay vì chỉ gợi ý",
        "plan_required": "starter",
    },
    "adjust_auto_reply_threshold": {
        "label": "Chỉnh ngưỡng confidence cho auto-reply",
        "navigation": "Phiên live > [session đang chạy] > slider 'Ngưỡng confidence' (0.5-1.0)",
        "when": "Khi auto-reply gửi quá nhiều câu sai hoặc bỏ qua quá nhiều câu đúng",
        "plan_required": "starter",
    },
}


# Settings > Moderation — tame spam/noise so AI focuses on real questions.
_MODERATION: dict[str, AllowedAction] = {
    "add_blocked_keyword": {
        "label": "Thêm từ khóa chặn comment",
        "navigation": "Cài đặt > Kiểm duyệt > mục 'Từ khóa chặn' > nhập từ > nút 'Thêm'",
        "when": "Khi có comment spam lặp lại với từ khóa cụ thể",
        "plan_required": "starter",
    },
    "adjust_emoji_threshold": {
        "label": "Chỉnh ngưỡng emoji spam",
        "navigation": "Cài đặt > Kiểm duyệt > slider 'Emoji threshold' (3-20)",
        "when": "Khi nhiều comment toàn emoji bị (hoặc không bị) lọc nhầm",
        "plan_required": "starter",
    },
    "review_flagged_comments": {
        "label": "Duyệt comment bị flag",
        "navigation": "Cài đặt > Kiểm duyệt > tab 'Comment cần kiểm duyệt' > Approve/Dismiss",
        "when": "Khi muốn approve hoặc reject comment đã bị moderation flag",
        "plan_required": "starter",
    },
    "toggle_spam_filter": {
        "label": "Bật/tắt auto-hide spam comments",
        "navigation": "Cài đặt > Kiểm duyệt > toggle 'Auto-hide spam'",
        "when": "Khi spam quá nhiều khiến AI lãng phí budget vào comment rác",
        "plan_required": "starter",
    },
    "toggle_llm_classify": {
        "label": "Bật AI phân loại các comment khó",
        "navigation": "Cài đặt > Kiểm duyệt > toggle 'AI classify uncertain'",
        "when": "Khi nhiều comment không rõ intent bị xếp nhầm vào 'khác'",
        "plan_required": "enterprise",
    },
}


# Chrome extension popup — only relevant before/at session start.
_EXTENSION: dict[str, AllowedAction] = {
    "select_persona_per_session": {
        "label": "Chọn persona trước khi bắt đầu session",
        "navigation": "Extension popup > dropdown 'Persona' > chọn > nút 'Bắt đầu'",
        "when": "Khi muốn dùng phong cách host khác cho session sắp tới",
        "plan_required": "starter",
    },
    "select_products_per_session": {
        "label": "Chọn sản phẩm đang bán cho session",
        "navigation": "Extension popup > checkbox sản phẩm (1-5) > nút 'Bắt đầu'",
        "when": "Khi vào session live, để AI biết tập trung vào sản phẩm nào",
        "plan_required": "starter",
    },
}


# Voices & Videos — AI generation surfaces (Pro+).
_MEDIA: dict[str, AllowedAction] = {
    "create_voice_clone": {
        "label": "Tạo voice clone giọng riêng",
        "navigation": "Cài đặt > Voice clones > nút 'Tạo voice mới' > upload audio + consent PDF",
        "when": "Khi shop muốn AI dùng giọng của chính mình thay vì giọng TTS mặc định",
        "plan_required": "pro",
    },
    "create_video_from_script": {
        "label": "Tạo video AI từ kịch bản",
        "navigation": "Videos > nút 'Tạo video mới' > chọn script + avatar + voice",
        "when": "Khi muốn nhân bản kịch bản thành video ngắn cho marketing ngoài live",
        "plan_required": "pro",
    },
}


# Single flat registry — assertion below guarantees no key collisions.
ALLOWED_ACTIONS: dict[str, AllowedAction] = {
    **_PRODUCTS,
    **_SCRIPTS,
    **_SESSIONS,
    **_MODERATION,
    **_EXTENSION,
    **_MEDIA,
}

# Build-time invariant: every key appears exactly once.
assert len(ALLOWED_ACTIONS) == sum(
    len(d) for d in (_PRODUCTS, _SCRIPTS, _SESSIONS, _MODERATION, _EXTENSION, _MEDIA)
), "Duplicate action key across allowed_actions sections"


_SECTION_ORDER: list[tuple[str, dict[str, AllowedAction]]] = [
    ("Sản phẩm", _PRODUCTS),
    ("Kịch bản", _SCRIPTS),
    ("Phiên live", _SESSIONS),
    ("Kiểm duyệt", _MODERATION),
    ("Extension popup", _EXTENSION),
    ("Voice & Video", _MEDIA),
]


# ────────────────────────────────────────────────────────────────────────────
# Public helpers
# ────────────────────────────────────────────────────────────────────────────


def _normalize_plan(shop_plan: str | None) -> int:
    """Map a shop's ``plan`` column to a numeric tier rank.

    Unknown plans default to ``starter`` rank — the safest assumption is
    that the user can do basic things but not advanced ones.
    """
    return _PLAN_RANK.get((shop_plan or "starter").lower(), _PLAN_RANK["starter"])


def get_allowed_actions_for_shop(
    shop_plan: str | None,
) -> dict[str, AllowedAction]:
    """Return the subset of actions a shop on ``shop_plan`` can perform.

    Trial → starter equivalent. Unknown plan → starter equivalent.
    """
    rank = _normalize_plan(shop_plan)
    return {
        key: action
        for key, action in ALLOWED_ACTIONS.items()
        if _PLAN_RANK[action["plan_required"]] <= rank
    }


def format_allowed_actions_for_prompt(shop_plan: str | None) -> str:
    """Render the allowed-action list as a Vietnamese bullet list grouped
    by dashboard page. Used inside the LLM prompt.

    Sections with zero actions for the given plan are omitted entirely so
    the LLM never sees an empty header.
    """
    rank = _normalize_plan(shop_plan)
    lines: list[str] = []
    for section_name, section in _SECTION_ORDER:
        section_lines = [
            f"  - [{key}] {action['label']}\n"
            f"      Đường dẫn: {action['navigation']}\n"
            f"      Khi nào dùng: {action['when']}"
            for key, action in section.items()
            if _PLAN_RANK[action["plan_required"]] <= rank
        ]
        if section_lines:
            lines.append(f"## {section_name}")
            lines.extend(section_lines)
            lines.append("")
    return "\n".join(lines).rstrip()
