"""Tests for QuotaStatus logic."""

from app.services.usage import QuotaStatus


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
