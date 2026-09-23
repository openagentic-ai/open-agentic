from openagentic.runtime import detect_hardware, discover_local_runtimes
from openagentic.runtime import RuntimeManager
import pytest


@pytest.mark.asyncio
async def test_runtime_manager_starts_and_stops_local_process():
    manager = RuntimeManager()
    await manager.start("demo", ("/bin/sh", "-c", "sleep 10"))
    await manager.stop("demo")


def test_runtime_discovery_returns_safe_metadata(monkeypatch):
    monkeypatch.setenv("OPENAGENTIC_GPU", "cpu")
    runtimes = discover_local_runtimes()
    assert {runtime.name for runtime in runtimes} == {"ollama", "llama-server", "lmstudio"}
    assert all(runtime.hardware["gpu"] == "cpu" for runtime in runtimes)


def test_hardware_detection_is_local(monkeypatch):
    monkeypatch.setenv("OPENAGENTIC_GPU", "cpu")
    result = detect_hardware()
    assert result["gpu"] == "cpu"
    assert int(result["cpu_count"]) > 0
