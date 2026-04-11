"""Tests for auth utility functions — password hashing and JWT tokens."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing")

import pytest

from app.auth.utils import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    get_token_expiry_seconds,
    hash_password,
    verify_password,
)


def test_hash_password_roundtrip():
    plain = "my-secure-password-123"
    try:
        hashed = hash_password(plain)
    except (ValueError, AttributeError):
        pytest.skip("passlib/bcrypt incompatibility on this Python version")
    assert hashed != plain
    assert verify_password(plain, hashed)


def test_verify_password_wrong():
    try:
        hashed = hash_password("correct-password")
    except (ValueError, AttributeError):
        pytest.skip("passlib/bcrypt incompatibility on this Python version")
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    token = create_access_token(user_id=42, shop_ids=[1, 2, 3])
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["shop_ids"] == [1, 2, 3]
    assert payload["type"] == "access"


def test_refresh_token_roundtrip():
    token = create_refresh_token(user_id=7)
    payload = decode_token(token)
    assert payload["sub"] == "7"
    assert payload["type"] == "refresh"
    assert "jti" in payload
    assert len(payload["jti"]) == 32  # uuid4 hex


def test_reset_token_roundtrip():
    token = create_reset_token(user_id=99)
    payload = decode_token(token)
    assert payload["sub"] == "99"
    assert payload["type"] == "reset"


def test_get_token_expiry_seconds():
    seconds = get_token_expiry_seconds()
    assert seconds > 0
    assert seconds == 60 * 60  # default 60 minutes
