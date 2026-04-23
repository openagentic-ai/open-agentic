"""API integration tests for workflow routes."""

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from openagentic.db.session import get_db
from openagentic.deps import get_current_user
from openagentic.main import app
from openagentic.workflow import service
from openagentic.workflow.models import ExecutionStatus


@pytest.fixture
async def workflow_api_client(monkeypatch):
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id)
    state = {"workflows": {}, "runs": {}}

    async def fake_current_user():
        return user

    async def fake_db():
        yield object()

    now = datetime.now(timezone.utc)

    async def list_workflows(_db, uid):
        return [w for w in state["workflows"].values() if w.user_id == uid]

    async def create_workflow(_db, uid, body):
        wid = uuid.uuid4()
        wf = SimpleNamespace(
            id=wid,
            user_id=uid,
            name=body.name,
            description=body.description,
            definition=body.definition,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        state["workflows"][wid] = wf
        return wf

    async def get_workflow(_db, workflow_id, uid):
        wf = state["workflows"].get(workflow_id)
        if wf and wf.user_id == uid:
            return wf
        return None

    async def update_workflow(_db, workflow, body):
        patch = body.model_dump(exclude_unset=True)
        for k, v in patch.items():
            setattr(workflow, k, v)
        workflow.updated_at = datetime.now(timezone.utc)
        return workflow

    async def delete_workflow(_db, workflow):
        state["workflows"].pop(workflow.id, None)

    async def create_run(_db, workflow, input_data):
        run_id = uuid.uuid4()
        run = SimpleNamespace(
            id=run_id,
            workflow_id=workflow.id,
            user_id=workflow.user_id,
            status=ExecutionStatus.pending,
            input_data=input_data,
            output_data=None,
            node_states={},
            created_at=datetime.now(timezone.utc),
            started_at=None,
            completed_at=None,
            updated_at=datetime.now(timezone.utc),
        )
        state["runs"][run_id] = run
        return run

    async def execute_run(_db, run, _workflow):
        run.status = ExecutionStatus.completed
        run.started_at = datetime.now(timezone.utc)
        run.completed_at = datetime.now(timezone.utc)
        run.output_data = {"result": "ok"}
        run.node_states = {"trace": [{"node_id": "n1", "status": "success"}]}
        return run

    async def list_runs(_db, uid, workflow_id=None):
        runs = [r for r in state["runs"].values() if r.user_id == uid]
        if workflow_id:
            runs = [r for r in runs if r.workflow_id == workflow_id]
        return runs

    async def get_run(_db, run_id, uid):
        run = state["runs"].get(run_id)
        if run and run.user_id == uid:
            return run
        return None

    async def request_cancel(_db, run):
        run.node_states["_cancel_requested"] = True
        run.status = ExecutionStatus.cancelled
        return run

    monkeypatch.setattr(service, "list_workflows", list_workflows)
    monkeypatch.setattr(service, "create_workflow", create_workflow)
    monkeypatch.setattr(service, "get_workflow", get_workflow)
    monkeypatch.setattr(service, "update_workflow", update_workflow)
    monkeypatch.setattr(service, "delete_workflow", delete_workflow)
    monkeypatch.setattr(service, "create_run", create_run)
    monkeypatch.setattr(service, "execute_run", execute_run)
    monkeypatch.setattr(service, "list_runs", list_runs)
    monkeypatch.setattr(service, "get_run", get_run)
    monkeypatch.setattr(service, "request_cancel", request_cancel)

    app.dependency_overrides[get_current_user] = fake_current_user
    app.dependency_overrides[get_db] = fake_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_workflow_api_end_to_end(workflow_api_client):
    client = workflow_api_client
    definition = {
        "nodes": [{"id": "n1", "type": "value", "config": {"value": "ok"}}],
        "edges": [],
    }

    create_resp = await client.post(
        "/api/workflows",
        json={"name": "wf-demo", "description": "phase3 api test", "definition": definition},
    )
    assert create_resp.status_code == 201
    workflow_id = create_resp.json()["id"]

    list_resp = await client.get("/api/workflows")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    patch_resp = await client.patch(f"/api/workflows/{workflow_id}", json={"name": "wf-renamed"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "wf-renamed"

    run_resp = await client.post(
        f"/api/workflows/{workflow_id}/runs",
        json={"input_data": {"foo": "bar"}},
    )
    assert run_resp.status_code == 200
    run_payload = run_resp.json()
    run_id = run_payload["id"]
    assert run_payload["status"] == "completed"

    run_list_resp = await client.get(f"/api/workflow-runs?workflow_id={workflow_id}")
    assert run_list_resp.status_code == 200
    assert len(run_list_resp.json()) == 1

    cancel_resp = await client.post(f"/api/workflow-runs/{run_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_workflow_run_returns_404_when_workflow_missing(workflow_api_client):
    client = workflow_api_client
    resp = await client.post(
        f"/api/workflows/{uuid.uuid4()}/runs",
        json={"input_data": {"foo": "bar"}},
    )
    assert resp.status_code == 404

