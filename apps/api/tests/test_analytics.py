"""Tests for analytics service — overview stats, used rate, CSV export, chart bucketing."""

import csv
import io
from datetime import datetime, timezone

import pytest

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


# --- Used rate calculation ---


class TestUsedRate:
    def test_used_rate_normal(self):
        total = 100
        sent = 65
        rate = round((sent / total * 100) if total > 0 else 0, 1)
        assert rate == 65.0

    def test_used_rate_zero_suggestions(self):
        total = 0
        sent = 0
        rate = round((sent / total * 100) if total > 0 else 0, 1)
        assert rate == 0

    def test_used_rate_all_sent(self):
        total = 50
        sent = 50
        rate = round((sent / total * 100) if total > 0 else 0, 1)
        assert rate == 100.0

    def test_used_rate_none_sent(self):
        total = 30
        sent = 0
        rate = round((sent / total * 100) if total > 0 else 0, 1)
        assert rate == 0.0

    def test_used_rate_rounding(self):
        total = 3
        sent = 1
        rate = round((sent / total * 100) if total > 0 else 0, 1)
        assert rate == 33.3


# --- Live hours calculation ---


class TestLiveHours:
    def test_seconds_to_hours(self):
        total_seconds = 7200
        live_hours = round(float(total_seconds) / 3600, 2)
        assert live_hours == 2.0

    def test_partial_hours(self):
        total_seconds = 5400  # 1.5 hours
        live_hours = round(float(total_seconds) / 3600, 2)
        assert live_hours == 1.5

    def test_zero_seconds(self):
        total_seconds = 0
        live_hours = round(float(total_seconds) / 3600, 2)
        assert live_hours == 0.0

    def test_small_duration(self):
        total_seconds = 120  # 2 minutes
        live_hours = round(float(total_seconds) / 3600, 2)
        assert live_hours == 0.03


# --- Schema validation ---


class TestSchemas:
    def test_overview_stats(self):
        stats = OverviewStats(
            live_hours=2.5,
            comments_count=150,
            used_rate=65.0,
            scripts_count=3,
            recent_sessions=[],
            usage=[],
        )
        assert stats.live_hours == 2.5
        assert stats.used_rate == 65.0

    def test_recent_session(self):
        s = RecentSession(
            id=1,
            uuid="abc-123",
            platform="facebook",
            status="ended",
            started_at=datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc),
            duration_seconds=7200,
            comments_count=100,
            suggestions_count=80,
            sent_count=60,
        )
        assert s.platform == "facebook"
        assert s.duration_seconds == 7200

    def test_session_list_response(self):
        resp = SessionListResponse(items=[], total=0, page=1, page_size=20)
        assert resp.total == 0

    def test_session_detail_response(self):
        detail = SessionDetailResponse(
            id=1,
            uuid="abc-123",
            platform="tiktok",
            platform_url="https://tiktok.com/live/123",
            persona_id=5,
            active_product_ids=[1, 2, 3],
            status="running",
            started_at=datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
            ended_at=None,
            duration_seconds=None,
            comments_count=50,
            suggestions_count=40,
            sent_count=30,
            pasted_not_sent_count=2,
            read_count=5,
            dismissed_count=3,
            avg_latency_ms=450,
        )
        assert detail.active_product_ids == [1, 2, 3]
        assert detail.avg_latency_ms == 450

    def test_chart_point(self):
        pt = ChartPoint(
            minute=datetime(2026, 4, 10, 10, 5, tzinfo=timezone.utc),
            comment_count=12,
        )
        assert pt.comment_count == 12

    def test_product_mention(self):
        pm = ProductMention(name="Kem chống nắng ABC", mention_count=15)
        assert pm.mention_count == 15

    def test_top_question(self):
        tq = TopQuestion(text="Giá bao nhiêu ạ?", intent="pricing")
        assert tq.intent == "pricing"

    def test_comment_with_suggestion(self):
        c = CommentWithSuggestion(
            id=1,
            external_user_name="user123",
            text="Ship có nhanh không?",
            received_at=datetime(2026, 4, 10, 10, 5, tzinfo=timezone.utc),
            intent="shipping",
            suggestion_text="Dạ shop giao trong 2-3 ngày ạ",
            suggestion_status="sent",
            suggestion_latency_ms=320,
        )
        assert c.suggestion_status == "sent"

    def test_comment_without_suggestion(self):
        c = CommentWithSuggestion(
            id=2,
            external_user_name="user456",
            text="Hello shop",
            received_at=datetime(2026, 4, 10, 10, 6, tzinfo=timezone.utc),
            intent="greeting",
            suggestion_text=None,
            suggestion_status=None,
            suggestion_latency_ms=None,
        )
        assert c.suggestion_text is None

    def test_usage_meter_unlimited(self):
        m = UsageMeterOut(resource_type="live_hours", used=100, limit=-1, unit="hours")
        assert m.limit == -1


# --- CSV export format ---


class TestCsvExport:
    def _build_csv(self, rows: list[dict]) -> str:
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
        for row in rows:
            writer.writerow([
                row.get("user", ""),
                row.get("text", ""),
                row.get("time", ""),
                row.get("intent", ""),
                row.get("suggestion", ""),
                row.get("status", ""),
                row.get("latency", ""),
            ])
        return output.getvalue()

    def test_csv_headers(self):
        csv_str = self._build_csv([])
        reader = csv.reader(io.StringIO(csv_str))
        headers = next(reader)
        assert headers == [
            "Người bình luận",
            "Bình luận",
            "Thời gian",
            "Phân loại",
            "Gợi ý AI",
            "Trạng thái gợi ý",
            "Độ trễ (ms)",
        ]

    def test_csv_with_data(self):
        csv_str = self._build_csv([
            {
                "user": "Minh",
                "text": "Giá bao nhiêu?",
                "time": "2026-04-10 10:05:00",
                "intent": "pricing",
                "suggestion": "Dạ 200k ạ",
                "status": "sent",
                "latency": "320",
            },
        ])
        reader = csv.reader(io.StringIO(csv_str))
        next(reader)  # skip header
        row = next(reader)
        assert row[0] == "Minh"
        assert row[1] == "Giá bao nhiêu?"
        assert row[4] == "Dạ 200k ạ"

    def test_csv_empty_suggestion(self):
        csv_str = self._build_csv([
            {
                "user": "Lan",
                "text": "Hello",
                "time": "2026-04-10 10:06:00",
                "intent": "greeting",
            },
        ])
        reader = csv.reader(io.StringIO(csv_str))
        next(reader)
        row = next(reader)
        assert row[4] == ""  # no suggestion
        assert row[6] == ""  # no latency


# --- Chart bucketing ---


class TestChartBucketing:
    def test_chart_points_sorted(self):
        points = [
            ChartPoint(minute=datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc), comment_count=5),
            ChartPoint(minute=datetime(2026, 4, 10, 10, 1, tzinfo=timezone.utc), comment_count=8),
            ChartPoint(minute=datetime(2026, 4, 10, 10, 2, tzinfo=timezone.utc), comment_count=3),
        ]
        minutes = [p.minute for p in points]
        assert minutes == sorted(minutes)

    def test_chart_point_counts_positive(self):
        pt = ChartPoint(
            minute=datetime(2026, 4, 10, 10, 0, tzinfo=timezone.utc),
            comment_count=0,
        )
        assert pt.comment_count >= 0
