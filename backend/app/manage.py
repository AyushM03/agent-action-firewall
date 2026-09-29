"""Operator commands for local development.

Usage (from backend/):
    python -m app.manage create-approver <username>     # prompts for a password
    python -m app.manage issue-agent-key <agent-name>   # prints the new key once
"""

import argparse
import asyncio
import getpass
import sys

from app.core.db import async_session, engine
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


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("create-approver").add_argument("username")
    commands.add_parser("issue-agent-key").add_argument("agent_name")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
