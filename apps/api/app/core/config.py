from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/cohost_dev"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30

    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""

    embedding_model: str = "gemini-text-embedding-004"
    embedding_dimension: int = 768

    resend_api_key: str = ""
    email_from: str = "AI Co-host <noreply@aicohost.vn>"

    lemonsqueezy_api_key: str = ""
    lemonsqueezy_webhook_secret: str = ""
    lemonsqueezy_store_id: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""

    extension_id: str = ""

    sentry_dsn: str = ""

    model_config = {"env_file": "../../.env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()


def validate_production_settings() -> None:
    """Raise on dangerous defaults in non-development environments."""
    if settings.app_env == "development":
        return
    if settings.jwt_secret == "change-me-in-production":
        raise RuntimeError(
            "JWT_SECRET must be changed from default in production. "
            "Set the JWT_SECRET environment variable."
        )
    if not settings.google_client_id:
        import logging
        logging.getLogger(__name__).warning(
            "GOOGLE_CLIENT_ID not set — Google OAuth will return 503"
        )
