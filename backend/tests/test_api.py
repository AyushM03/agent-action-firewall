"""HTTP layer: agent API keys, approver login, approval endpoints, and the full approval flow."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, generate_api_key, hash_api_key
from app.models import Agent, AuditEvent, PolicyEffect
from app.services.accounts import create_approver
from tests.test_firewall_flow import add_rule, make_agent

PASSWORD = "correct horse battery"


def unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def agent_with_key(db: AsyncSession, *action_types: str) -> tuple[Agent, dict[str, str]]:
    agent = await make_agent(db, *action_types)
    api_key = generate_api_key()
    agent.api_key_hash = hash_api_key(api_key)
    await db.flush()
    return agent, {"X-API-Key": api_key}


async def approver_headers(db: AsyncSession, client: AsyncClient) -> dict[str, str]:
    username = unique_name("approver")
    await create_approver(db, username, PASSWORD)
    response = await client.post("/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def event_types(db: AsyncSession, request_id: str) -> list[str]:
    stmt = select(AuditEvent.event_type).where(AuditEvent.action_request_id == uuid.UUID(request_id))
    return list((await db.scalars(stmt.order_by(AuditEvent.id))).all())


# --- POST /actions/request ---


async def test_request_without_api_key_is_401(client: AsyncClient) -> None:
    response = await client.post("/actions/request", json={"action_type": "send_email", "payload": {}})
    assert response.status_code == 401


async def test_request_with_unknown_api_key_is_401(client: AsyncClient) -> None:
    response = await client.post(
        "/actions/request",
        json={"action_type": "send_email", "payload": {}},
        headers={"X-API-Key": generate_api_key()},
    )
    assert response.status_code == 401


async def test_request_is_decided_and_recorded_for_the_keyed_agent(db: AsyncSession, client: AsyncClient) -> None:
    agent, headers = await agent_with_key(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()

    response = await client.post(
        "/actions/request", json={"action_type": "send_email", "payload": {"to": "a@example.com"}}, headers=headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["decision"] == "allow"
    assert body["code"] == "rule_matched"
    [event] = (await db.scalars(select(AuditEvent).where(AuditEvent.action_request_id == uuid.UUID(body["request_id"])))).all()
    assert event.agent_id == agent.id


async def test_agent_id_in_body_cannot_impersonate_another_agent(db: AsyncSession, client: AsyncClient) -> None:
    _, headers = await agent_with_key(db, "make_payment")
    victim = await make_agent(db, "make_payment")
    add_rule(db, victim, "make_payment", PolicyEffect.ALLOW)
    await db.flush()

    response = await client.post(
        "/actions/request",
        json={"agent_id": str(victim.id), "action_type": "make_payment", "payload": {"amount": 1}},
        headers=headers,
    )

    # The key's agent has no allow rule of its own; the victim's allow rule was never used.
    assert response.json()["decision"] == "deny"
    [event] = (await db.scalars(select(AuditEvent).where(AuditEvent.action_request_id == uuid.UUID(response.json()["request_id"])))).all()
    assert event.agent_id != victim.id


async def test_invalid_body_is_422_and_not_recorded(db: AsyncSession, client: AsyncClient) -> None:
    _, headers = await agent_with_key(db, "send_email")
    response = await client.post("/actions/request", json={"action_type": "", "payload": []}, headers=headers)
    assert response.status_code == 422


# --- /auth ---


async def test_login_with_wrong_password_is_401(db: AsyncSession, client: AsyncClient) -> None:
    username = unique_name("someone")
    await create_approver(db, username, PASSWORD)
    response = await client.post("/auth/login", json={"username": username, "password": "nope"})
    assert response.status_code == 401


async def test_login_with_unknown_user_is_401(client: AsyncClient) -> None:
    response = await client.post("/auth/login", json={"username": unique_name("nobody"), "password": PASSWORD})
    assert response.status_code == 401


async def test_me_returns_logged_in_approver(db: AsyncSession, client: AsyncClient) -> None:
    username = unique_name("carol")
    await create_approver(db, username, PASSWORD)
    token = (await client.post("/auth/login", json={"username": username, "password": PASSWORD})).json()["access_token"]

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.json() == {"username": username}


async def test_deactivated_approver_token_stops_working(db: AsyncSession, client: AsyncClient) -> None:
    approver = await create_approver(db, unique_name("dave"), PASSWORD)
    headers = {"Authorization": f"Bearer {create_access_token(approver.username)}"}
    approver.is_active = False
    await db.flush()

    assert (await client.get("/approvals/pending", headers=headers)).status_code == 401


# --- /approvals ---


async def test_approval_endpoints_require_authentication(client: AsyncClient) -> None:
    request_id = uuid.uuid4()
    assert (await client.get("/approvals/pending")).status_code == 401
    assert (await client.post(f"/approvals/{request_id}/approve")).status_code == 401
    assert (await client.post(f"/approvals/{request_id}/reject")).status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert (await client.post(f"/approvals/{request_id}/approve", headers=bad)).status_code == 401


async def test_agent_api_key_cannot_approve(db: AsyncSession, client: AsyncClient) -> None:
    _, headers = await agent_with_key(db, "make_payment")
    assert (await client.post(f"/approvals/{uuid.uuid4()}/approve", headers=headers)).status_code == 401


async def test_unauthenticated_approve_writes_no_event(db: AsyncSession, client: AsyncClient) -> None:
    agent, headers = await agent_with_key(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    request_id = (await client.post("/actions/request", json={"action_type": "make_payment", "payload": {"amount": 1}}, headers=headers)).json()["request_id"]

    assert (await client.post(f"/approvals/{request_id}/approve")).status_code == 401
    assert await event_types(db, request_id) == ["needs_approval"]


async def test_approve_unknown_request_is_404(db: AsyncSession, client: AsyncClient) -> None:
    headers = await approver_headers(db, client)
    assert (await client.post(f"/approvals/{uuid.uuid4()}/approve", headers=headers)).status_code == 404


async def test_approve_allowed_request_is_409(db: AsyncSession, client: AsyncClient) -> None:
    agent, agent_headers = await agent_with_key(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    await db.flush()
    request_id = (await client.post("/actions/request", json={"action_type": "send_email", "payload": {}}, headers=agent_headers)).json()["request_id"]
    headers = await approver_headers(db, client)

    response = await client.post(f"/approvals/{request_id}/approve", headers=headers)

    assert response.status_code == 409
    assert await event_types(db, request_id) == ["allowed"]


# --- Full flow: request -> needs_approval -> human decision ---


async def test_full_flow_request_needs_approval_then_approved(db: AsyncSession, client: AsyncClient) -> None:
    agent, agent_headers = await agent_with_key(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    headers = await approver_headers(db, client)

    decision = (await client.post("/actions/request", json={"action_type": "make_payment", "payload": {"amount": 12_500}}, headers=agent_headers)).json()
    assert decision["decision"] == "needs_approval"
    request_id = decision["request_id"]

    pending = (await client.get("/approvals/pending", headers=headers)).json()
    [item] = [item for item in pending if item["request_id"] == request_id]
    assert item["agent_name"] == agent.name
    assert item["action_type"] == "make_payment"
    assert item["payload"] == {"amount": 12_500}

    response = await client.post(f"/approvals/{request_id}/approve", headers=headers, json={"note": "Invoice checked"})
    assert response.status_code == 200
    assert response.json()["event_type"] == "approved"
    assert response.json()["actor"].startswith("approver:approver-")

    pending = (await client.get("/approvals/pending", headers=headers)).json()
    assert request_id not in {item["request_id"] for item in pending}
    assert await event_types(db, request_id) == ["needs_approval", "approved"]

    again = await client.post(f"/approvals/{request_id}/reject", headers=headers)
    assert again.status_code == 409
    assert await event_types(db, request_id) == ["needs_approval", "approved"]


async def test_full_flow_request_needs_approval_then_rejected(db: AsyncSession, client: AsyncClient) -> None:
    agent, agent_headers = await agent_with_key(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    headers = await approver_headers(db, client)
    request_id = (await client.post("/actions/request", json={"action_type": "make_payment", "payload": {"amount": 99_999}}, headers=agent_headers)).json()["request_id"]

    response = await client.post(f"/approvals/{request_id}/reject", headers=headers)

    assert response.status_code == 200
    assert response.json()["event_type"] == "rejected"
    assert await event_types(db, request_id) == ["needs_approval", "rejected"]
