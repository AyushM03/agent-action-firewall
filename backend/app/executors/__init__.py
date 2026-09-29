from app.core.config import Settings
from app.executors.base import ExecutionError, ExecutionResult, Executor
from app.executors.gmail import GmailExecutor
from app.executors.payments import StripePaymentExecutor


def build_executors(settings: Settings) -> dict[str, Executor]:
    """One executor per action type, configured from backend env vars only."""
    return {
        "send_email": GmailExecutor(
            settings.gmail_client_id,
            settings.gmail_client_secret,
            settings.gmail_refresh_token,
            settings.gmail_sender_address,
        ),
        "make_payment": StripePaymentExecutor(settings.stripe_secret_key),
    }


__all__ = ["ExecutionError", "ExecutionResult", "Executor", "build_executors"]
