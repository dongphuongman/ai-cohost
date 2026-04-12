"""Quality tests for AI session insights.

These cover the parts that don't need a live DB or LLM:
- generic-insight detector
- format helpers (do they reference specific data?)
- coercion of LLM output (action_required for issues/suggestions)
- schema shape for the new InsightItem
"""

from datetime import datetime, timezone

import pytest

from app.schemas.analytics import InsightItem, SessionInsights
from app.services.insights.allowed_actions import (
    ALLOWED_ACTIONS,
    format_allowed_actions_for_prompt,
    get_allowed_actions_for_shop,
)
from app.services.session_insights import (
    FORBIDDEN_PHRASES,
    _coerce_items,
    _format_drops,
    _format_products,
    _format_repeated,
    _format_uncovered,
    _is_generic_insight,
    _validate_against_hallucination,
    validate_insight_actions,
)


# ────────────────────────────────────────────────────────────────────────────
# Generic detector — the heart of the quality bar.
# ────────────────────────────────────────────────────────────────────────────


class TestGenericDetector:
    def test_pure_generic_advice_rejected(self):
        item = InsightItem(
            title="Tăng tương tác",
            detail="Nên tăng cường tương tác và phản hồi nhanh để hỗ trợ tốt hơn",
            action="Tập trung vào khách",
        )
        assert _is_generic_insight(item) is True

    def test_specific_with_quoted_question_passes(self):
        item = InsightItem(
            title="8 khách hỏi giá combo cho LUVIBA LO46",
            detail='Có 8 khách hỏi "mua 2 cái có giảm giá không" cho Loa LUVIBA LO46',
            action="Vào Sản phẩm > LUVIBA LO46 > thêm field 'Giá combo'",
        )
        assert _is_generic_insight(item) is False

    def test_specific_with_numbers_passes(self):
        item = InsightItem(
            title="Phút 14:23 comments tụt 75%",
            detail="Comments giảm từ 32 xuống 8 đúng lúc chuyển sản phẩm",
            action="Thêm hook trước khi chuyển sản phẩm",
        )
        assert _is_generic_insight(item) is False

    def test_borderline_one_phrase_with_specifics_passes(self):
        # One soft generic phrase + concrete numbers = OK.
        item = InsightItem(
            title="Cải thiện coverage cho 12 comment",
            detail="12 comments không có gợi ý AI, intent='question'",
            action="Thêm 3 FAQ cho sản phẩm Fx799",
        )
        assert _is_generic_insight(item) is False

    def test_dict_input_supported(self):
        # Coercion path can call the detector before pydantic conversion.
        assert _is_generic_insight({
            "title": "Tăng tương tác và nâng cao chất lượng",
            "detail": "",
            "action": None,
        }) is True


# ────────────────────────────────────────────────────────────────────────────
# Coercion — action is required for issues/suggestions, optional for wins.
# ────────────────────────────────────────────────────────────────────────────


class TestCoerceItems:
    def test_action_required_drops_items_without_action(self):
        raw = [
            {"title": "ok", "detail": "12 comments uncovered", "action": "Thêm FAQ"},
            {"title": "no action", "detail": "stuff", "action": None},
            {"title": "no action 2", "detail": "more", "action": ""},
        ]
        items = _coerce_items(raw, action_required=True)
        assert len(items) == 1
        assert items[0].action == "Thêm FAQ"

    def test_action_optional_keeps_items_without_action(self):
        raw = [
            {"title": "win", "detail": "Sent rate 92%", "action": None},
            {"title": "win2", "detail": "Latency 800ms", "action": None},
        ]
        items = _coerce_items(raw, action_required=False)
        assert len(items) == 2
        assert all(item.action is None for item in items)

    def test_string_legacy_input_wrapped(self):
        # Tolerant fallback if LLM regresses to string array.
        items = _coerce_items(
            ["Comments tụt 75% phút 14:23"], action_required=False
        )
        assert len(items) == 1
        assert items[0].title
        assert items[0].detail

    def test_non_list_returns_empty(self):
        assert _coerce_items(None, action_required=True) == []
        assert _coerce_items("not a list", action_required=True) == []


# ────────────────────────────────────────────────────────────────────────────
# Format helpers — do they encode the specific signals the LLM needs?
# ────────────────────────────────────────────────────────────────────────────


