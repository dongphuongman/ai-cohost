"""Tests for product schema HTML sanitization."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing")

from app.schemas.products import _strip_html, ProductCreate


def test_strip_html_removes_tags():
    assert _strip_html("<b>bold</b>") == "bold"
    assert _strip_html("<script>alert('xss')</script>") == "alert('xss')"


def test_strip_html_removes_javascript():
    assert "javascript:" not in _strip_html("javascript:alert(1)")


def test_strip_html_none():
    assert _strip_html(None) is None


def test_strip_html_clean_string():
    assert _strip_html("Hello World") == "Hello World"


def test_product_create_sanitizes_name():
    p = ProductCreate(name="<b>Test</b> Product")
    assert p.name == "Test Product"


def test_product_create_sanitizes_description():
    p = ProductCreate(name="OK", description="<script>xss</script>Clean")
    assert "<script>" not in p.description


def test_product_create_validates_price():
    p = ProductCreate(name="Test", price=0)
    assert p.price == 0
