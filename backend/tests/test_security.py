from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    API_KEY_PREFIX,
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)


def test_generated_keys_are_prefixed_and_unique():
    a, b = generate_api_key(), generate_api_key()
    assert a.startswith(API_KEY_PREFIX)
    assert a != b


def test_verify_accepts_matching_key_and_rejects_others():
    key = generate_api_key()
    stored = hash_api_key(key)
    assert verify_api_key(key, stored)
    assert not verify_api_key(generate_api_key(), stored)


def test_password_hash_verifies_only_the_right_password():
    stored = hash_password("correct horse")
    assert stored != "correct horse"
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong horse", stored)


def test_passwords_over_72_bytes_are_refused_not_truncated():
    with pytest.raises(ValueError):
        hash_password("x" * 73)
    stored = hash_password("x" * 72)
    assert not verify_password("x" * 72 + "extra", stored)


def test_access_token_round_trips_username():
    assert decode_access_token(create_access_token("alice")) == "alice"


def test_expired_token_is_rejected():
    issued = datetime.now(UTC) - timedelta(minutes=settings.jwt_expire_minutes + 1)
    assert decode_access_token(create_access_token("alice", now=issued)) is None


def test_token_signed_with_another_secret_is_rejected():
    forged = jwt.encode({"sub": "alice", "role": "approver"}, "not-the-secret", algorithm="HS256")
    assert decode_access_token(forged) is None


def test_token_without_approver_role_is_rejected():
    token = jwt.encode({"sub": "alice", "role": "agent"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    assert decode_access_token(token) is None


def test_garbage_token_is_rejected():
    assert decode_access_token("not.a.jwt") is None
