"""模块说明（中文）：`src/openagentic/core/llm/provider_config.py`。\n\n该文件集中管理运行时配置与环境变量读取。\n"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from openagentic.config import SETTINGS


@dataclass
class ProviderProfile:
    id: str
    display_name: str
    api_base: str = ""
    api_key: str = ""
    models: list[str] = field(default_factory=list)
    enabled: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "api_base": self.api_base,
            "models": self.models,
            "enabled": self.enabled,
            "api_key_configured": bool(self.api_key),
            "api_key_masked": _mask_key(self.api_key),
        }


@dataclass
class ProviderConfig:
    default_model: str
    profiles: list[ProviderProfile]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "default_model": self.default_model,
            "profiles": [profile.to_public_dict() for profile in self.profiles],
        }


DEFAULT_PROFILES: list[ProviderProfile] = [
    ProviderProfile(
        id="openai",
        display_name="OpenAI",
        api_base="https://api.openai.com/v1",
        models=["openai/gpt-4.1", "openai/gpt-4.1-mini", "openai/gpt-4o-mini"],
    ),
    ProviderProfile(
        id="anthropic",
        display_name="Anthropic Claude",
        api_base="https://api.anthropic.com",
        models=["anthropic/claude-sonnet-4-20250514", "anthropic/claude-3-7-sonnet-latest"],
    ),
    ProviderProfile(
        id="xai",
        display_name="xAI Grok",
        api_base="https://api.x.ai/v1",
        models=["xai/grok-3-beta"],
    ),
    ProviderProfile(
        id="gemini",
        display_name="Google Gemini",
        api_base="https://generativelanguage.googleapis.com/v1beta/openai",
        models=["gemini/gemini-2.0-flash", "gemini/gemini-1.5-pro"],
    ),
    ProviderProfile(
        id="deepseek",
        display_name="DeepSeek",
        api_base="https://api.deepseek.com/v1",
        models=["deepseek/deepseek-reasoner", "deepseek/deepseek-chat"],
    ),
    ProviderProfile(
        id="mistral",
        display_name="Mistral AI",
        api_base="https://api.mistral.ai/v1",
        models=["mistral/mistral-large-latest", "mistral/mistral-medium-latest"],
    ),
    ProviderProfile(
        id="cohere",
        display_name="Cohere",
        api_base="https://api.cohere.com/v2",
        models=["cohere/command-r-plus", "cohere/command-r"],
    ),
    ProviderProfile(
        id="groq",
        display_name="Groq",
        api_base="https://api.groq.com/openai/v1",
        models=["openai/llama-3.3-70b-versatile", "openai/mixtral-8x7b-32768"],
    ),
    ProviderProfile(
        id="openrouter",
        display_name="OpenRouter",
        api_base="https://openrouter.ai/api/v1",
        models=["openai/openai/gpt-4o-mini", "openai/anthropic/claude-3.7-sonnet"],
    ),
    ProviderProfile(
        id="moonshot",
        display_name="Moonshot (Kimi)",
        api_base="https://api.moonshot.cn/v1",
        models=["openai/moonshot-v1-8k", "openai/moonshot-v1-128k"],
    ),
    ProviderProfile(
        id="zhipu",
        display_name="Zhipu AI (GLM)",
        api_base="https://open.bigmodel.cn/api/paas/v4",
        models=["openai/glm-4.5", "openai/glm-4.5-air"],
    ),
    ProviderProfile(
        id="minimax",
        display_name="MiniMax",
        api_base="https://api.minimax.chat/v1",
        models=["openai/minimax-m2", "openai/minimax-m2.5"],
    ),
    ProviderProfile(
        id="volcengine",
        display_name="ByteDance Volcengine (Doubao)",
        api_base="https://ark.cn-beijing.volces.com/api/v3",
        models=["openai/doubao-seed-1-6-thinking", "openai/doubao-pro-32k"],
    ),
    ProviderProfile(
        id="baidu",
        display_name="Baidu ERNIE",
        api_base="https://qianfan.baidubce.com/v2",
        models=["openai/ernie-4.0-8k", "openai/ernie-4.0-turbo-8k"],
    ),
    ProviderProfile(
        id="tencent",
        display_name="Tencent Hunyuan",
        api_base="https://api.hunyuan.cloud.tencent.com/v1",
        models=["openai/hunyuan-turbos-latest", "openai/hunyuan-large"],
    ),
    ProviderProfile(
        id="nvidia",
        display_name="NVIDIA NIM",
        api_base="https://integrate.api.nvidia.com/v1",
        models=["openai/meta/llama-3.1-70b-instruct", "openai/nvidia/llama-3.1-nemotron-70b-instruct"],
    ),
    ProviderProfile(
        id="together",
        display_name="Together AI",
        api_base="https://api.together.xyz/v1",
        models=["openai/meta-llama/Llama-3.3-70B-Instruct-Turbo", "openai/Qwen/Qwen2.5-72B-Instruct-Turbo"],
    ),
    ProviderProfile(
        id="fireworks",
        display_name="Fireworks AI",
        api_base="https://api.fireworks.ai/inference/v1",
        models=["openai/accounts/fireworks/models/llama-v3p3-70b-instruct", "openai/accounts/fireworks/models/qwen3-32b"],
    ),
    ProviderProfile(
        id="qwen",
        display_name="Qwen",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        models=["qwen/qwen-max", "qwen/qwen-plus", "qwen/qwen3-32b"],
    ),
    ProviderProfile(
        id="ollama",
        display_name="Ollama (local)",
        api_base=SETTINGS.OLLAMA_API_BASE,
        models=["ollama/qwen3:14b", "ollama/deepseek-r1:32b"],
    ),
]

DEFAULT_CONFIG = ProviderConfig(
    default_model=SETTINGS.LITELLM_DEFAULT_MODEL,
    profiles=DEFAULT_PROFILES,
)


def _mask_key(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _clone_config(config: ProviderConfig) -> ProviderConfig:
    return ProviderConfig(
        default_model=config.default_model,
        profiles=[ProviderProfile(**asdict(profile)) for profile in config.profiles],
    )


def _infer_provider_from_api_base(api_base: str) -> str:
    base = api_base.lower()
    if "openrouter.ai" in base:
        return "openrouter"
    if "mistral.ai" in base:
        return "mistral"
    if "cohere.com" in base:
        return "cohere"
    if "groq.com" in base:
        return "groq"
    if "moonshot.cn" in base:
        return "moonshot"
    if "bigmodel.cn" in base:
        return "zhipu"
    if "minimax.chat" in base:
        return "minimax"
    if "volces.com" in base:
        return "volcengine"
    if "baidubce.com" in base or "qianfan" in base:
        return "baidu"
    if "hunyuan" in base or "tencent" in base:
        return "tencent"
    if "nvidia.com" in base:
        return "nvidia"
    if "together.xyz" in base:
        return "together"
    if "fireworks.ai" in base:
        return "fireworks"
    if "deepseek" in base:
        return "deepseek"
    if "x.ai" in base or "grok" in base:
        return "xai"
    if "generativelanguage.googleapis.com" in base or "googleapis.com" in base:
        return "gemini"
    if "dashscope.aliyuncs.com" in base:
        return "qwen"
    if "anthropic" in base:
        return "anthropic"
    return "openai"


def _normalize_model(provider_id: str, model: str) -> str:
    if "/" in model:
        return model
    return f"{provider_id}/{model}"


def _apply_env_bootstrap(config: ProviderConfig) -> tuple[ProviderConfig, bool]:
    env_api_key = os.getenv("OPENAI_API_KEY", SETTINGS.OPENAI_API_KEY).strip()
    env_api_base = os.getenv("OPENAI_BASE_URL", SETTINGS.OPENAI_BASE_URL).strip()
    env_chat_model = os.getenv("OPENAI_CHAT_MODEL", SETTINGS.OPENAI_CHAT_MODEL).strip()
    if not (env_api_key or env_api_base or env_chat_model):
        return config, False

    provider_id = _infer_provider_from_api_base(env_api_base) if env_api_base else "openai"
    profiles_by_id = {p.id: p for p in config.profiles}
    profile = profiles_by_id.get(provider_id)
    changed = False
    if profile is None:
        profile = ProviderProfile(id=provider_id, display_name=provider_id.upper(), enabled=True)
        config.profiles.append(profile)
        changed = True

    if env_api_base and profile.api_base != env_api_base:
        profile.api_base = env_api_base
        changed = True
    if env_api_key and profile.api_key != env_api_key:
        profile.api_key = env_api_key
        changed = True
    if not profile.enabled:
        profile.enabled = True
        changed = True

    normalized_model = _normalize_model(provider_id, env_chat_model) if env_chat_model else ""
    if normalized_model:
        if normalized_model not in profile.models:
            profile.models.insert(0, normalized_model)
            changed = True
        # Upgrade stale default from initial ollama or empty state.
        if (
            config.default_model == DEFAULT_CONFIG.default_model
            or config.default_model.startswith("ollama/")
            or config.default_model == ""
        ) and config.default_model != normalized_model:
            config.default_model = normalized_model
            changed = True

    return config, changed


class ProviderConfigStore:
    """JSON-file backed store for provider profiles."""

    def __init__(self, path: str) -> None:
        raw_path = Path(path)
        self.path = raw_path if raw_path.is_absolute() else Path.cwd() / raw_path
        self._lock = threading.Lock()
        self._config = self._load()

    def get(self) -> ProviderConfig:
        with self._lock:
            return _clone_config(self._config)

    def set_default_model(self, model: str) -> ProviderConfig:
        with self._lock:
            self._config.default_model = model
            self._save_unlocked()
            return _clone_config(self._config)

    def upsert_profile(
        self,
        profile_id: str,
        *,
        display_name: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        models: list[str] | None = None,
        enabled: bool | None = None,
    ) -> ProviderConfig:
        with self._lock:
            profiles = self._config.profiles
            profile = next((p for p in profiles if p.id == profile_id), None)
            if profile is None:
                profile = ProviderProfile(id=profile_id, display_name=display_name or profile_id.upper())
                profiles.append(profile)
            if display_name is not None:
                profile.display_name = display_name
            if api_base is not None:
                profile.api_base = api_base
            if api_key is not None:
                profile.api_key = api_key
            if models is not None:
                profile.models = models
            if enabled is not None:
                profile.enabled = enabled
            self._save_unlocked()
            return _clone_config(self._config)

    def resolve_runtime(self, model: str | None) -> tuple[str, str | None, str | None]:
        cfg = self.get()
        model_id = model or cfg.default_model
        provider_id = model_id.split("/")[0] if "/" in model_id else ""
        profile = next((p for p in cfg.profiles if p.id == provider_id and p.enabled), None)
        if profile:
            api_base = profile.api_base or None
            api_key = profile.api_key or None
            return model_id, api_base, api_key
        if model_id.startswith("ollama/"):
            return model_id, SETTINGS.OLLAMA_API_BASE, None
        return model_id, None, None

    def _load(self) -> ProviderConfig:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            cfg = _clone_config(DEFAULT_CONFIG)
            cfg, _ = _apply_env_bootstrap(cfg)
            data = {
                "default_model": cfg.default_model,
                "profiles": [asdict(profile) for profile in cfg.profiles],
            }
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return cfg
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            profiles = [ProviderProfile(**item) for item in data.get("profiles", [])]
            if not profiles:
                profiles = [ProviderProfile(**asdict(profile)) for profile in DEFAULT_PROFILES]
            cfg = ProviderConfig(
                default_model=data.get("default_model", SETTINGS.LITELLM_DEFAULT_MODEL),
                profiles=profiles,
            )
            cfg, changed = _apply_env_bootstrap(cfg)
            if changed:
                data = {
                    "default_model": cfg.default_model,
                    "profiles": [asdict(profile) for profile in cfg.profiles],
                }
                self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return cfg
        except (json.JSONDecodeError, OSError, TypeError):
            cfg = _clone_config(DEFAULT_CONFIG)
            cfg, _ = _apply_env_bootstrap(cfg)
            return cfg

    def _save_unlocked(self) -> None:
        data = {
            "default_model": self._config.default_model,
            "profiles": [asdict(profile) for profile in self._config.profiles],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


_store: ProviderConfigStore | None = None


def get_provider_store() -> ProviderConfigStore:
    global _store
    if _store is None:
        _store = ProviderConfigStore(SETTINGS.MODEL_PROVIDER_CONFIG_PATH)
    return _store

