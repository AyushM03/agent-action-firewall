"""Operator commands for local development.

Usage (from backend/):
    python -m app.manage create-approver <username>     # prompts for a password
    python -m app.manage issue-agent-key <agent-name>   # prints the new key once
    python -m app.manage gmail-auth                     # one-time OAuth consent, prints GMAIL_REFRESH_TOKEN
"""

import argparse
import asyncio
import getpass
import sys

from app.core.config import settings
from app.core.db import async_session, engine
from app.executors.gmail import GMAIL_SEND_SCOPE
from app.services.accounts import AccountError, create_approver, issue_agent_key


async def run(args: argparse.Namespace) -> None:
    engine.echo = False
    try:
        async with async_session() as session:
            if args.command == "create-approver":
                password = getpass.getpass("Password: ")
                if password != getpass.getpass("Repeat password: "):
                    sys.exit("Passwords don't match.")
                if len(password) < 8:
                    sys.exit("Password must be at least 8 characters.")
                await create_approver(session, args.username, password)
                print(f"Created approver '{args.username}'.")
            else:
                api_key = await issue_agent_key(session, args.agent_name)
                print(f"API key for '{args.agent_name}' (shown once, any previous key no longer works):")
                print(api_key)
    except (AccountError, ValueError) as exc:
        sys.exit(str(exc))
    finally:
        await engine.dispose()


def gmail_auth() -> None:
    """Run the OAuth consent flow for the send-only scope and print the refresh token for backend/.env."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not (settings.gmail_client_id and settings.gmail_client_secret):
        sys.exit("Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in backend/.env first (OAuth client type: Desktop app).")
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=[GMAIL_SEND_SCOPE],
    )
    credentials = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    print("Add this to backend/.env (keep it secret, never commit it):")
    print(f"GMAIL_REFRESH_TOKEN={credentials.refresh_token}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("create-approver").add_argument("username")
    commands.add_parser("issue-agent-key").add_argument("agent_name")
    commands.add_parser("gmail-auth")
    args = parser.parse_args()
    if args.command == "gmail-auth":
        gmail_auth()
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
