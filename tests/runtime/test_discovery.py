from openagentic.runtime import discover_local_runtimes


def test_runtime_discovery_returns_safe_metadata(monkeypatch):
    monkeypatch.setenv("OPENAGENTIC_GPU", "cpu")
    runtimes = discover_local_runtimes()
    assert {runtime.name for runtime in runtimes} == {"ollama", "llama-server", "lmstudio"}
    assert all(runtime.hardware["gpu"] == "cpu" for runtime in runtimes)
