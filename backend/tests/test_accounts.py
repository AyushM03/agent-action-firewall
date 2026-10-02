"""Approver password reset (services/accounts.py, `python -m app.manage reset-approver-password`)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import manage
from app.services.accounts import AccountError, authenticate_approver, create_approver, reset_approver_password
from tests.test_api import PASSWORD, unique_name

NEW_PASSWORD = "a brand new passphrase"


async def test_reset_replaces_the_password(db: AsyncSession, client: AsyncClient) -> None:
    username = unique_name("approver")
    await create_approver(db, username, PASSWORD)

    await reset_approver_password(db, username, NEW_PASSWORD)

    assert await authenticate_approver(db, username, PASSWORD) is None
    assert await authenticate_approver(db, username, NEW_PASSWORD) is not None
    response = await client.post("/auth/login", json={"username": username, "password": NEW_PASSWORD})
    assert response.status_code == 200


async def test_reset_unknown_approver_fails(db: AsyncSession) -> None:
    with pytest.raises(AccountError, match="No approver named"):
        await reset_approver_password(db, unique_name("nobody"), NEW_PASSWORD)


async def test_reset_does_not_reactivate_a_deactivated_approver(db: AsyncSession) -> None:
    username = unique_name("approver")
    approver = await create_approver(db, username, PASSWORD)
    approver.is_active = False
    await db.flush()

    await reset_approver_password(db, username, NEW_PASSWORD)

    assert approver.is_active is False
    assert await authenticate_approver(db, username, NEW_PASSWORD) is None


async def test_too_long_password_is_refused_and_old_one_kept(db: AsyncSession) -> None:
    username = unique_name("approver")
    await create_approver(db, username, PASSWORD)

    with pytest.raises(ValueError, match="at most 72 bytes"):
        await reset_approver_password(db, username, "x" * 73)

    assert await authenticate_approver(db, username, PASSWORD) is not None


@pytest.mark.parametrize(
    ("typed", "error"),
    [(["long enough 1", "long enough 2"], "don't match"), (["short", "short"], "at least 8")],
)
def test_cli_prompt_rejects_bad_passwords(monkeypatch: pytest.MonkeyPatch, typed: list[str], error: str) -> None:
    answers = iter(typed)
    monkeypatch.setattr(manage.getpass, "getpass", lambda prompt: next(answers))

    with pytest.raises(SystemExit, match=error):
        manage.prompt_new_password("New password")


def test_cli_prompt_returns_a_confirmed_password(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []

    def fake_getpass(prompt: str) -> str:
        prompts.append(prompt)
        return NEW_PASSWORD

    monkeypatch.setattr(manage.getpass, "getpass", fake_getpass)

    assert manage.prompt_new_password("New password") == NEW_PASSWORD
    assert prompts == ["New password: ", "Repeat new password: "]
