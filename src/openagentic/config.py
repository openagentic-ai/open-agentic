"""模块说明（中文）：`src/openagentic/config.py`。\n\n该文件集中管理运行时配置与环境变量读取。\n"""

from pathlib import Path
import os
from typing import Any

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _load_yaml_config() -> dict[str, Any]:
    configured = os.getenv("OPENAGENTIC_CONFIG_PATH", "").strip()
    path = Path(configured) if configured else PROJECT_ROOT / "openagentic.yaml"
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

PRODUCT_CONFIG = _load_yaml_config()
MODEL_CONFIG = PRODUCT_CONFIG.get("models", {})

def configured_model(role: str, fallback: str = "") -> str:
    return str(MODEL_CONFIG.get(role, fallback) or fallback)

def configured_value(section: str, key: str, fallback: Any) -> Any:
    value = PRODUCT_CONFIG.get(section, {}).get(key, fallback)
    return fallback if value is None else value


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
    LITELLM_DEFAULT_MODEL: str = configured_model("default", "openai/deepseek-v4-flash")
    OLLAMA_API_BASE: str = "http://localhost:11434"
    MODEL_PROVIDER_CONFIG_PATH: str = ".openagentic/model_providers.json"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_CHAT_MODEL: str = ""

    # CLI (`openagentic` ReAct：单条用户消息内「模型↔工具」最大轮数，防死循环)
    CLI_REACT_MAX_ITERATIONS: int = 1000
    CLI_DEFAULT_MODEL: str = configured_model("cli", configured_model("default", "deepseek-v4-flash"))
    COMPLEX_MODEL: str = configured_model("complex", configured_model("default", "deepseek-v4-pro"))
    EVALUATOR_MODEL: str = configured_model("evaluator", configured_model("default", "deepseek-v4-flash"))
    CHANNEL_MODEL: str = configured_model("channel", configured_model("default", "deepseek-v4-flash"))
    EMBEDDING_MODEL: str = configured_model("embedding", "nomic-embed-text")
    LOCAL_MODEL: str = configured_model("local", "ollama/Qwen3.8-27B")
    LLM_TEMPERATURE: float = float(configured_value("llm", "temperature", 0.7))
    LLM_MAX_TOKENS: int | None = configured_value("llm", "max_tokens", None)
    LLM_REQUEST_TIMEOUT: float = float(configured_value("llm", "request_timeout_seconds", 180))
    AGENT_MAX_ITERATIONS: int = int(configured_value("agent", "max_iterations", 30))
    AGENT_MAX_VERIFY_RETRIES: int = int(configured_value("agent", "max_verify_retries", 1))
    CONTEXT_MAX_TOKENS: int = int(configured_value("context", "max_tokens", 80000))
    CONTEXT_TOOL_OUTPUT_MAX_CHARS: int = int(configured_value("context", "tool_output_max_chars", 4000))
    CONTEXT_KEEP_RECENT: int = int(configured_value("context", "keep_recent_messages", 10))
    MEMORY_MAX_TOKENS: int = int(configured_value("context", "working_memory_max_tokens", 6000))
    RETRIEVAL_CHUNK_SIZE: int = int(configured_value("retrieval", "chunk_size", 500))
    RETRIEVAL_CHUNK_OVERLAP: int = int(configured_value("retrieval", "chunk_overlap", 50))
    RETRIEVAL_TOP_K: int = int(configured_value("retrieval", "top_k", 5))
    RETRIEVAL_RERANK_TOP_N: int = int(configured_value("retrieval", "rerank_top_n", 20))
    CHANNEL_MAX_HISTORY: int = int(configured_value("channels", "max_history", 20))
    CHANNEL_TOOL_TIMEOUT: float = float(configured_value("channels", "tool_timeout_seconds", 30))
    CHANNEL_REPLY_TIMEOUT: float = float(configured_value("channels", "reply_timeout_seconds", 180))
    GATE_GLOBAL_CONCURRENCY: int = int(configured_value("concurrency", "global_concurrency", 100))
    GATE_MAX_QUEUED: int = int(configured_value("concurrency", "max_queued", 200))
    GATE_DEFAULT_TIMEOUT: float = float(configured_value("concurrency", "default_timeout_seconds", 180))
    GATE_LLM_CONCURRENCY: int = int(configured_value("concurrency", "llm_concurrency", 30))
    GATE_LLM_LOCAL_CONCURRENCY: int = int(configured_value("concurrency", "llm_local_concurrency", 2))
    GATE_SUBPROCESS_CONCURRENCY: int = int(configured_value("concurrency", "subprocess_concurrency", 10))
    GATE_IO_CONCURRENCY: int = int(configured_value("concurrency", "io_concurrency", 50))
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
