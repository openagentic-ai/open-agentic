"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # App
    app_name: str = "OpenAgentic"
    app_env: str = "development"
    app_port: int = 8000
    app_log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://openagentic:openagentic@postgres:5432/openagentic"

    # JWT Auth
    jwt_secret_key: str = "change-me-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # LLM
    litellm_default_model: str = "ollama/qwen3:14b"
    ollama_api_base: str = "http://localhost:11434"

    # File storage
    upload_dir: str = "/data/uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