class TestFormatHelpers:
    def test_uncovered_includes_text_and_count(self):
        s = _format_uncovered([
            {"text": "có ship COD không", "intent": "shipping", "freq": 4},
        ])
        assert "có ship COD không" in s
        assert "4 lần" in s

    def test_repeated_flags_missing_faq(self):
        s = _format_repeated([
            {
                "text": "Pin dùng được bao lâu",
                "intent": "question",
                "ask_count": 5,
                "has_suggestion": False,
            },
        ])
        assert "Pin dùng được bao lâu" in s
        assert "KHÔNG" in s  # has_suggestion False → KHÔNG

    def test_products_marks_data_gaps(self):
        s = _format_products([
            {
                "id": 1,
                "name": "Loa LUVIBA LO46",
                "mention_count": 28,
                "faq_count": 1,
                "has_price": False,
                "has_description": True,
                "has_highlights": False,
            },
        ])
        assert "Loa LUVIBA LO46" in s
        assert "28 lần" in s
        assert "THIẾU GIÁ" in s
        assert "THIẾU HIGHLIGHTS" in s
        assert "1 FAQ" in s

    def test_products_no_gaps_clean_output(self):
        s = _format_products([
            {
                "id": 1,
                "name": "Sản phẩm hoàn hảo",
                "mention_count": 5,
                "faq_count": 10,
                "has_price": True,
                "has_description": True,
                "has_highlights": True,
            },
        ])
        assert "[" not in s  # No gap brackets

    def test_drops_formats_minute_marker(self):
        s = _format_drops([
            {
                "minute": datetime(2026, 4, 12, 14, 23, tzinfo=timezone.utc),
                "before": 32,
                "after": 8,
            },
        ])
        assert "14:23" in s
        assert "32" in s
        assert "8" in s

    def test_empty_inputs_return_neutral_strings(self):
        # Each helper should return a non-empty placeholder so the prompt
        # field is never blank.
        for fn in (_format_uncovered, _format_repeated, _format_products, _format_drops):
            out = fn([])
            assert out
            assert out.startswith("(")


# ────────────────────────────────────────────────────────────────────────────
# Schema shape
# ────────────────────────────────────────────────────────────────────────────


class TestSessionInsightsSchema:
    def test_action_optional(self):
        item = InsightItem(title="t", detail="d")
        assert item.action is None

    def test_full_payload_roundtrip(self):
        payload = SessionInsights(
            positives=[InsightItem(title="t", detail="d")],
            improvements=[
                InsightItem(title="t", detail="d", action="step 1; step 2")
            ],
            suggestions=[],
            generated_at=datetime.now(timezone.utc),
            cached=False,
            warning=None,
        )
        dumped = payload.model_dump(mode="json")
        assert dumped["improvements"][0]["action"] == "step 1; step 2"
        assert dumped["warning"] is None


# ────────────────────────────────────────────────────────────────────────────
# Hallucination guard — make sure the validator catches features that
# don't exist in the dashboard, and only those.
# ────────────────────────────────────────────────────────────────────────────


class TestHallucinationValidator:
    @pytest.mark.parametrize("forbidden_action", [
        "Vào cài đặt AI > thêm intent 'greeting' và soạn câu trả lời",
        "Tạo intent mới cho complaint và thêm câu mẫu",
        "Soạn sẵn câu trả lời cho intent shipping",
        "Thiết lập workflow tự động trả lời khi có comment",
        "Tích hợp với Zalo để nhận thông báo",
        "Bật notification email khi có comment mới",
        "Tạo automation rule cho spam",
        "Vào AI settings để config",
    ])
    def test_validator_rejects_hallucinated_features(self, forbidden_action):
        item = InsightItem(
            title="Test",
            detail="Doesn't matter",
            action=forbidden_action,
        )
        violations = _validate_against_hallucination(item)
        assert violations, f"Should detect hallucination in: {forbidden_action!r}"

    @pytest.mark.parametrize("real_action", [
        "Bước 1: Vào Sản phẩm > Loa LUVIBA LO46 > tab 'FAQ' > nút 'Thêm FAQ'",
        "Cài đặt > Persona > đổi sang 'Năng động'",
        "Sản phẩm > Kem Victory > field 'Mô tả' > thêm thông tin combo",
        "Phiên live > session này > nút 'Xuất CSV'",
        "Cài đặt > Kiểm duyệt > mục 'Từ khóa chặn' > nhập 'mua hộ' > Thêm",
        "Kịch bản > nút 'Tạo script mới' > chọn 3 sản phẩm + persona",
        "Extension popup > checkbox sản phẩm > nút 'Bắt đầu'",
    ])
    def test_validator_accepts_real_actions(self, real_action):
        item = InsightItem(
            title="Test",
            detail="8 khách hỏi giá combo cho LUVIBA",
            action=real_action,
        )
        violations = _validate_against_hallucination(item)
        assert not violations, (
            f"Real action wrongly flagged: {real_action!r} "
            f"violations={violations}"
        )

    def test_top_level_validator_aggregates_by_section(self):
        clean = InsightItem(
            title="Clean",
            detail="8 questions about LUVIBA",
            action="Vào Sản phẩm > LUVIBA > tab 'FAQ' > nút 'Thêm FAQ'",
        )
        bad = InsightItem(
            title="Bad",
            detail="Has issues",
            action="Vào cài đặt AI > thêm intent greeting",
        )
        payload = SessionInsights(
            positives=[clean],
            improvements=[bad],
            suggestions=[],
            generated_at=datetime.now(timezone.utc),
        )
        ok, violations = validate_insight_actions(payload)
        assert ok is False
        # All violations should be from the improvements section.
        assert all(v["section"] == "improvements" for v in violations)
        assert all("Bad" in v["title"] for v in violations)

    def test_top_level_validator_accepts_clean_payload(self):
        payload = SessionInsights(
            positives=[InsightItem(
                title="Adoption rate 92%",
                detail="40/43 gợi ý đã được dùng",
                action=None,
            )],
            improvements=[InsightItem(
                title="LUVIBA thiếu FAQ combo",
                detail="8 câu hỏi 'mua 2 cái có giảm không' chưa được trả lời",
                action="Bước 1: Vào Sản phẩm > LUVIBA > tab 'FAQ' > nút 'Thêm FAQ'",
            )],
            suggestions=[],
            generated_at=datetime.now(timezone.utc),
        )
        ok, violations = validate_insight_actions(payload)
        assert ok is True
        assert violations == []

    def test_validator_handles_dict_input(self):
        # Robust to raw LLM output that hasn't been coerced yet.
        ok, violations = validate_insight_actions({
            "positives": [],
            "improvements": [{
                "title": "Bad",
                "detail": "Vào cài đặt AI thêm intent",
                "action": None,
            }],
            "suggestions": [],
        })
        assert ok is False
        assert violations[0]["section"] == "improvements"

    def test_forbidden_phrases_includes_core_hallucinations(self):
        # Regression guard — these were in the original incident report.
        # If someone removes them by accident, this test catches it.
        for required in ("thêm intent", "soạn sẵn câu trả lời", "tạo workflow"):
            assert required in FORBIDDEN_PHRASES


