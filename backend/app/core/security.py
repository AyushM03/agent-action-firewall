"""Agent API key helpers.

Keys are shown to the operator once at creation; only their SHA-256 hash is stored.
"""

import hashlib
import hmac
import secrets

API_KEY_PREFIX = "aaf_"


def generate_api_key() -> str:
    """Return a new random agent API key."""
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Return the hex SHA-256 digest used to store and look up a key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """Compare a presented key against a stored hash in constant time."""
    return hmac.compare_digest(hash_api_key(api_key), stored_hash)
