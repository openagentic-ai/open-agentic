"""Offline integration tests: real auth and SQL, injected Agent and SaaS transport."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from tests.merchants.test_merchant_catalog import (
    commerce_client as commerce_client_fixture,
    booking_setup,
)

from openagentic.commerce.access import CommerceActor
from openagentic.commerce.client import CommerceAgentClient
from openagentic.commerce.engine import build_commerce_engine
from openagentic.commerce.platform_models import AgentGrant, PriceQuote
from openagentic.core.auth.models import User
from openagentic.core.auth.service import create_access_token, create_refresh_token, decode_token
from openagentic.db.session import get_db
from openagentic.integrations.merchant_api import HttpMerchantAdapter, LocalMerchantAdapter


commerce_client = commerce_client_fixture


def database(client):
    return client._transport.app.dependency_overrides[get_db]()


async def quote(client, buyer, sid):
    response = await client.post(
        "/api/commerce/tools/quote_service", headers=buyer, json={"arguments": {"service_id": sid}}
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.asyncio
async def test_delegated_agent_scopes_isolation_and_revoke(commerce_client):
    c = commerce_client
    owner, buyer, stranger, mid, sid, body = await booking_setup(c)
    granted = await c.post(
        "/api/commerce/agent-grants",
        headers=buyer,
        json={
            "name": "Independent Agent",
            "scopes": ["services:read", "quotes:write"],
            "expires_days": 1,
        },
    )
    assert granted.status_code == 201, granted.text
    grant = granted.json()
    agent = {"Authorization": "Bearer " + grant["token"]}
    listed = (await c.get("/api/commerce/agent-grants", headers=buyer)).json()
    assert "token" not in listed[0] and "token_hash" not in listed[0]
    async for db in database(c):
        stored = await db.get(AgentGrant, UUID(grant["id"]))
        assert stored.token_hash != grant["token"] and len(stored.token_hash) == 64
    sdk_http = httpx.AsyncClient(transport=c._transport, base_url="http://test", headers=agent)
    async with sdk_http:
        sdk = CommerceAgentClient(sdk_http)
        manifest = await sdk.manifest()
        assert {t["function"]["name"] for t in manifest["tools"]} == {
            "find_services",
            "quote_service",
        }
        found = await sdk.find_services("空调", "杭州")
        assert found[0]["id"] == sid
        q = await sdk.quote_service(sid)
        assert q["requires_user_confirmation"] and q["confirmation_path"].endswith(q["id"])
    confirmation = {
        key: body[key]
        for key in ("preferred_at", "customer_name", "customer_phone", "note", "confirmed")
    }
    assert (
        await c.post(f"/api/commerce/quotes/{q['id']}/confirm", headers=agent, json=confirmation)
    ).status_code == 401
    assert (
        await c.post(f"/api/commerce/quotes/{q['id']}/confirm", headers=stranger, json=confirmation)
    ).status_code == 404
    assert (
        await c.post(
            "/api/commerce/tools/get_order",
            headers=agent,
            json={"arguments": {"order_id": str(uuid4())}},
        )
    ).status_code == 403
    assert (
        await c.post(
            "/api/commerce/tools/find_services",
            headers=agent,
            json={"arguments": {"user_id": str(uuid4())}},
        )
    ).status_code == 422
    order = await c.post(
        f"/api/commerce/quotes/{q['id']}/confirm", headers=buyer, json=confirmation
    )
    assert order.status_code == 200, order.text
    repeat = await c.post(
        f"/api/commerce/quotes/{q['id']}/confirm", headers=buyer, json=confirmation
    )
    assert repeat.json()["id"] == order.json()["id"]
    assert len((await c.get("/api/orders", headers=buyer)).json()) == 1
    assert (
        await c.delete(f"/api/commerce/agent-grants/{grant['id']}", headers=stranger)
    ).status_code == 404
    assert (
        await c.delete(f"/api/commerce/agent-grants/{grant['id']}", headers=buyer)
    ).status_code == 200
    assert (await c.get("/api/commerce/tools", headers=agent)).status_code == 401
    audits = (await c.get("/api/commerce/tool-audits", headers=buyer)).json()
    assert {a["status_code"] for a in audits} >= {200, 403, 422}
    assert all("arguments" not in a for a in audits)
    assert (await c.get("/api/commerce/tool-audits", headers=stranger)).json() == []


@pytest.mark.asyncio
async def test_quote_expiry_changes_confirmation_and_replay(commerce_client):
    c = commerce_client
    owner, buyer, _, mid, sid, body = await booking_setup(c)
    q = await quote(c, buyer, sid)
    payload = {
        key: body[key]
        for key in ("preferred_at", "customer_name", "customer_phone", "note", "confirmed")
    }
    assert (
        await c.post(
            f"/api/commerce/quotes/{q['id']}/confirm",
            headers=buyer,
            json={**payload, "confirmed": False},
        )
    ).status_code == 422
    async for db in database(c):
        row = await db.get(PriceQuote, UUID(q["id"]))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
    assert (
        await c.post(f"/api/commerce/quotes/{q['id']}/confirm", headers=buyer, json=payload)
    ).status_code == 409
    q = await quote(c, buyer, sid)
    service = (await c.get(f"/api/merchants/{mid}/services", headers=owner)).json()[0]
    fields = (
        "name",
        "description",
        "price_fen",
        "duration_minutes",
        "availability_note",
        "is_published",
    )
    updated = {key: service[key] for key in fields}
    updated["duration_minutes"] += 10
    assert (
        await c.put(f"/api/merchants/{mid}/services/{sid}", headers=owner, json=updated)
    ).status_code == 200
    assert (
        await c.post(f"/api/commerce/quotes/{q['id']}/confirm", headers=buyer, json=payload)
    ).status_code == 409
    q = await quote(c, buyer, sid)
    first = await c.post(f"/api/commerce/quotes/{q['id']}/confirm", headers=buyer, json=payload)
    assert first.status_code == 200
    async for db in database(c):
        row = await db.get(PriceQuote, UUID(q["id"]))
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await db.commit()
    retry = await c.post(f"/api/commerce/quotes/{q['id']}/confirm", headers=buyer, json=payload)
    assert retry.json()["id"] == first.json()["id"]
    assert (
        await c.post(
            f"/api/commerce/quotes/{q['id']}/confirm",
            headers=buyer,
            json={**payload, "note": "changed"},
        )
    ).status_code == 409


@pytest.mark.asyncio
async def test_engine_uses_actor_bound_tools_without_network(commerce_client, monkeypatch):
    c = commerce_client
    _, buyer, stranger, _, sid, _ = await booking_setup(c)
    await c.post(
        "/api/memory/procedures",
        headers=buyer,
        json={
            "name": "帮我找杭州的空调清洗",
            "description": "本账号独有流程",
            "trigger_pattern": "空调",
            "steps": ["用户确认后再提交预约"],
        },
    )
    await c.post(
        "/api/memory/procedures",
        headers=stranger,
        json={
            "name": "帮我找杭州的空调清洗",
            "description": "其他账号私有流程",
            "trigger_pattern": "空调",
            "steps": ["不得泄漏的客户资料"],
        },
    )
    mocked_llm = AsyncMock(
        side_effect=[
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call1",
                            "type": "function",
                            "function": {
                                "name": "find_services",
                                "arguments": json.dumps({"q": "空调", "region": "杭州"}),
                            },
                        }
                    ]
                }
            },
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call2",
                            "type": "function",
                            "function": {
                                "name": "quote_service",
                                "arguments": json.dumps({"service_id": sid}),
                            },
                        }
                    ]
                }
            },
            {"message": {"content": "已准备报价，请用户打开确认页面。"}},
        ]
    )
    monkeypatch.setattr("openagentic.agent.engine.litellm_chat", mocked_llm)
    user_id = decode_token(buyer["Authorization"].split(" ")[1])["sub"]
    async for db in database(c):
        actor = CommerceActor(await db.get(User, UUID(user_id)))
        engine = build_commerce_engine(db, actor, model="offline-test", api_key="unused")
        messages = [{"role": "user", "content": "帮我找杭州的空调清洗"}]
        result = await engine.chat(messages)
        assert result == "已准备报价，请用户打开确认页面。"
        tool_results = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        assert tool_results[0][0]["id"] == sid
        assert tool_results[1]["requires_user_confirmation"]
        assert (await db.scalars(select(PriceQuote))).first() is not None
    assert (await c.get("/api/orders", headers=buyer)).json() == []
    assert mocked_llm.await_count == 3
    assert "本账号独有流程" in messages[0]["content"]
    assert "其他账号私有流程" not in messages[0]["content"]


@pytest.mark.asyncio
async def test_refresh_malformed_and_expired_agent_tokens_rejected(commerce_client):
    c = commerce_client
    _, buyer, _, _, _, _ = await booking_setup(c)
    uid = decode_token(buyer["Authorization"].split(" ")[1])["sub"]
    refresh = create_refresh_token(uid)
    invalid, _ = create_access_token("not-a-uuid")
    for token in (refresh, invalid):
        assert (
            await c.get("/api/commerce/agent-grants", headers={"Authorization": "Bearer " + token})
        ).status_code == 401
    g = (
        await c.post(
            "/api/commerce/agent-grants",
            headers=buyer,
            json={"name": "expired", "scopes": ["services:read"]},
        )
    ).json()
    async for db in database(c):
        row = await db.get(AgentGrant, UUID(g["id"]))
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
    assert (
        await c.get("/api/commerce/tools", headers={"Authorization": "Bearer " + g["token"]})
    ).status_code == 401


@pytest.mark.asyncio
async def test_saas_import_upsert_tenant_boundary_and_duplicate_ids(commerce_client):
    c = commerce_client
    owner, _, stranger, mid, _, _ = await booking_setup(c)
    data = (await c.get("/api/commerce/integrations/example")).json()
    assert data["mode"] == "local-example"
    catalog = data["catalog"]
    endpoint = f"/api/merchants/{mid}/integrations/catalog"
    assert (await c.post(endpoint, headers=stranger, json=catalog)).status_code == 404
    first = (await c.post(endpoint, headers=owner, json=catalog)).json()
    catalog["services"][0]["price_fen"] = 12000
    second = (await c.post(endpoint, headers=owner, json=catalog)).json()
    assert first["updated"] == second["updated"]
    services = (await c.get(f"/api/merchants/{mid}/services", headers=owner)).json()
    imported = [s for s in services if s["id"] == first["updated"][0]["service_id"]]
    assert (
        len(imported) == 1 and imported[0]["price_fen"] == 12000 and not imported[0]["is_published"]
    )
    assert len((await c.get(f"/api/catalog/storefronts/{mid}")).json()["services"]) == 1
    catalog["services"] *= 2
    assert (await c.post(endpoint, headers=owner, json=catalog)).status_code == 422


@pytest.mark.asyncio
async def test_http_merchant_contract_uses_mock_transport_and_idempotency():
    catalog = (await LocalMerchantAdapter().catalog()).model_dump()
    oid = str(uuid4())
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/catalog":
            return httpx.Response(200, json=catalog)
        assert request.headers["idempotency-key"] == oid
        return httpx.Response(200, json={"order_id": oid, "status": "pending"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = HttpMerchantAdapter(client, "http://offline-merchant")
        assert (await adapter.catalog()).system == "local-example"
        assert (await adapter.submit_order({"id": oid}))["order_id"] == oid
    assert len(calls) == 2
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"order_id": "wrong"}))
    ) as client:
        with pytest.raises(ValueError):
            await HttpMerchantAdapter(client, "http://offline").submit_order({"id": oid})


@pytest.mark.asyncio
async def test_persistent_delivery_retry_dedup_and_isolation(commerce_client):
    c = commerce_client
    owner, buyer, stranger, mid, _, body = await booking_setup(c)
    order = (await c.post("/api/orders", headers=buyer, json=body)).json()
    oid = order["id"]
    enqueue = f"/api/merchants/{mid}/integrations/orders/{oid}"
    assert (await c.post(enqueue, headers=owner, json={"system": "test-saas"})).status_code == 409
    await c.post(
        f"/api/merchants/{mid}/orders/{oid}/status", headers=owner, json={"status": "accepted"}
    )
    record = (await c.post(enqueue, headers=owner, json={"system": "test-saas"})).json()
    repeat = (await c.post(enqueue, headers=owner, json={"system": "test-saas"})).json()
    assert repeat["id"] == record["id"]
    adapter = LocalMerchantAdapter()
    adapter.submit_order = AsyncMock(
        side_effect=[
            httpx.ConnectError("sensitive vendor error"),
            {"order_id": oid, "status": "accepted"},
        ]
    )
    c._transport.app.state.merchant_adapters = {(mid, "test-saas"): adapter}
    retry = f"/api/merchants/{mid}/integrations/deliveries/{record['id']}/retry"
    assert (await c.post(retry, headers=stranger)).status_code == 404
    failed = (await c.post(retry, headers=owner)).json()
    assert failed["status"] == "failed" and "sensitive" not in failed["error"]
    sent = (await c.post(retry, headers=owner)).json()
    assert sent["status"] == "delivered" and sent["attempts"] == 2
    assert (await c.post(retry, headers=owner)).json()["attempts"] == 2
    assert adapter.submit_order.await_count == 2
    assert (await c.get(f"/api/orders/{oid}", headers=buyer)).json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_finance_confirm_fees_refund_and_authorization(commerce_client, monkeypatch):
    c = commerce_client
    owner, buyer, stranger, mid, _, body = await booking_setup(c)
    oid = (await c.post("/api/orders", headers=buyer, json=body)).json()["id"]
    pay = f"/api/orders/{oid}/payments"
    payload = {"request_id": str(uuid4()), "confirmed": True}
    assert (await c.post(pay, headers=buyer, json=payload)).status_code == 409
    await c.post(
        f"/api/merchants/{mid}/orders/{oid}/status", headers=owner, json={"status": "accepted"}
    )
    assert (
        await c.post(pay, headers=buyer, json={**payload, "confirmed": False})
    ).status_code == 422
    assert (await c.post(pay, headers=stranger, json=payload)).status_code == 404
    fee = f"/api/merchants/{mid}/fee-policy"
    assert (
        await c.put(fee, headers=owner, json={"basis_points": 500, "flat_fen": 100})
    ).status_code == 403
    operator_id = decode_token(owner["Authorization"].split(" ")[1])["sub"]
    monkeypatch.setenv("OPENAGENTIC_OPERATOR_IDS", operator_id)
    assert (
        await c.put(fee, headers=owner, json={"basis_points": 500, "flat_fen": 100})
    ).status_code == 200
    paid = await c.post(pay, headers=buyer, json=payload)
    assert paid.status_code == 201, paid.text
    assert paid.json()["fee_fen"] == 590 and paid.json()["provider"] == "local_simulated"
    assert (await c.post(pay, headers=buyer, json=payload)).json()["id"] == paid.json()["id"]
    assert (
        await c.post(pay, headers=buyer, json={**payload, "request_id": str(uuid4())})
    ).status_code == 409
    assert (await c.post(f"/api/orders/{oid}/cancel", headers=buyer)).status_code == 409
    await c.put(fee, headers=owner, json={"basis_points": 1000, "flat_fen": 0})
    finance = (await c.get(f"/api/orders/{oid}/finance", headers=buyer)).json()
    assert finance["payment"]["fee_fen"] == 590
    assert (await c.get(f"/api/orders/{oid}/finance", headers=stranger)).status_code == 404
    refund = (
        await c.post(f"/api/orders/{oid}/refunds", headers=buyer, json={"reason": "时间有变"})
    ).json()
    assert (
        await c.post(f"/api/orders/{oid}/refunds", headers=buyer, json={"reason": "重复"})
    ).json()["id"] == refund["id"]
    resolve = f"/api/merchants/{mid}/refunds/{refund['id']}/resolve"
    assert (
        await c.post(resolve, headers=stranger, json={"approve": True, "resolution": "同意"})
    ).status_code == 404
    done = await c.post(resolve, headers=owner, json={"approve": True, "resolution": "同意退款"})
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "processed"
    assert (
        await c.post(resolve, headers=owner, json={"approve": False, "resolution": "反悔"})
    ).status_code == 409
    assert (
        await c.post(resolve, headers=owner, json={"approve": True, "resolution": "重复"})
    ).status_code == 200
    bill = (await c.get(f"/api/merchants/{mid}/billing", headers=owner)).json()
    assert bill["paid_fen"] == 0 and bill["fee_fen"] == 0 and bill["refunded_fen"] == 9800
    assert (await c.post(f"/api/orders/{oid}/cancel", headers=buyer)).status_code == 200


@pytest.mark.asyncio
async def test_standard_payment_disabled_and_support_cases(commerce_client):
    c = commerce_client
    owner, buyer, stranger, mid, _, body = await booking_setup(c)
    c._transport.app.state.payment_provider = None
    assert (await c.get("/api/commerce/payments/capabilities")).json() == {
        "mode": "disabled",
        "real_money": False,
    }
    oid = (await c.post("/api/orders", headers=buyer, json=body)).json()["id"]
    assert (
        await c.post(
            f"/api/orders/{oid}/payments",
            headers=buyer,
            json={"request_id": str(uuid4()), "confirmed": True},
        )
    ).status_code == 503
    endpoint = f"/api/orders/{oid}/cases"
    assert (
        await c.post(endpoint, headers=stranger, json={"subject": "坏单", "description": "越权"})
    ).status_code == 404
    case = (
        await c.post(
            endpoint, headers=buyer, json={"subject": "改时间", "description": "需要商家协助"}
        )
    ).json()
    assert (await c.get(endpoint, headers=stranger)).status_code == 404
    close = f"/api/commerce/cases/{case['id']}/close"
    assert (await c.post(close, headers=buyer)).status_code == 409
    resolve = f"/api/merchants/{mid}/cases/{case['id']}/resolve"
    assert (await c.post(resolve, headers=stranger, json={"resolution": "越权"})).status_code == 404
    response = await c.post(resolve, headers=owner, json={"resolution": "已联系并改时间"})
    assert response.status_code == 200, response.text
    assert (await c.post(close, headers=owner)).status_code == 404
    assert (await c.post(close, headers=buyer)).json()["status"] == "closed"
    assert (await c.post(close, headers=buyer)).status_code == 200
    assert (await c.post(resolve, headers=owner, json={"resolution": "再改"})).status_code == 409


@pytest.mark.asyncio
async def test_operations_actual_orders_sources_human_time_and_operator_scope(
    commerce_client, monkeypatch
):
    c = commerce_client
    owner, buyer, stranger, mid, _, body = await booking_setup(c)
    ids = []
    for _ in range(2):
        oid = (
            await c.post("/api/orders", headers=buyer, json={**body, "request_id": str(uuid4())})
        ).json()["id"]
        ids.append(oid)
        for status in ("accepted", "completed"):
            await c.post(
                f"/api/merchants/{mid}/orders/{oid}/status", headers=owner, json={"status": status}
            )
    log = {
        "actor": "founder",
        "category": "operation",
        "minutes": 30,
        "note": "协助核对服务",
        "order_id": ids[0],
        "attribution": "existing_customer",
    }
    assert (
        await c.post(f"/api/merchants/{mid}/pilot-logs", headers=stranger, json=log)
    ).status_code == 404
    assert (
        await c.post(f"/api/merchants/{mid}/pilot-logs", headers=owner, json=log)
    ).status_code == 201
    assert (
        await c.post(
            f"/api/merchants/{mid}/pilot-logs",
            headers=owner,
            json={**log, "order_id": str(uuid4())},
        )
    ).status_code == 404
    stats = (await c.get("/api/commerce/operations", headers=owner)).json()
    row = stats["merchants"][0]
    assert stats["scope"] == "owned_merchants" and row["orders"] == 2 and row["repeat_buyers"] == 1
    assert (
        row["founder_minutes"] == 30
        and row["existing_customer_orders"] == 1
        and row["new_platform_orders"] == 0
    )
    assert (await c.get("/api/commerce/operations", headers=stranger)).json()["merchants"] == []
    uid = decode_token(stranger["Authorization"].split(" ")[1])["sub"]
    monkeypatch.setenv("OPENAGENTIC_OPERATOR_IDS", uid)
    all_stats = (await c.get("/api/commerce/operations", headers=stranger)).json()
    assert all_stats["scope"] == "platform" and all_stats["merchants"][0]["id"] == mid


@pytest.mark.asyncio
async def test_store_qr_offline_origin_validation_and_owner_boundary(commerce_client):
    c = commerce_client
    owner, _, stranger, mid, _, _ = await booking_setup(c)
    endpoint = f"/api/merchants/{mid}/share"
    assert (await c.get(endpoint, headers=stranger)).status_code == 404
    response = await c.get(endpoint, headers=owner, params={"origin": "http://127.0.0.1:8766"})
    assert response.status_code == 200, response.text
    assert response.json()["url"] == f"http://127.0.0.1:8766/stores/{mid}"
    assert response.json()["svg"].startswith("<svg") and "<script" not in response.json()["svg"]
    for origin in (
        "file:///tmp",
        "https://user:secret@host",
        "https://host/path",
        "https://host?q=1",
        "https://[",
    ):
        assert (await c.get(endpoint, headers=owner, params={"origin": origin})).status_code == 422
