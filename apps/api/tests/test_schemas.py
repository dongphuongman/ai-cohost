"""Tests for Pydantic schema validation."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import pytest
from pydantic import ValidationError

from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    SignupRequest,
    UpdateProfileRequest,
    VerifyEmailRequest,
)


def test_signup_valid():
    data = SignupRequest(email="test@example.com", password="12345678", full_name="Test User")
    assert data.email == "test@example.com"


def test_signup_short_password():
    with pytest.raises(ValidationError):
        SignupRequest(email="test@example.com", password="short", full_name="Test")


def test_signup_invalid_email():
    with pytest.raises(ValidationError):
        SignupRequest(email="not-an-email", password="12345678", full_name="Test")


def test_signup_empty_name():
    with pytest.raises(ValidationError):
        SignupRequest(email="test@example.com", password="12345678", full_name="")


def test_verify_email_otp_length():
    data = VerifyEmailRequest(user_id=1, otp="123456")
    assert data.otp == "123456"

    with pytest.raises(ValidationError):
        VerifyEmailRequest(user_id=1, otp="12345")  # too short

    with pytest.raises(ValidationError):
        VerifyEmailRequest(user_id=1, otp="1234567")  # too long


def test_change_password_min_length():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="old", new_password="short")


def test_update_profile_optional_fields():
    data = UpdateProfileRequest()
    assert data.full_name is None
    assert data.phone is None
    assert data.avatar_url is None

    data = UpdateProfileRequest(full_name="New Name")
    assert data.full_name == "New Name"
