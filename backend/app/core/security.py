"""Credential helpers: agent API keys, approver passwords, approver JWTs.

Agent keys are shown to the operator once at creation; only their SHA-256 hash
is stored. Approver passwords are stored as bcrypt hashes.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

API_KEY_PREFIX = "aaf_"

# bcrypt only looks at the first 72 bytes; longer passwords are refused, not truncated.
MAX_PASSWORD_BYTES = 72


def generate_api_key() -> str:
    """Return a new random agent API key."""
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Return the hex SHA-256 digest used to store and look up a key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Compare a presented key against a stored hash in constant time."""
    return hmac.compare_digest(hash_api_key(api_key), stored_hash)


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, stored_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, stored_hash.encode("ascii"))


# Checked against when the username doesn't exist, so login takes the same time either way.
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def create_access_token(username: str, now: datetime | None = None) -> str:
    issued = now or datetime.now(UTC)
    claims = {
        "sub": username,
        "role": "approver",
        "iat": issued,
        "exp": issued + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the approver username from a valid token, or None."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if claims.get("role") != "approver" or not isinstance(claims.get("sub"), str):
        return None
    return claims["sub"]