# ────────────────────────────────────────────────────────────────────────────
# Plan filtering — Starter shops must not see Pro/Enterprise actions in
# their prompt, otherwise the LLM can recommend features they can't use.
# ────────────────────────────────────────────────────────────────────────────


class TestAllowedActionsPlanFilter:
    def test_starter_excludes_pro_and_enterprise(self):
        starter = get_allowed_actions_for_shop("starter")
        # Pro features
        assert "create_voice_clone" not in starter
        assert "create_video_from_script" not in starter
        assert "add_product_faq_ai" not in starter
        assert "add_product_highlight_ai" not in starter
        assert "regenerate_script" not in starter
        assert "create_script_from_session" not in starter
        # Enterprise features
        assert "reindex_product" not in starter
        assert "toggle_llm_classify" not in starter
        # Basic features should be present
        assert "add_product" in starter
        assert "add_product_faq_manual" in starter
        assert "add_blocked_keyword" in starter

    def test_pro_excludes_enterprise_only(self):
        pro = get_allowed_actions_for_shop("pro")
        assert "create_voice_clone" in pro  # Pro feature
        assert "add_product_faq_ai" in pro  # Pro feature
        assert "reindex_product" not in pro  # Enterprise-only
        assert "toggle_llm_classify" not in pro  # Enterprise-only

    def test_enterprise_sees_everything(self):
        enterprise = get_allowed_actions_for_shop("enterprise")
        assert len(enterprise) == len(ALLOWED_ACTIONS)

    def test_trial_treated_as_starter(self):
        assert get_allowed_actions_for_shop("trial") == get_allowed_actions_for_shop("starter")

    def test_unknown_plan_falls_back_to_starter(self):
        assert get_allowed_actions_for_shop("mystery_tier") == get_allowed_actions_for_shop("starter")
        assert get_allowed_actions_for_shop(None) == get_allowed_actions_for_shop("starter")

    def test_plan_counts_match_design(self):
        # Locks in the 18/24/26 split agreed during prompt design. If you
        # add a new action, update this assertion AND document the tier.
        assert len(get_allowed_actions_for_shop("starter")) == 18
        assert len(get_allowed_actions_for_shop("pro")) == 24
        assert len(get_allowed_actions_for_shop("enterprise")) == 26

    def test_starter_prompt_renders_no_pro_actions(self):
        rendered = format_allowed_actions_for_prompt("starter")
        # No Pro/Enterprise action keys should appear in the rendered prompt
        # for a Starter shop.
        for key in (
            "create_voice_clone",
            "create_video_from_script",
            "add_product_faq_ai",
            "reindex_product",
            "toggle_llm_classify",
        ):
            assert key not in rendered, f"Starter prompt leaked Pro/Enterprise action: {key}"
        # Sanity: at least one Starter action should be there.
        assert "add_product_faq_manual" in rendered

    def test_pro_prompt_includes_pro_actions(self):
        rendered = format_allowed_actions_for_prompt("pro")
        assert "create_voice_clone" in rendered
        assert "add_product_faq_ai" in rendered
        # But not the Enterprise-only ones
        assert "reindex_product" not in rendered
        assert "toggle_llm_classify" not in rendered

    def test_every_action_has_required_fields(self):
        # Schema sanity — every entry has the four fields the prompt expects.
        for key, action in ALLOWED_ACTIONS.items():
            for field in ("label", "navigation", "when", "plan_required"):
                assert field in action, f"{key} missing {field}"
            assert action["plan_required"] in ("starter", "pro", "enterprise"), (
                f"{key} has unknown plan tier {action['plan_required']!r}"
            )
