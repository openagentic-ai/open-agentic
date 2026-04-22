"""Persistent provider configuration for multi-LLM support."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from openagentic.config import settings


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
        models=["deepseek/deepseek-chat", "deepseek/deepseek-reasoner"],
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
        api_base=settings.ollama_api_base,
        models=["ollama/qwen3:14b", "ollama/deepseek-r1:32b"],
    ),
]

DEFAULT_CONFIG = ProviderConfig(
    default_model=settings.litellm_default_model,
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
            return model_id, settings.ollama_api_base, None
        return model_id, None, None

    def _load(self) -> ProviderConfig:
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "default_model": DEFAULT_CONFIG.default_model,
                "profiles": [asdict(profile) for profile in DEFAULT_CONFIG.profiles],
            }
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return _clone_config(DEFAULT_CONFIG)
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            profiles = [ProviderProfile(**item) for item in data.get("profiles", [])]
            if not profiles:
                profiles = [ProviderProfile(**asdict(profile)) for profile in DEFAULT_PROFILES]
            return ProviderConfig(
                default_model=data.get("default_model", settings.litellm_default_model),
                profiles=profiles,
            )
        except (json.JSONDecodeError, OSError, TypeError):
            return _clone_config(DEFAULT_CONFIG)

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
        _store = ProviderConfigStore(settings.model_provider_config_path)
    return _store

