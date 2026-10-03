"""Guard the user-required direction: business apps depend on the foundation."""

import ast
from pathlib import Path

import httpx
import pytest

from openagentic.main import create_app


def test_shared_agent_foundation_does_not_import_commerce_application():
    root = Path(__file__).resolve().parents[2] / "src" / "openagentic"
    forbidden = tuple(
        f"openagentic.{name}"
        for name in ("apps", "commerce", "merchants", "catalog", "integrations")
    )
    violations = []
    for area in ("agent", "application", "memory", "retrieval", "db", "tools"):
        for file in (root / area).rglob("*.py"):
            for node in ast.walk(ast.parse(file.read_text())):
                imports = (
                    [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else [item.name for item in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                if any(
                    name == prefix or name.startswith(prefix + ".")
                    for name in imports
                    for prefix in forbidden
                ):
                    violations.append(f"{file.relative_to(root)}:{node.lineno}")
    assert not violations, violations


@pytest.mark.asyncio
async def test_business_application_can_be_unmounted_without_removing_foundation():
    app = create_app(commerce_enabled=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/health")).json()["status"] == "ok"
        # 行为探测代替 app.routes 结构检查：FastAPI 0.14x 起路由装配是惰性的，
        # 创建后立即遍历 app.routes 看不到 include_router 注册的路由。
        assert (await client.post("/api/auth/login", json={})).status_code != 404
        assert (await client.get("/api/memory/vault")).status_code != 404
        assert (await client.get("/api/merchants")).status_code == 404
        assert (await client.post("/api/commerce/tools", json={})).status_code == 404
