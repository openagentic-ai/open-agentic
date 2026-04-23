"""CLI provider aliases, resolution, and interactive provider configuration."""

from __future__ import annotations

import sys

import httpx

from openagentic.cli.platform_adapter import CLI_PLATFORM
from openagentic.config import SETTINGS
from openagentic.core.llm.provider_config import get_provider_store

DEFAULT_MODEL = SETTINGS.CLI_DEFAULT_MODEL

PROVIDER_ALIASES = {
    "claude": "anthropic",
    "anthropic": "anthropic",
    "openai": "openai",
    "grok": "xai",
    "xai": "xai",
    "gemini": "gemini",
    "deepseek": "deepseek",
    "mistral": "mistral",
    "cohere": "cohere",
    "groq": "groq",
    "openrouter": "openrouter",
    "kimi": "moonshot",
    "moonshot": "moonshot",
    "zhipu": "zhipu",
    "zhipuai": "zhipu",
    "glm": "zhipu",
    "minimax": "minimax",
    "doubao": "volcengine",
    "bytedance": "volcengine",
    "volcengine": "volcengine",
    "baidu": "baidu",
    "ernie": "baidu",
    "tencent": "tencent",
    "hunyuan": "tencent",
    "nvidia": "nvidia",
    "together": "together",
    "togetherai": "together",
    "fireworks": "fireworks",
    "qwen": "qwen",
    "ollama": "ollama",
}
KNOWN_PROVIDER_IDS = set(PROVIDER_ALIASES.values()) | {"openai"}
OPENAI_COMPATIBLE_PROVIDERS = {
    "groq",
    "openrouter",
    "moonshot",
    "zhipu",
    "minimax",
    "volcengine",
    "baidu",
    "tencent",
    "nvidia",
    "together",
    "fireworks",
}


def normalize_provider(provider: str) -> str:
    lower = provider.strip().lower()
    return PROVIDER_ALIASES.get(lower, lower)


def list_provider_profiles() -> list[dict]:
    config = get_provider_store().get()
    profiles = []
    for profile in config.profiles:
        profiles.append(
            {
                "id": profile.id,
                "display_name": profile.display_name,
                "api_base": profile.api_base,
                "api_key": profile.api_key,
                "models": profile.models,
                "enabled": profile.enabled,
            }
        )
    return profiles


def find_profile(provider: str) -> dict | None:
    provider = normalize_provider(provider)
    for profile in list_provider_profiles():
        if profile["id"] == provider:
            return profile
    return None


def resolve_provider(provider: str, model: str) -> str:
    if provider and provider != "auto":
        return normalize_provider(provider)
    if "/" in model:
        return normalize_provider(model.split("/", 1)[0])
    default_model = get_provider_store().get().default_model
    if "/" in default_model:
        return normalize_provider(default_model.split("/", 1)[0])
    return "ollama"


def resolve_model_for_provider(provider: str, model: str) -> str:
    profile = find_profile(provider)

    if model and model != DEFAULT_MODEL:
        candidate = model.strip()
        if "/" in candidate:
            parts = candidate.split("/")
            model_provider = normalize_provider(parts[0])
            if model_provider == provider:
                if len(parts) >= 3 and normalize_provider(parts[1]) in KNOWN_PROVIDER_IDS:
                    if profile and profile["models"]:
                        return profile["models"][0]
                    return get_provider_store().get().default_model
                return candidate
            if provider in OPENAI_COMPATIBLE_PROVIDERS:
                return candidate
            if profile and profile["models"]:
                return profile["models"][0]
            return get_provider_store().get().default_model
        if provider in OPENAI_COMPATIBLE_PROVIDERS:
            return f"openai/{candidate}"
        return f"{provider}/{candidate}"
    if profile and profile["models"]:
        return profile["models"][0]
    return get_provider_store().get().default_model


def normalize_runtime_model(provider: str, model_name: str) -> str:
    if "/" in model_name:
        return model_name
    if provider in OPENAI_COMPATIBLE_PROVIDERS:
        return f"openai/{model_name}"
    return f"{provider}/{model_name}"


def discover_models_openai_compatible(provider: str, api_base: str, api_key: str) -> list[str]:
    if not api_base or not api_key or provider == "ollama":
        return []
    endpoint = f"{api_base.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = httpx.get(endpoint, headers=headers, timeout=8.0)
        if response.status_code != 200:
            return []
        payload = response.json()
        raw_models = payload.get("data", [])
        ids: list[str] = []
        for item in raw_models:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id")
            if isinstance(model_id, str) and model_id.strip():
                ids.append(model_id.strip())

        seen: set[str] = set()
        normalized: list[str] = []
        for model_id in ids:
            runtime_model = normalize_runtime_model(provider, model_id)
            if runtime_model in seen:
                continue
            seen.add(runtime_model)
            normalized.append(runtime_model)
        return normalized
    except Exception:
        return []


