from app.core.security import API_KEY_PREFIX, generate_api_key, hash_api_key, verify_api_key


def test_generated_keys_are_prefixed_and_unique():
    a, b = generate_api_key(), generate_api_key()
    assert a.startswith(API_KEY_PREFIX)
    assert a != b


def test_verify_accepts_matching_key_and_rejects_others():
    key = generate_api_key()
    stored = hash_api_key(key)
    assert verify_api_key(key, stored)
    assert not verify_api_key(generate_api_key(), stored)
