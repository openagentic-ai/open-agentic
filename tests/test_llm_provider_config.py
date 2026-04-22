"""Tests for persistent LLM provider config store."""

import tempfile

from openagentic.core.llm.provider_config import ProviderConfigStore


def test_provider_store_persists_updates():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = f"{tmpdir}/providers.json"
        store = ProviderConfigStore(path)
        initial = store.get()
        assert initial.profiles

        updated = store.upsert_profile(
            "deepseek",
            api_base="https://api.deepseek.com/v1",
            api_key="sk-test-12345678",
            models=["deepseek/deepseek-chat", "deepseek/deepseek-reasoner"],
            enabled=True,
        )
        assert any(p.id == "deepseek" and p.api_key for p in updated.profiles)

        reloaded = ProviderConfigStore(path).get()
        deepseek = next(p for p in reloaded.profiles if p.id == "deepseek")
        assert deepseek.api_base == "https://api.deepseek.com/v1"
        assert deepseek.models == ["deepseek/deepseek-chat", "deepseek/deepseek-reasoner"]


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

