"""Gmail and Stripe executors without the network: message building, guards and error mapping."""

import uuid
from types import SimpleNamespace

import pytest
import stripe
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.executors import ExecutionError
from app.executors.gmail import GmailExecutor
from app.executors.payloads import MakePaymentPayload, SendEmailPayload
from app.executors.payments import StripePaymentExecutor

EMAIL = SendEmailPayload(to="a@example.com", subject="Receipt", body="Thanks!")
PAYMENT = MakePaymentPayload(amount=2_500, currency="usd", description="Invoice 7")
REQUEST_ID = uuid.UUID("00000000-0000-0000-0000-000000000007")


def gmail() -> GmailExecutor:
    return GmailExecutor("client-id", "client-secret", "refresh-token", "firewall@example.com")


async def expect_error(executor, payload) -> ExecutionError:
    with pytest.raises(ExecutionError) as exc_info:
        await executor.execute(REQUEST_ID, payload)
    return exc_info.value


# --- Gmail ---


def test_gmail_message_has_expected_headers_and_body() -> None:
    message = gmail().build_message(REQUEST_ID, EMAIL)
    assert message["From"] == "firewall@example.com"
    assert message["To"] == "a@example.com"
    assert message["Subject"] == "Receipt"
    assert message["X-Agent-Firewall-Request"] == str(REQUEST_ID)
    assert message.get_content().strip() == "Thanks!"


async def test_gmail_unconfigured_fails_without_calling_api(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = GmailExecutor("", "", "", "")
    monkeypatch.setattr(executor, "_send", lambda *_: pytest.fail("must not call Gmail"))
    assert (await expect_error(executor, EMAIL)).code == "not_configured"


async def test_gmail_success_returns_message_id(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = gmail()
    monkeypatch.setattr(executor, "_send", lambda message: {"id": "msg-123", "threadId": "thr-9"})
    result = await executor.execute(REQUEST_ID, EMAIL)
    assert result.external_id == "msg-123"
    assert result.details == {"thread_id": "thr-9", "to": "a@example.com"}


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (RefreshError("invalid_grant: token=abc"), "auth_failed"),
        (HttpError(SimpleNamespace(status=403, reason="Forbidden"), b"{}"), "gmail_error"),
        (ConnectionError("dns"), "network_error"),
    ],
)
async def test_gmail_errors_are_mapped_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch, error: Exception, code: str
) -> None:
    executor = gmail()

    def fail(message):
        raise error

    monkeypatch.setattr(executor, "_send", fail)
    err = await expect_error(executor, EMAIL)
    assert err.code == code
    assert "token=abc" not in err.message


# --- Stripe ---


async def test_stripe_refuses_live_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = StripePaymentExecutor("sk_live_" + "x" * 24)
    monkeypatch.setattr(executor, "_create", lambda *_: pytest.fail("must not call Stripe"))
    err = await expect_error(executor, PAYMENT)
    assert err.code == "live_key_refused"
    assert "sk_live_" not in err.message


async def test_stripe_unconfigured_fails() -> None:
    assert (await expect_error(StripePaymentExecutor(""), PAYMENT)).code == "not_configured"


async def test_stripe_success_returns_payment_intent_id(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = StripePaymentExecutor("sk_test_dummy")
    seen = {}

    def create(request_id, payload):
        seen["args"] = (request_id, payload)
        return SimpleNamespace(id="pi_123", status="succeeded", amount=2_500, currency="usd")

    monkeypatch.setattr(executor, "_create", create)
    result = await executor.execute(REQUEST_ID, PAYMENT)
    assert result.external_id == "pi_123"
    assert result.details == {"status": "succeeded", "amount": 2_500, "currency": "usd"}
    assert seen["args"] == (REQUEST_ID, PAYMENT)


async def test_stripe_incomplete_payment_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    executor = StripePaymentExecutor("sk_test_dummy")
    monkeypatch.setattr(
        executor, "_create", lambda *_: SimpleNamespace(id="pi_9", status="requires_action", amount=1, currency="usd")
    )
    assert (await expect_error(executor, PAYMENT)).code == "payment_incomplete"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (stripe.CardError("Your card was declined.", None, "card_declined"), "card_declined"),
        (stripe.AuthenticationError("Invalid API Key provided: sk_test_***"), "auth_failed"),
        (stripe.APIConnectionError("network down"), "stripe_error"),
    ],
)
async def test_stripe_errors_are_mapped(monkeypatch: pytest.MonkeyPatch, error: Exception, code: str) -> None:
    executor = StripePaymentExecutor("sk_test_dummy")

    def fail(*_):
        raise error

    monkeypatch.setattr(executor, "_create", fail)
    err = await expect_error(executor, PAYMENT)
    assert err.code == code
    assert "sk_test_" not in err.message
