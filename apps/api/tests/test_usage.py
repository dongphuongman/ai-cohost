"""Tests for QuotaStatus logic and effective-plan gating."""

import pytest

from app.schemas.billing import PLAN_LIMITS
from app.services.usage import QuotaStatus, _effective_plan


def test_quota_not_exceeded():
    q = QuotaStatus(used=5, limit=10, remaining=5)
    assert not q.exceeded


def test_quota_exceeded():
    q = QuotaStatus(used=10, limit=10, remaining=0)
    assert q.exceeded


def test_quota_over_limit():
    q = QuotaStatus(used=15, limit=10, remaining=-5)
    assert q.exceeded


def test_quota_unlimited():
    q = QuotaStatus(used=999, limit=-1, remaining=float("inf"))
    assert not q.exceeded


# --- _effective_plan: revenue-leak regression tests ---
#
# Regression for /cso finding #3 (2026-04-12): check_quota / check_seat_limit
# read Shop.plan without Shop.plan_status, so a past_due/cancelled Pro shop
# kept full Pro quota until a human downgraded them. Every failed Lemon
# Squeezy payment was silently donating paid-tier features. These tests
# encode the invariant: paid plan entitles quota iff plan_status is healthy.


class TestEffectivePlanHealthy:
    @pytest.mark.parametrize(
        "plan,plan_status",
        [
            ("pro", "active"),
            ("starter", "active"),
            ("enterprise", "active"),
            ("pro", "trialing"),
            ("pro", "on_trial"),
            ("trial", "active"),
        ],
    )
    def test_healthy_status_keeps_plan(self, plan, plan_status):
        assert _effective_plan(plan, plan_status) == plan


class TestEffectivePlanUnhealthy:
    @pytest.mark.parametrize(
        "plan_status",
        ["past_due", "cancelled", "unpaid", "expired", "paused", None, "", "unknown"],
    )
    def test_pro_with_unhealthy_status_collapses_to_trial(self, plan_status):
        # The core revenue-leak case: card declined, webhook set past_due,
        # shop.plan still says "pro". Quota must fall back to trial limits.
        assert _effective_plan("pro", plan_status) == "trial"

    @pytest.mark.parametrize("plan", ["starter", "pro", "enterprise"])
    def test_every_paid_plan_collapses_on_past_due(self, plan):
        assert _effective_plan(plan, "past_due") == "trial"

    def test_cancelled_pro_uses_trial_limits_not_pro_limits(self):
        # Concrete assertion against PLAN_LIMITS: a cancelled Pro shop gets
        # 10 scripts/month (trial), not unlimited (pro).
        effective = _effective_plan("pro", "cancelled")
        assert PLAN_LIMITS[effective]["scripts_per_month"] == 10
        assert PLAN_LIMITS["pro"]["scripts_per_month"] == -1


class TestEffectivePlanEdges:
    def test_unknown_plan_with_healthy_status_falls_back_to_trial(self):
        assert _effective_plan("legacy_gold", "active") == "trial"

    def test_none_plan_with_healthy_status_falls_back_to_trial(self):
        assert _effective_plan(None, "active") == "trial"

    def test_none_plan_with_unhealthy_status_falls_back_to_trial(self):
        assert _effective_plan(None, "past_due") == "trial"
