"""Per-action-type payload schemas (SECURITY.md: Input Validation). Pure, no DB."""

import pytest

from app.executors.payloads import (
    InvalidPayloadError,
    MakePaymentPayload,
    SendEmailPayload,
    UnknownActionTypeError,
    parse_payload,
)

EMAIL = {"to": "a@example.com", "subject": "Hello", "body": "Hi there."}
PAYMENT = {"amount": 1_000, "currency": "usd"}


def error_locs(action_type: str, payload: dict) -> set[str]:
    with pytest.raises(InvalidPayloadError) as exc_info:
        parse_payload(action_type, payload)
    return {e["loc"] for e in exc_info.value.errors}


def test_valid_email_payload_parses() -> None:
    parsed = parse_payload("send_email", EMAIL)
    assert isinstance(parsed, SendEmailPayload)
    assert parsed.to == "a@example.com"


def test_email_requires_all_fields() -> None:
    assert error_locs("send_email", {}) == {"to", "subject", "body"}


@pytest.mark.parametrize("to", ["not-an-email", "a@b", "Bob <a@example.com>", "a@example.com, b@example.com", ""])
def test_email_rejects_bad_recipients(to: str) -> None:
    assert error_locs("send_email", {**EMAIL, "to": to}) == {"to"}


@pytest.mark.parametrize("subject", ["Hi\r\nBcc: victim@example.com", "Hi\nX-Header: 1", ""])
def test_email_subject_cannot_inject_headers_or_be_empty(subject: str) -> None:
    assert error_locs("send_email", {**EMAIL, "subject": subject}) == {"subject"}


def test_unknown_fields_are_rejected() -> None:
    assert error_locs("send_email", {**EMAIL, "bcc": "x@example.com"}) == {"bcc"}
    assert error_locs("make_payment", {**PAYMENT, "customer": "cus_123"}) == {"customer"}


def test_valid_payment_payload_parses_with_default_currency() -> None:
    parsed = parse_payload("make_payment", {"amount": 5_000})
    assert isinstance(parsed, MakePaymentPayload)
    assert (parsed.amount, parsed.currency) == (5_000, "usd")


@pytest.mark.parametrize("amount", [12.5, "5000", True, None, 49, 1_000_001, -100])
def test_payment_amount_must_be_integer_cents_in_range(amount: object) -> None:
    assert error_locs("make_payment", {**PAYMENT, "amount": amount}) == {"amount"}


@pytest.mark.parametrize("currency", ["USD", "us", "dollars"])
def test_payment_currency_must_be_lowercase_iso(currency: str) -> None:
    assert error_locs("make_payment", {**PAYMENT, "currency": currency}) == {"currency"}


def test_unknown_action_type_raises() -> None:
    with pytest.raises(UnknownActionTypeError):
        parse_payload("delete_database", {})


def test_errors_do_not_echo_submitted_values() -> None:
    with pytest.raises(InvalidPayloadError) as exc_info:
        parse_payload("send_email", {**EMAIL, "subject": "secret-value\n"})
    assert "secret-value" not in str(exc_info.value.errors)
