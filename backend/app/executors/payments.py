"""Create payments with Stripe, test mode only (ADR-004, SECURITY.md)."""

import asyncio
import uuid

import stripe

from app.executors.base import ExecutionError, ExecutionResult
from app.executors.payloads import MakePaymentPayload, Payload

TEST_KEY_PREFIXES = ("sk_test_", "rk_test_")
# Stripe's always-succeeds test card, so a payment can be confirmed server-side with no customer.
TEST_PAYMENT_METHOD = "pm_card_visa"


class StripePaymentExecutor:
    actor = "executor:stripe"

    def __init__(self, secret_key: str) -> None:
        self._secret_key = secret_key

    def _create(self, request_id: uuid.UUID, payload: MakePaymentPayload) -> stripe.PaymentIntent:
        client = stripe.StripeClient(self._secret_key, max_network_retries=2)
        params: dict = {
            "amount": payload.amount,
            "currency": payload.currency,
            "payment_method": TEST_PAYMENT_METHOD,
            "confirm": True,
            "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
            "metadata": {"action_request_id": str(request_id)},
        }
        if payload.description:
            params["description"] = payload.description
        # Same request -> same PaymentIntent, even if this is ever retried.
        return client.payment_intents.create(params=params, options={"idempotency_key": f"aaf-{request_id}"})

    async def execute(self, request_id: uuid.UUID, payload: Payload) -> ExecutionResult:
        assert isinstance(payload, MakePaymentPayload)
        if not self._secret_key:
            raise ExecutionError("not_configured", "Stripe executor is not configured (STRIPE_SECRET_KEY).")
        if not self._secret_key.startswith(TEST_KEY_PREFIXES):
            raise ExecutionError("live_key_refused", "Refusing to use a non-test Stripe key.")
        try:
            intent = await asyncio.to_thread(self._create, request_id, payload)
        except stripe.CardError as exc:
            raise ExecutionError("card_declined", f"Stripe declined the payment: {exc.code or 'card_error'}.")
        except stripe.AuthenticationError:
            raise ExecutionError("auth_failed", "Stripe rejected the API key.")
        except stripe.StripeError as exc:
            raise ExecutionError("stripe_error", f"Stripe error: {exc.code or type(exc).__name__}.")
        if intent.status != "succeeded":
            raise ExecutionError("payment_incomplete", f"PaymentIntent {intent.id} ended in status '{intent.status}'.")
        return ExecutionResult(
            intent.id, {"status": intent.status, "amount": intent.amount, "currency": intent.currency}
        )
