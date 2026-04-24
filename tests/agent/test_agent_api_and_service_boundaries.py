"""Agent API and service boundary tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from openagentic.agent import service
from openagentic.agent.models import ExecutionStatus
from openagentic.db.session import get_db
from openagentic.deps import get_current_user
from openagentic.main import app


@pytest.fixture
async def agent_api_client(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4())
    now = datetime.now(timezone.utc)
    state = {"agents": {}, "executions": {}}

    async def fake_current_user():
        return user

    async def fake_db():
        yield object()

    async def list_agents(_db, user_id):
        return [a for a in state["agents"].values() if a.user_id == user_id]

    async def create_agent(_db, user_id, body):
        aid = uuid.uuid4()
        agent = SimpleNamespace(
            id=aid,
            user_id=user_id,
            name=body.name,
            description=body.description,
            system_prompt=body.system_prompt,
            model=body.model,
            tools=body.tools or [],
            config=body.config or {},
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        state["agents"][aid] = agent
        return agent

    async def get_agent(_db, agent_id, user_id):
        agent = state["agents"].get(agent_id)
        if agent and agent.user_id == user_id:
            return agent
        return None

    async def update_agent(_db, agent, body):
        patch = body.model_dump(exclude_unset=True)
        for k, v in patch.items():
            setattr(agent, k, v)
        return agent

    async def delete_agent(_db, agent):
        state["agents"].pop(agent.id, None)

    async def execute_agent(_db, agent, user_input):
        eid = uuid.uuid4()
        exe = SimpleNamespace(
            id=eid,
            agent_id=agent.id,
            status=ExecutionStatus.completed.value,
            input=user_input,
            output="ok",
            steps=[{"step": "final", "observation": "ok"}],
            token_total=0,
            started_at=now,
            completed_at=now,
        )
        state["executions"].setdefault(agent.id, []).append(exe)
        return exe

    async def list_executions(_db, agent_id):
        return state["executions"].get(agent_id, [])

    monkeypatch.setattr(service, "list_agents", list_agents)
    monkeypatch.setattr(service, "create_agent", create_agent)
    monkeypatch.setattr(service, "get_agent", get_agent)
    monkeypatch.setattr(service, "update_agent", update_agent)
    monkeypatch.setattr(service, "delete_agent", delete_agent)
    monkeypatch.setattr(service, "execute_agent", execute_agent)
    monkeypatch.setattr(service, "list_executions", list_executions)

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db] = fake_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_agent_api_crud_and_execute_flow(agent_api_client):
    client = agent_api_client

    create_resp = await client.post("/api/agents", json={"name": "demo-agent", "tools": ["echo"]})
    assert create_resp.status_code == 201
    agent_id = create_resp.json()["id"]

    list_resp = await client.get("/api/agents")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    patch_resp = await client.patch(f"/api/agents/{agent_id}", json={"name": "renamed"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "renamed"

    run_resp = await client.post(f"/api/agents/{agent_id}/execute", json={"input": "hello"})
    assert run_resp.status_code == 200
    assert run_resp.json()["status"] == "completed"

    executions_resp = await client.get(f"/api/agents/{agent_id}/executions")
    assert executions_resp.status_code == 200
    assert len(executions_resp.json()) == 1

    delete_resp = await client.delete(f"/api/agents/{agent_id}")
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_agent_execute_returns_404_for_missing_agent(agent_api_client):
    client = agent_api_client
    resp = await client.post(f"/api/agents/{uuid.uuid4()}/execute", json={"input": "hello"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Agent not found"


@pytest.mark.asyncio
async def test_list_executions_returns_404_for_missing_agent(agent_api_client):
    client = agent_api_client
    resp = await client.get(f"/api/agents/{uuid.uuid4()}/executions")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Agent not found"


@pytest.mark.asyncio
async def test_execute_agent_marks_failed_when_executor_raises(monkeypatch):
    captured = {"execution": None}

    class _FakeDB:
        def add(self, execution):
            captured["execution"] = execution

        async def flush(self):
            return None

    async def fake_run(_agent, _user_input):
        raise RuntimeError("tool crashed")

    monkeypatch.setattr(service.executor, "run", fake_run)
    agent = SimpleNamespace(id=uuid.uuid4(), user_id=uuid.uuid4())

    execution = await service.execute_agent(_FakeDB(), agent, "hello")
    assert execution.status == ExecutionStatus.failed
    assert execution.output == "执行失败，请查看错误信息。"
    assert execution.steps and execution.steps[0]["step"] == "error"
    assert "tool crashed" in execution.steps[0]["observation"]
