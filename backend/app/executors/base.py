"""The contract every action executor follows."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.executors.payloads import Payload


@dataclass(frozen=True)
class ExecutionResult:
    """What the external system did. `external_id` is its ID (Gmail message, Stripe PaymentIntent)."""

    external_id: str
    details: dict[str, Any] = field(default_factory=dict)


class ExecutionError(Exception):
    """The external call failed. The message goes into the audit log, so it must never contain secrets."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Executor(Protocol):
    # Written as the event actor, e.g. "executor:gmail".
    actor: str

    async def execute(self, request_id: uuid.UUID, payload: Payload) -> ExecutionResult: ...