def require_provider_configured(provider: str) -> tuple[str, str | None]:
    profile = find_profile(provider)
    if not profile:
        raise RuntimeError(f"Unknown provider: {provider}")
    if not profile["enabled"]:
        raise RuntimeError(f"Provider {provider} is disabled. Please enable it in config.")
    if provider != "ollama" and not profile["api_key"]:
        configure_provider_interactive(provider)
        profile = find_profile(provider)
        if not profile:
            raise RuntimeError(f"Unknown provider: {provider}")
    api_base = profile["api_base"] or None
    api_key = profile["api_key"] or None
    if provider != "ollama" and not api_key:
        raise RuntimeError(f"Provider {provider} requires API key before use.")
    return api_base or "", api_key


def print_provider_menu(current_provider: str) -> None:
    print("\n可选模型厂商：")
    for profile in list_provider_profiles():
        mark = "*" if profile["id"] == current_provider else " "
        status = "enabled" if profile["enabled"] else "disabled"
        key_status = "key:yes" if profile["api_key"] else "key:no"
        print(f" {mark} {profile['id']:<10} {profile['display_name']:<18} [{status}, {key_status}]")


def read_nav_key() -> str:
    return CLI_PLATFORM.read_nav_key()


def select_provider_interactive(current_provider: str) -> str | None:
    profiles = list_provider_profiles()
    if not profiles:
        return None
    ids = [p["id"] for p in profiles]
    selected_idx = ids.index(current_provider) if current_provider in ids else 0

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print_provider_menu(current_provider)
        selected = input(f"请选择 provider（默认 {current_provider}）: ").strip()
        return normalize_provider(selected) if selected else current_provider

    while True:
        CLI_PLATFORM.clear_screen()
        print("可选模型厂商（↑/↓ 选择，Enter 确认，q 取消）：")
        for idx, profile in enumerate(profiles):
            cursor = ">" if idx == selected_idx else " "
            status = "enabled" if profile["enabled"] else "disabled"
            key_status = "key:yes" if profile["api_key"] else "key:no"
            print(
                f" {cursor} {profile['id']:<12} {profile['display_name']:<24} "
                f"[{status}, {key_status}]"
            )

        key = read_nav_key()
        if key == "up":
            selected_idx = (selected_idx - 1) % len(profiles)
            continue
        if key == "down":
            selected_idx = (selected_idx + 1) % len(profiles)
            continue
        if key == "enter":
            return profiles[selected_idx]["id"]
        if key in {"quit", "interrupt"}:
            return None


def looks_like_api_key(value: str) -> bool:
    value = value.strip()
    if not value or " " in value:
        return False
    return value.startswith("sk-") or len(value) >= 24


def configure_provider_interactive(provider: str) -> None:
    provider = normalize_provider(provider)
    profile = find_profile(provider)
    if profile is None:
        print(f"[ERROR] 未找到 provider: {provider}")
        return
    print(f"\n--- 配置 {profile['display_name']} ({provider}) ---")
    print("提示：按回车采用默认项。")
    current_base = profile["api_base"] or ""
    current_models = ", ".join(profile["models"] or [])
    current_key = profile["api_key"] or ""

    api_key = ""
    if provider != "ollama":
        while True:
            hint = "（必填，无默认项）" if not current_key else "（默认：保持不变）"
            api_key = input(f"API Key{hint}: ").strip()
            if api_key:
                break
            if current_key:
                break
            print("[ERROR] 该 provider 需要 API Key，不能为空。")

    effective_key = api_key if api_key else current_key
    auto_models = profile["models"]
    if provider != "ollama":
        discovered = discover_models_openai_compatible(provider, current_base, effective_key)
        if discovered:
            auto_models = discovered
            print(f"[AUTO] 已探测到 {len(discovered)} 个模型。")
        else:
            print("[AUTO] 未探测到模型列表，使用内置默认模型。")

        quick = input("仅使用自动配置并保存? (Y/n): ").strip().lower()
        if quick in {"", "y", "yes"}:
            get_provider_store().upsert_profile(
                provider,
                api_base=current_base,
                api_key=effective_key or None,
                models=auto_models,
                enabled=True,
            )
            print(f"[OK] 已保存 {provider} 配置（自动模式）")
            return

    api_base_input = input(f"API Base [{current_base}]: ").strip()
    api_base = api_base_input or current_base

    if looks_like_api_key(api_base_input) and not api_key and provider != "ollama":
        api_key = api_base_input
        effective_key = api_key
        api_base = current_base
        print("[WARN] 检测到你把 API Key 填到了 API Base，已自动纠正。")

    models_input = input(f"模型列表(逗号分隔) [{current_models}]: ").strip()
    enabled_input = input(f"启用? (y/n) [{'y' if profile['enabled'] else 'n'}]: ").strip().lower()
    enabled = profile["enabled"] if enabled_input == "" else enabled_input in {"y", "yes", "1"}
    models = (
        [m.strip() for m in models_input.split(",") if m.strip()]
        if models_input
        else auto_models
    )
    get_provider_store().upsert_profile(
        provider,
        api_base=api_base,
        api_key=effective_key if effective_key else None,
        models=models,
        enabled=enabled,
    )
    print(f"[OK] 已保存 {provider} 配置")
