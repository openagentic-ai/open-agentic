"""Test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from openagentic.main import app


@pytest.fixture
async def client():
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _never_call_real_jev(monkeypatch):
    """测试绝不真调 Jev——那是付费 API，而且会让测试结果依赖外网。

    需要 Jev 的测试自己注入 fake 客户端（见 tests/control_plane/test_jev.py）。
    """
    monkeypatch.setenv("OPENAGENTIC_JEV_ENABLED", "0")
