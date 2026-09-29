"""Live executor tests against the real Gmail API and Stripe test mode (ADR-004).

Deselected by default. Run with:  pytest -m integration
Each test skips itself if its credentials aren't configured in backend/.env.
"""

import uuid

import pytest

from app.core.config import settings
from app.executors import build_executors
from app.executors.payloads import MakePaymentPayload, SendEmailPayload

pytestmark = pytest.mark.integration


@pytest.mark.skipif(not settings.stripe_secret_key, reason="STRIPE_SECRET_KEY not set")
async def test_stripe_creates_a_test_mode_payment() -> None:
    executor = build_executors(settings)["make_payment"]
    request_id = uuid.uuid4()

    result = await executor.execute(request_id, MakePaymentPayload(amount=1_234, description="AAF integration test"))

    assert result.external_id.startswith("pi_")
    assert result.details == {"status": "succeeded", "amount": 1_234, "currency": "usd"}
    # Same request ID -> same PaymentIntent (idempotency key), not a second charge.
    again = await executor.execute(request_id, MakePaymentPayload(amount=1_234, description="AAF integration test"))
    assert again.external_id == result.external_id


@pytest.mark.skipif(
    not (settings.gmail_client_id and settings.gmail_refresh_token and settings.gmail_sender_address),
    reason="GMAIL_* not set",
)
async def test_gmail_sends_a_real_email_to_the_sender() -> None:
    executor = build_executors(settings)["send_email"]
    payload = SendEmailPayload(
        to=settings.gmail_sender_address,
        subject="Agent Action Firewall integration test",
        body="Sent by tests/test_integrations.py. Safe to delete.",
    )

    result = await executor.execute(uuid.uuid4(), payload)

    assert result.external_id
