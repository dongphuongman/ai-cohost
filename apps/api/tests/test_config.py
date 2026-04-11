"""Tests for production settings validation and config utilities."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing")

import pytest
from unittest.mock import patch
from app.core.config import validate_production_settings, settings


def test_validate_production_skips_development():
    """In development mode, validation should pass even with defaults."""
    with patch.object(settings, "app_env", "development"):
        validate_production_settings()  # Should not raise


def test_validate_production_raises_on_default_jwt_secret():
    """In production, using the default JWT_SECRET must raise RuntimeError."""
    with patch.object(settings, "app_env", "production"), \
         patch.object(settings, "jwt_secret", "change-me-in-production"):
        with pytest.raises(RuntimeError, match="JWT_SECRET must be changed"):
            validate_production_settings()


def test_validate_production_warns_missing_google_client_id():
    """In production, missing google_client_id should warn but not raise."""
    with patch.object(settings, "app_env", "production"), \
         patch.object(settings, "jwt_secret", "a-real-secret"), \
         patch.object(settings, "google_client_id", ""):
        validate_production_settings()  # Should not raise, just warn


def test_validate_production_passes_with_all_configured():
    """With all settings configured, validation should pass silently."""
    with patch.object(settings, "app_env", "production"), \
         patch.object(settings, "jwt_secret", "a-real-secret"), \
         patch.object(settings, "google_client_id", "123456.apps.googleusercontent.com"):
        validate_production_settings()  # Should not raise
