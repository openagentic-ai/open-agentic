"""Tests for persistent LLM provider config store."""

import tempfile

from openagentic.core.llm.provider_config import ProviderConfigStore


def test_provider_store_persists_updates(monkeypatch):
    # 清除环境变量避免 _apply_env_bootstrap 干扰二次加载
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_CHAT_MODEL"):
        monkeypatch.delenv(key, raising=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/providers.json"
        store = ProviderConfigStore(path)
        initial = store.get()
        assert initial.profiles

        updated = store.upsert_profile(
            "deepseek",
            api_base="https://api.deepseek.com/v1",
            api_key="sk-test-12345678",
            models=["deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"],
            enabled=True,
        )
        assert any(p.id == "deepseek" and p.api_key for p in updated.profiles)

        reloaded = ProviderConfigStore(path).get()
        deepseek = next(p for p in reloaded.profiles if p.id == "deepseek")
        assert deepseek.api_base == "https://api.deepseek.com/v1"
        assert deepseek.models == ["deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash"]


def test_resolve_runtime_uses_default_model_profile():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/providers.json"
        store = ProviderConfigStore(path)
        store.upsert_profile(
            "openai",
            api_base="https://api.openai.com/v1",
            api_key="sk-openai-abc12345",
            models=["openai/gpt-4.1"],
            enabled=True,
        )
        store.set_default_model("openai/gpt-4.1")
        model, api_base, api_key = store.resolve_runtime(None)
        assert model == "openai/gpt-4.1"
        assert api_base == "https://api.openai.com/v1"
        assert api_key == "sk-openai-abc12345"


def test_default_deepseek_profile_lists_pro_first(monkeypatch):
    # 清除环境变量避免 _apply_env_bootstrap 干扰
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_CHAT_MODEL"):
        monkeypatch.delenv(key, raising=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/providers.json"
        store = ProviderConfigStore(path)
        deepseek = next(p for p in store.get().profiles if p.id == "deepseek")
        assert deepseek.models[0] == "deepseek/deepseek-v4-pro"


def test_env_bootstrap_updates_stale_default_to_deepseek(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-deepseek-abc12345")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "deepseek-chat")
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/providers.json"
        store = ProviderConfigStore(path)
        cfg = store.get()
        assert cfg.default_model == "deepseek/deepseek-chat"
        deepseek = next(p for p in cfg.profiles if p.id == "deepseek")
        assert deepseek.api_key == "sk-deepseek-abc12345"
        assert deepseek.api_base == "https://api.deepseek.com/v1"


def test_resolve_runtime_ollama_profile_rewrites_openai_protocol(monkeypatch):
    """ollama profile 指向 OpenAI 兼容端点（Xinference）时，模型名重写为 openai/ 前缀"""
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_CHAT_MODEL", "OLLAMA_API_BASE"):
        monkeypatch.delenv(key, raising=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/providers.json"
        store = ProviderConfigStore(path)
        store.upsert_profile(
            "ollama",
            api_base="http://localhost:9997/v1",
            api_key="xf-local-key-12345678",
            models=["ollama/Qwen3.8-27B"],
            enabled=True,
        )
        model, api_base, api_key = store.resolve_runtime("ollama/Qwen3.8-27B")
        assert model == "openai/Qwen3.8-27B"
        assert api_base == "http://localhost:9997/v1"
        assert api_key == "xf-local-key-12345678"


def test_resolve_runtime_ollama_profile_keeps_non_ollama_model(monkeypatch):
    """非 ollama/ 前缀的模型名不被重写"""
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_CHAT_MODEL", "OLLAMA_API_BASE"):
        monkeypatch.delenv(key, raising=False)
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/providers.json"
        store = ProviderConfigStore(path)
        store.upsert_profile(
            "ollama",
            api_base="http://localhost:9997/v1",
            api_key="xf-local-key-12345678",
            models=["ollama/Qwen3.8-27B"],
            enabled=True,
        )
        model, api_base, api_key = store.resolve_runtime("openai/deepseek-v4-flash")
        assert model == "openai/deepseek-v4-flash"
        assert api_base == "https://api.openai.com/v1"
