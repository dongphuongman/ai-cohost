from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/cohost_dev"

    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    deepseek_api_key: str = ""

    embedding_model: str = "gemini-text-embedding-004"
    embedding_dimension: int = 768

    model_config = {"env_file": "../../.env", "env_file_encoding": "utf-8"}


settings = WorkerSettings()
