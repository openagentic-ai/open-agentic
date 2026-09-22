"""模块说明（中文）：`src/openagentic/config.py`。\n\n该文件集中管理运行时配置与环境变量读取。\n"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


def load_env_file(path: str | Path | None = None) -> None:
    """把 `.env` 写回 `os.environ`。

    pydantic 的 `env_file` 只把值读进 Settings 对象，**不写回进程环境**；
    而控制面 / Jev 这些按「环境变量激活」设计的模块读的是 `os.environ`——
    不写回就意味着它们静默不启用（2026-09-23 实际踩到：控制面代码正确、
    测试全绿，但线上根本没激活）。

    `override=False`：已存在的环境变量优先，systemd `EnvironmentFile` 与
    CLI 显式传入的值不该被 `.env` 覆盖。文件缺失/非法静默忽略。
    """
    try:
        load_dotenv(path, override=False)
    except Exception:  # nosec B110 — .env 缺失/非法不得影响应用启动
        pass


# 模块导入即生效——任何 import openagentic.config 的入口都拿到完整环境
load_env_file()


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

    # LLM (LiteLLM 统一网关，任意 provider 改 .env 即切)
    LITELLM_DEFAULT_MODEL: str = "openai/deepseek-v4-flash"
    OLLAMA_API_BASE: str = "http://localhost:11434"
    MODEL_PROVIDER_CONFIG_PATH: str = ".openagentic/model_providers.json"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_CHAT_MODEL: str = ""

    # CLI (`openagentic` ReAct：单条用户消息内「模型↔工具」最大轮数，防死循环)
    CLI_REACT_MAX_ITERATIONS: int = 1000
    CLI_DEFAULT_MODEL: str = "deepseek-v4-flash"
    OPENAGENTIC_API_BASE: str = ""

    # CLI env-var override (like Claude Code's ANTHROPIC_* vars)
    OPENAGENTIC_BASE_URL: str = ""
    OPENAGENTIC_AUTH_TOKEN: str = ""
    OPENAGENTIC_MODEL: str = ""
    # 跳过启动时强制 provider 配置向导（用于 CI/demo/批量测试）
    OPENAGENTIC_SKIP_PROVIDER_CHECK: bool = False

    # File storage
    UPLOAD_DIR: str = "/data/uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


SETTINGS = Settings()
