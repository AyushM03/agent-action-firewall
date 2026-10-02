"""Dashboard read endpoints: the audit log viewer, request history, and agent activity.

The dev DB may already hold events from earlier runs, so every query here is
scoped to an agent created by the test.
"""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, PolicyEffect
from tests.test_api import agent_with_key, approver_headers
from tests.test_firewall_flow import add_rule, payload_for


async def submit(client: AsyncClient, headers: dict[str, str], action_type: str, **overrides) -> str:
    response = await client.post(
        "/actions/request", json={"action_type": action_type, "payload": payload_for(action_type, **overrides)}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["request_id"]


async def busy_agent(db: AsyncSession, client: AsyncClient) -> tuple[Agent, dict[str, str], dict[str, str]]:
    """An agent whose emails are allowed and payments need approval, with one of each submitted.

    Produces, oldest first: allowed, executed (email), needs_approval (payment).
    """
    agent, agent_headers = await agent_with_key(db, "send_email", "make_payment")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    await submit(client, agent_headers, "send_email")
    await submit(client, agent_headers, "make_payment")
    return agent, agent_headers, await approver_headers(db, client)


# --- authentication ---


async def test_dashboard_endpoints_require_an_approver(client: AsyncClient) -> None:
    for path in ("/audit/events", f"/audit/requests/{uuid.uuid4()}", "/agents"):
        assert (await client.get(path)).status_code == 401, path


async def test_agent_api_key_is_not_accepted_for_dashboard_reads(db: AsyncSession, client: AsyncClient) -> None:
    _, agent_headers = await agent_with_key(db, "send_email")
    assert (await client.get("/audit/events", headers=agent_headers)).status_code == 401


# --- GET /audit/events ---


async def test_events_are_newest_first_with_everything_the_log_must_show(db: AsyncSession, client: AsyncClient) -> None:
    agent, _, headers = await busy_agent(db, client)

    response = await client.get("/audit/events", params={"agent_id": str(agent.id)}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [e["event_type"] for e in body["items"]] == ["needs_approval", "executed", "allowed"]
    assert body["next_before"] is None
    newest = body["items"][0]
    assert newest["agent_name"] == agent.name
    assert newest["action_type"] == "make_payment"
    assert newest["reason"]
    assert newest["created_at"]
    assert newest["actor"] == "firewall"


async def test_events_filter_by_action_type_and_event_types(db: AsyncSession, client: AsyncClient) -> None:
    agent, _, headers = await busy_agent(db, client)
    base = {"agent_id": str(agent.id)}

    by_action = await client.get("/audit/events", params={**base, "action_type": "send_email"}, headers=headers)
    assert [e["event_type"] for e in by_action.json()["items"]] == ["executed", "allowed"]

    by_types = await client.get(
        "/audit/events", params=[*base.items(), ("event_type", "allowed"), ("event_type", "needs_approval")], headers=headers
    )
    assert [e["event_type"] for e in by_types.json()["items"]] == ["needs_approval", "allowed"]


async def test_events_paginate_without_overlap(db: AsyncSession, client: AsyncClient) -> None:
    agent, _, headers = await busy_agent(db, client)
    params = {"agent_id": str(agent.id), "limit": 2}

    first = (await client.get("/audit/events", params=params, headers=headers)).json()
    assert len(first["items"]) == 2
    assert first["next_before"] == first["items"][-1]["id"]

    second = (await client.get("/audit/events", params={**params, "before": first["next_before"]}, headers=headers)).json()
    assert [e["event_type"] for e in second["items"]] == ["allowed"]
    assert second["next_before"] is None


async def test_events_reject_bad_filters(db: AsyncSession, client: AsyncClient) -> None:
    headers = await approver_headers(db, client)
    for params in ({"event_type": "bogus"}, {"limit": 0}, {"limit": 201}, {"agent_id": "not-a-uuid"}, {"before": 0}):
        assert (await client.get("/audit/events", params=params, headers=headers)).status_code == 422, params


async def test_events_for_an_agent_with_no_activity_are_empty(db: AsyncSession, client: AsyncClient) -> None:
    agent, _ = await agent_with_key(db, "send_email")
    headers = await approver_headers(db, client)

    body = (await client.get("/audit/events", params={"agent_id": str(agent.id)}, headers=headers)).json()

    assert body == {"items": [], "next_before": None}


# --- GET /audit/requests/{id} ---


async def test_request_history_shows_payload_and_every_event_in_order(db: AsyncSession, client: AsyncClient) -> None:
    agent, agent_headers = await agent_with_key(db, "make_payment")
    add_rule(db, agent, "make_payment", PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    request_id = await submit(client, agent_headers, "make_payment", amount=1234)
    headers = await approver_headers(db, client)
    await client.post(f"/approvals/{request_id}/approve", json={"note": "ok"}, headers=headers)

    response = await client.get(f"/audit/requests/{request_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["agent_name"] == agent.name
    assert body["payload"]["amount"] == 1234
    assert [e["event_type"] for e in body["events"]] == ["needs_approval", "approved", "executed"]
    assert body["events"][1]["data"] == {"note": "ok"}


async def test_unknown_request_history_is_404(db: AsyncSession, client: AsyncClient) -> None:
    headers = await approver_headers(db, client)
    assert (await client.get(f"/audit/requests/{uuid.uuid4()}", headers=headers)).status_code == 404


# --- GET /agents ---


async def test_agent_activity_counts_requests_events_and_pending(db: AsyncSession, client: AsyncClient) -> None:
    agent, agent_headers, headers = await busy_agent(db, client)
    await submit(client, agent_headers, "make_payment")  # a second payment, which we approve
    pending = (await client.get("/approvals/pending", headers=headers)).json()
    mine = [p["request_id"] for p in pending if p["agent_id"] == str(agent.id)]
    await client.post(f"/approvals/{mine[0]}/approve", headers=headers)

    response = await client.get("/agents", headers=headers)

    assert response.status_code == 200
    item = next(a for a in response.json() if a["id"] == str(agent.id))
    assert item["total_requests"] == 3
    assert item["pending_approvals"] == 1
    assert item["event_counts"] == {"allowed": 1, "executed": 2, "needs_approval": 2, "approved": 1}
    assert item["last_activity_at"] is not None
    assert item["has_api_key"] is True
    assert "api_key_hash" not in item


async def test_agent_with_no_activity_is_listed_with_zero_counts(db: AsyncSession, client: AsyncClient) -> None:
    agent, _ = await agent_with_key(db, "send_email")
    headers = await approver_headers(db, client)

    item = next(a for a in (await client.get("/agents", headers=headers)).json() if a["id"] == str(agent.id))

    assert item["total_requests"] == 0
    assert item["pending_approvals"] == 0
    assert item["event_counts"] == {}
    assert item["last_activity_at"] is None
