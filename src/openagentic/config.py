"""模块说明（中文）：`src/openagentic/config.py`。\n\n该文件集中管理运行时配置与环境变量读取。\n"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # App
    APP_NAME: str = "OpenAgentic"
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    APP_LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://openagentic:openagentic@postgres:5432/openagentic"

    # JWT Auth
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    LITELLM_DEFAULT_MODEL: str = "ollama/qwen3:14b"
    OLLAMA_API_BASE: str = "http://localhost:11434"
    MODEL_PROVIDER_CONFIG_PATH: str = ".openagentic/model_providers.json"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_CHAT_MODEL: str = ""

    # CLI (`openagentic` ReAct：单条用户消息内「模型↔工具」最大轮数，防死循环)
    CLI_REACT_MAX_ITERATIONS: int = 1000
    CLI_DEFAULT_MODEL: str = "qwen3:14b"
    OPENAGENTIC_API_BASE: str = ""

    # CLI env-var override (like Claude Code's ANTHROPIC_* vars)
    OPENAGENTIC_BASE_URL: str = ""
    OPENAGENTIC_AUTH_TOKEN: str = ""
    OPENAGENTIC_MODEL: str = ""

    # File storage
    UPLOAD_DIR: str = "/data/uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


SETTINGS = Settings()
