"""Payload schema for each supported action type (SECURITY.md: Input Validation).

Validated by the decision flow before policy runs, and parsed again by the
executor. Unknown fields are rejected so an agent can't smuggle in parameters
that a policy rule never looked at.
"""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints, ValidationError

# One address, no display name. Deliberately simple: Gmail does the real validation.
EmailAddress = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")
]
# No CR/LF, so a subject can't inject extra MIME headers.
HeaderText = Annotated[str, StringConstraints(min_length=1, max_length=200, pattern=r"^[^\r\n]*$")]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SendEmailPayload(Payload):
    to: EmailAddress
    subject: HeaderText
    body: str = Field(min_length=1, max_length=20_000)


class MakePaymentPayload(Payload):
    # Integer cents (matches policy conditions like amount <= 5000). Stripe's USD minimum is 50.
    amount: StrictInt = Field(ge=50, le=1_000_000)
    currency: str = Field(default="usd", pattern=r"^[a-z]{3}$")
    description: str | None = Field(default=None, max_length=500)


PAYLOAD_SCHEMAS: dict[str, type[Payload]] = {
    "send_email": SendEmailPayload,
    "make_payment": MakePaymentPayload,
}


class UnknownActionTypeError(Exception):
    pass


class InvalidPayloadError(Exception):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__(f"{len(errors)} validation error(s)")
        self.errors = errors


def parse_payload(action_type: str, payload: dict[str, Any]) -> Payload:
    schema = PAYLOAD_SCHEMAS.get(action_type)
    if schema is None:
        raise UnknownActionTypeError(action_type)
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        # Location and message only: the submitted values are already stored on the request.
        raise InvalidPayloadError(
            [{"loc": ".".join(str(p) for p in err["loc"]), "msg": err["msg"]} for err in exc.errors()]
        ) from exc
