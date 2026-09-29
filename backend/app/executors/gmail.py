"""Send email through the Gmail API with the send-only OAuth scope (SECURITY.md)."""

import asyncio
import base64
import uuid
from email.message import EmailMessage

from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.executors.base import ExecutionError, ExecutionResult
from app.executors.payloads import Payload, SendEmailPayload

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
TOKEN_URI = "https://oauth2.googleapis.com/token"


class GmailExecutor:
    actor = "executor:gmail"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, sender: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._sender = sender

    @property
    def configured(self) -> bool:
        return all((self._client_id, self._client_secret, self._refresh_token, self._sender))

    def build_message(self, request_id: uuid.UUID, payload: SendEmailPayload) -> EmailMessage:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = payload.to
        message["Subject"] = payload.subject
        message["X-Agent-Firewall-Request"] = str(request_id)
        message.set_content(payload.body)
        return message

    def _send(self, message: EmailMessage) -> dict:
        credentials = Credentials(
            None,
            refresh_token=self._refresh_token,
            token_uri=TOKEN_URI,
            client_id=self._client_id,
            client_secret=self._client_secret,
            scopes=[GMAIL_SEND_SCOPE],
        )
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        return service.users().messages().send(userId="me", body={"raw": raw}).execute()

    async def execute(self, request_id: uuid.UUID, payload: Payload) -> ExecutionResult:
        assert isinstance(payload, SendEmailPayload)
        if not self.configured:
            raise ExecutionError("not_configured", "Gmail executor is not configured (GMAIL_* env vars).")
        message = self.build_message(request_id, payload)
        try:
            sent = await asyncio.to_thread(self._send, message)
        except GoogleAuthError:
            raise ExecutionError("auth_failed", "Gmail rejected the OAuth credentials (refresh token invalid or revoked).")
        except HttpError as exc:
            raise ExecutionError("gmail_error", f"Gmail API returned HTTP {exc.resp.status}.")
        except OSError:
            raise ExecutionError("network_error", "Could not reach the Gmail API.")
        return ExecutionResult(sent["id"], {"thread_id": sent.get("threadId"), "to": payload.to})
