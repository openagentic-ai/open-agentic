"""Exercise real SQL queries and HTTP authorization with an isolated database."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from openagentic.catalog.models import ServiceOffering
from openagentic.apps.commerce import mount_commerce
from openagentic.commerce.models import BookingOrder
from openagentic.commerce.platform_models import PLATFORM_MODELS
from openagentic.commerce.payments import LocalPaymentProvider
from openagentic.core.auth.models import ApiKey, User
from openagentic.core.auth.router import router as auth_router
from openagentic.core.chat.models import Conversation, Message
from openagentic.db.base import Base
from openagentic.db.session import get_db
from openagentic.merchants.models import Merchant, MerchantMember
from openagentic.memory.router import router as memory_router


@pytest.fixture
async def commerce_client(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAGENTIC_MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("OPENAGENTIC_OBSIDIAN_ROOT", str(tmp_path / "vaults"))
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        tables = [
            User.__table__,
            ApiKey.__table__,
            Conversation.__table__,
            Message.__table__,
            Merchant.__table__,
            MerchantMember.__table__,
            ServiceOffering.__table__,
            BookingOrder.__table__,
            *(model.__table__ for model in PLATFORM_MODELS),
        ]
        await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def database():
        async with factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app = FastAPI()
    app.state.payment_provider = LocalPaymentProvider()
    app.include_router(auth_router)
    app.include_router(memory_router)
    mount_commerce(app)
    app.dependency_overrides[get_db] = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await engine.dispose()


async def register(client, email):
    response = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "commerce-test-password",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["token"]}


STORE = {
    "name": "城南维修",
    "region": "杭州",
    "description": "上门维修",
    "contact_name": "老板",
    "contact_phone": "13800000000",
}
SERVICE = {
    "name": "空调清洗",
    "description": "清洁过滤网",
    "price_fen": 9800,
    "duration_minutes": 60,
    "availability_note": "周一至周六",
}


@pytest.mark.asyncio
async def test_real_auth_merchant_service_and_publication(commerce_client):
    client = commerce_client
    assert (await client.get("/api/merchants")).status_code == 401
    headers = await register(client, "owner@example.com")
    login = await client.post(
        "/api/auth/login",
        json={
            "email": "owner@example.com",
            "password": "commerce-test-password",
        },
    )
    assert login.status_code == 200
    created = await client.post("/api/merchants", json=STORE, headers=headers)
    assert created.status_code == 201
    mid = created.json()["id"]
    assert len((await client.get("/api/merchants", headers=headers)).json()) == 1
    updated = await client.put(
        f"/api/merchants/{mid}", json={**STORE, "name": "城南服务"}, headers=headers
    )
    assert updated.json()["name"] == "城南服务"
    path = f"/api/merchants/{mid}/services"
    draft = await client.post(path, json=SERVICE, headers=headers)
    assert draft.status_code == 201
    sid = draft.json()["id"]
    public_path = f"/api/catalog/storefronts/{mid}"
    public = (await client.get(public_path)).json()
    assert public["services"] == []
    assert "contact_phone" not in public["merchant"]
    assert "contact_name" not in public["merchant"]
    assert (await client.get("/api/catalog/services")).json() == []
    published = await client.put(
        f"{path}/{sid}", headers=headers, json={**SERVICE, "is_published": True}
    )
    assert published.status_code == 200
    public = (await client.get(public_path)).json()
    assert public["services"][0]["price_fen"] == 9800
    found = (
        await client.get("/api/catalog/services", params={"q": "空调", "region": "杭州"})
    ).json()
    assert len(found) == 1
    assert (await client.get("/api/catalog/services", params={"q": "%"})).json() == []
    assert (await client.get("/api/catalog/services", params={"region": "上海"})).json() == []
    await client.put(f"{path}/{sid}", headers=headers, json={**SERVICE, "is_published": False})
    assert (await client.get(public_path)).json()["services"] == []


@pytest.mark.asyncio
async def test_cross_merchant_reads_and_writes_are_blocked(commerce_client):
    client = commerce_client
    owner = await register(client, "owner@example.com")
    stranger = await register(client, "stranger@example.com")
    mid = (await client.post("/api/merchants", headers=owner, json=STORE)).json()["id"]
    other = (await client.post("/api/merchants", headers=stranger, json=STORE)).json()["id"]
    path = f"/api/merchants/{mid}/services"
    sid = (await client.post(path, json=SERVICE, headers=owner)).json()["id"]
    stores = (await client.get("/api/merchants", headers=stranger)).json()
    assert [store["id"] for store in stores] == [other]
    assert (await client.get(f"/api/merchants/{mid}", headers=stranger)).status_code == 404
    assert (
        await client.put(f"/api/merchants/{mid}", headers=stranger, json=STORE)
    ).status_code == 404
    assert (await client.get(path, headers=stranger)).status_code == 404
    assert (await client.post(path, headers=stranger, json=SERVICE)).status_code == 404
    assert (await client.put(f"{path}/{sid}", headers=stranger, json=SERVICE)).status_code == 404
    assert (
        await client.put(f"/api/merchants/{other}/services/{sid}", headers=stranger, json=SERVICE)
    ).status_code == 404


@pytest.mark.asyncio
async def test_invalid_service_and_owner_injection_rejected(commerce_client):
    client = commerce_client
    headers = await register(client, "owner@example.com")
    assert (
        await client.post(
            "/api/merchants", headers=headers, json={**STORE, "user_id": "fake-owner"}
        )
    ).status_code == 422
    assert (
        await client.post("/api/merchants", headers=headers, json={**STORE, "name": "   "})
    ).status_code == 422
    mid = (await client.post("/api/merchants", headers=headers, json=STORE)).json()["id"]
    for patch in (
        {"price_fen": -1},
        {"price_fen": 1.1},
        {"duration_minutes": 0},
        {"name": " "},
        {"merchant_id": mid},
    ):
        response = await client.post(
            f"/api/merchants/{mid}/services", headers=headers, json={**SERVICE, **patch}
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_memory_and_vault_are_authenticated_and_user_isolated(commerce_client):
    client = commerce_client
    assert (await client.get("/api/memory/vault")).status_code == 401
    assert (await client.get("/api/memory/core")).status_code == 401
    owner = await register(client, "owner@example.com")
    stranger = await register(client, "stranger@example.com")
    body = {
        "name": "接单流程",
        "description": "确认需求",
        "trigger_pattern": "接单",
        "steps": ["确认服务", "记录预约"],
    }
    assert (
        await client.post("/api/memory/procedures", headers=owner, json=body)
    ).status_code == 201
    result = (await client.get("/api/memory/vault/search", headers=owner)).json()
    assert len(result) == 1
    assert result[0]["properties"]["type"] == "procedure"
    assert (await client.get("/api/memory/vault/search", headers=stranger)).json() == []
    assert (
        await client.get("/api/memory/procedures/search", headers=stranger, params={"q": "接单"})
    ).json() == []
    path = result[0]["path"]
    assert (
        await client.get("/api/memory/vault/note", headers=owner, params={"path": path})
    ).status_code == 200
    assert (
        await client.get("/api/memory/vault/note", headers=stranger, params={"path": path})
    ).status_code == 404
    assert (
        await client.get("/api/memory/vault/note", headers=owner, params={"path": "../secret.md"})
    ).status_code == 400
    assert (
        await client.get("/api/memory/core", headers=owner, params={"category": "../../other"})
    ).status_code == 422
    await client.post(
        "/api/memory/core", headers=owner, json={"key": "preference", "value": "中文"}
    )
    assert len((await client.get("/api/memory/core", headers=owner)).json()) == 1
    assert (await client.get("/api/memory/core", headers=stranger)).json() == []


async def booking_setup(client):
    owner = await register(client, "owner@example.com")
    buyer = await register(client, "buyer@example.com")
    stranger = await register(client, "stranger@example.com")
    mid = (await client.post("/api/merchants", headers=owner, json=STORE)).json()["id"]
    offering = await client.post(
        f"/api/merchants/{mid}/services", headers=owner, json={**SERVICE, "is_published": True}
    )
    sid = offering.json()["id"]
    body = {
        "service_id": sid,
        "request_id": str(uuid4()),
        "expected_price_fen": 9800,
        "preferred_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "customer_name": "客户",
        "customer_phone": "13900000000",
        "note": "上门清洗",
        "confirmed": True,
    }
    return owner, buyer, stranger, mid, sid, body


@pytest.mark.asyncio
async def test_booking_confirmation_idempotency_and_fulfillment(commerce_client):
    client = commerce_client
    owner, buyer, stranger, mid, sid, body = await booking_setup(client)
    assert (await client.post("/api/orders", json=body)).status_code == 401
    assert (
        await client.post("/api/orders", headers=buyer, json={**body, "confirmed": False})
    ).status_code == 422
    created = await client.post("/api/orders", headers=buyer, json=body)
    assert created.status_code == 201, created.text
    order = created.json()
    oid = order["id"]
    assert order["status"] == "pending"
    assert order["preferred_at"].endswith("Z") or order["preferred_at"].endswith("+00:00")
    # Identical retry returns the same persisted order, even after a service price change.
    await client.put(
        f"/api/merchants/{mid}/services/{sid}",
        headers=owner,
        json={**SERVICE, "is_published": True, "price_fen": 12000},
    )
    replay = await client.post("/api/orders", headers=buyer, json=body)
    assert replay.json()["id"] == oid
    assert replay.json()["price_fen"] == 9800
    assert len((await client.get("/api/orders", headers=buyer)).json()) == 1
    assert (
        await client.post("/api/orders", headers=buyer, json={**body, "note": "其他要求"})
    ).status_code == 409
    merchant_path = f"/api/merchants/{mid}/orders"
    assert (await client.get(merchant_path, headers=stranger)).status_code == 404
    assert (await client.get(f"/api/orders/{oid}", headers=stranger)).status_code == 404
    assert (await client.post(f"/api/orders/{oid}/cancel", headers=stranger)).status_code == 404
    assert (
        await client.post(
            f"{merchant_path}/{oid}/status", headers=stranger, json={"status": "accepted"}
        )
    ).status_code == 404
    assert (
        await client.post(
            f"{merchant_path}/{oid}/status", headers=owner, json={"status": "completed"}
        )
    ).status_code == 409
    assert (
        await client.post(
            f"{merchant_path}/{oid}/status", headers=owner, json={"status": "accepted"}
        )
    ).json()["status"] == "accepted"
    assert (
        await client.post(
            f"{merchant_path}/{oid}/status", headers=owner, json={"status": "completed"}
        )
    ).json()["status"] == "completed"
    assert (await client.get(f"/api/orders/{oid}", headers=buyer)).json()["status"] == "completed"
    assert (await client.post(f"/api/orders/{oid}/cancel", headers=buyer)).status_code == 409
    assert (
        await client.post(
            f"{merchant_path}/{oid}/status", headers=owner, json={"status": "accepted"}
        )
    ).status_code == 409


@pytest.mark.asyncio
async def test_booking_price_availability_and_cancellation(commerce_client):
    client = commerce_client
    owner, buyer, _, mid, sid, body = await booking_setup(client)
    assert (
        await client.post("/api/orders", headers=buyer, json={**body, "expected_price_fen": 1})
    ).status_code == 409
    assert (
        await client.post(
            "/api/orders",
            headers=buyer,
            json={
                **body,
                "preferred_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            },
        )
    ).status_code == 400
    oid = (await client.post("/api/orders", headers=buyer, json=body)).json()["id"]
    cancelled = await client.post(f"/api/orders/{oid}/cancel", headers=buyer)
    assert cancelled.json()["status"] == "cancelled"
    assert (await client.post(f"/api/orders/{oid}/cancel", headers=buyer)).status_code == 200
    assert (
        await client.post(
            f"/api/merchants/{mid}/orders/{oid}/status", headers=owner, json={"status": "accepted"}
        )
    ).status_code == 409
    await client.put(f"/api/merchants/{mid}/services/{sid}", headers=owner, json=SERVICE)
    assert (
        await client.post("/api/orders", headers=buyer, json={**body, "request_id": str(uuid4())})
    ).status_code == 404
