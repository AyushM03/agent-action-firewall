"""End-to-end flows from TEST_PLAN.md, driven only through the HTTP API, the way an agent and an approver would.

The rate-limit flow uses fake executors and always runs. The approval flows use the real
Gmail API and Stripe test mode, so they are marked `integration` (run with `pytest -m integration`).
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_executors
from app.core.config import settings
from app.executors import build_executors
from app.main import app
from app.models import PolicyEffect
from tests.conftest import FakeClock, FakeExecutor
from tests.test_api import agent_with_key, approver_headers
from tests.test_firewall_flow import add_limit, add_rule, payload_for


async def request_action(client: AsyncClient, headers: dict[str, str], action_type: str, **payload) -> dict:
    response = await client.post(
        "/actions/request", json={"action_type": action_type, "payload": payload_for(action_type, **payload)}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def audit_trail(client: AsyncClient, headers: dict[str, str], request_id: str) -> list[dict]:
    """The request's events as the dashboard shows them."""
    response = await client.get(f"/audit/requests/{request_id}", headers=headers)
    assert response.status_code == 200
    return response.json()["events"]


# --- Agent exceeds rate limit → denied → no execution → audit trail reflects denial ---


async def test_agent_over_rate_limit_is_denied_not_executed_and_audited(
    db: AsyncSession, client: AsyncClient, executors: dict[str, FakeExecutor], clock: FakeClock
) -> None:
    agent, agent_headers = await agent_with_key(db, "send_email")
    add_rule(db, agent, "send_email", PolicyEffect.ALLOW)
    add_limit(db, agent, "send_email", max_requests=2, window=60)
    await db.flush()
    headers = await approver_headers(db, client)

    within_limit = [await request_action(client, agent_headers, "send_email") for _ in range(2)]
    over_limit = await request_action(client, agent_headers, "send_email")

    assert [d["decision"] for d in within_limit] == ["allow", "allow"]
    assert over_limit["decision"] == "deny"
    assert over_limit["code"] == "rate_limited"
    assert over_limit["execution"] is None
    # Only the two allowed requests reached the executor.
    assert [str(request_id) for request_id, _ in executors["send_email"].calls] == [d["request_id"] for d in within_limit]

    [denial] = await audit_trail(client, headers, over_limit["request_id"])
    assert denial["event_type"] == "denied"
    assert denial["actor"] == "firewall"
    assert denial["data"]["code"] == "rate_limited"
    denied = (
        await client.get("/audit/events", params={"agent_id": str(agent.id), "event_type": "denied"}, headers=headers)
    ).json()["items"]
    assert [e["request_id"] for e in denied] == [over_limit["request_id"]]

    # Once the window has passed the agent can act again.
    clock.advance(61)
    assert (await request_action(client, agent_headers, "send_email"))["decision"] == "allow"
    assert len(executors["send_email"].calls) == 3


# --- Agent requests risky action → queued → approved → actually executed → audit trail shows the full chain ---


@pytest.fixture
async def live_client(client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """`client`, but approved/allowed actions run through the real Gmail and Stripe executors."""
    app.dependency_overrides[get_executors] = lambda: build_executors(settings)
    yield client


async def approve_and_check_chain(
    db: AsyncSession, client: AsyncClient, action_type: str, executor_actor: str, **payload
) -> dict:
    """Run the full approval flow over HTTP and return the `executed` event."""
    agent, agent_headers = await agent_with_key(db, action_type)
    add_rule(db, agent, action_type, PolicyEffect.NEEDS_APPROVAL)
    await db.flush()
    headers = await approver_headers(db, client)

    decision = await request_action(client, agent_headers, action_type, **payload)
    assert decision["decision"] == "needs_approval"
    assert decision["execution"] is None
    request_id = decision["request_id"]
    pending = (await client.get("/approvals/pending", headers=headers)).json()
    assert request_id in {item["request_id"] for item in pending}
    # Held, not executed, while waiting for a human.
    assert [e["event_type"] for e in await audit_trail(client, headers, request_id)] == ["needs_approval"]

    response = await client.post(f"/approvals/{request_id}/approve", json={"note": "e2e test"}, headers=headers)

    assert response.status_code == 200
    execution = response.json()["execution"]
    assert execution["status"] == "executed", execution
    chain = await audit_trail(client, headers, request_id)
    assert [e["event_type"] for e in chain] == ["needs_approval", "approved", "executed"]
    assert chain[1]["actor"].startswith("approver:")
    executed = chain[2]
    assert executed["actor"] == executor_actor
    assert executed["data"]["authorized_by"] == "approved"
    assert executed["data"]["external_id"] == execution["external_id"]
    return executed


@pytest.mark.integration
@pytest.mark.skipif(
    not (settings.gmail_client_id and settings.gmail_refresh_token and settings.gmail_sender_address),
    reason="GMAIL_* not set",
)
async def test_risky_email_is_held_approved_and_really_sent(db: AsyncSession, live_client: AsyncClient) -> None:
    executed = await approve_and_check_chain(
        db,
        live_client,
        "send_email",
        "executor:gmail",
        to=settings.gmail_sender_address,
        subject="Agent Action Firewall end-to-end test",
        body="Requested by a test agent, held for approval, approved, then sent. Safe to delete.",
    )
    assert executed["data"]["external_id"]  # the Gmail message ID


@pytest.mark.integration
@pytest.mark.skipif(not settings.stripe_secret_key, reason="STRIPE_SECRET_KEY not set")
async def test_risky_payment_is_held_approved_and_really_paid(db: AsyncSession, live_client: AsyncClient) -> None:
    executed = await approve_and_check_chain(
        db, live_client, "make_payment", "executor:stripe", amount=4_321, description="AAF end-to-end test"
    )
    assert executed["data"]["external_id"].startswith("pi_")
    assert executed["data"]["status"] == "succeeded"
