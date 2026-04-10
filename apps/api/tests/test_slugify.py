"""Tests for the slugify helpers."""

import re


def _slugify_auth(name: str) -> str:
    """Mirror of auth/service.py _slugify (without the user_id suffix)."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


def test_slugify_basic():
    assert _slugify_auth("My Shop Name") == "my-shop-name"


def test_slugify_special_chars():
    # Vietnamese chars match \w so they're preserved
    assert _slugify_auth("Café & Bánh") == "café-bánh"


def test_slugify_extra_spaces():
    assert _slugify_auth("  hello   world  ") == "hello-world"


def test_slugify_underscores():
    assert _slugify_auth("my_shop_name") == "my-shop-name"


def test_slugify_multiple_dashes():
    assert _slugify_auth("a---b") == "a-b"
