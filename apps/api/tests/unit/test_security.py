"""Unit tests for app/core/security.py — hashing, JWT, opaque tokens."""
from __future__ import annotations

import uuid

import pytest

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    needs_rehash,
    verify_password,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, APP_ENV="test")


@pytest.mark.unit
def test_password_hash_is_argon2id():
    hashed = hash_password("Sup3rSecret!Pass")
    assert hashed.startswith("$argon2id$")


@pytest.mark.unit
def test_password_hash_verifies_correct_password():
    hashed = hash_password("Sup3rSecret!Pass")
    assert verify_password("Sup3rSecret!Pass", hashed) is True


@pytest.mark.unit
def test_password_hash_rejects_wrong_password():
    hashed = hash_password("Sup3rSecret!Pass")
    assert verify_password("WrongPassword!1", hashed) is False


@pytest.mark.unit
def test_password_hash_is_salted_differently_each_time():
    h1 = hash_password("Sup3rSecret!Pass")
    h2 = hash_password("Sup3rSecret!Pass")
    assert h1 != h2


@pytest.mark.unit
def test_needs_rehash_false_for_current_params():
    hashed = hash_password("Sup3rSecret!Pass")
    assert needs_rehash(hashed) is False


@pytest.mark.unit
def test_generate_opaque_token_returns_raw_and_hash_that_match():
    raw, digest = generate_opaque_token()
    assert digest == hash_opaque_token(raw)


@pytest.mark.unit
def test_opaque_tokens_are_unique():
    raw1, _ = generate_opaque_token()
    raw2, _ = generate_opaque_token()
    assert raw1 != raw2


@pytest.mark.unit
def test_access_token_roundtrip(settings: Settings):
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    token = create_access_token(
        settings=settings,
        user_id=user_id,
        org_id=org_id,
        branch_ids=[],
        role_code="branch_manager",
        permissions=["plants:read", "plants:write"],
    )
    payload = decode_access_token(token, settings=settings)
    assert payload["sub"] == str(user_id)
    assert payload["org_id"] == str(org_id)
    assert payload["role"] == "branch_manager"
    assert payload["permissions"] == ["plants:read", "plants:write"]
    assert payload["type"] == "access"


@pytest.mark.unit
def test_access_token_rejects_expired_token(settings: Settings):
    expired_settings = Settings(_env_file=None, APP_ENV="test", JWT_ACCESS_TOKEN_EXPIRE_MINUTES=-1)
    token = create_access_token(
        settings=expired_settings,
        user_id=uuid.uuid4(),
        org_id=None,
        branch_ids=None,
        role_code=None,
        permissions=[],
    )
    with pytest.raises(AuthenticationError):
        decode_access_token(token, settings=expired_settings)


@pytest.mark.unit
def test_access_token_rejects_tampering(settings: Settings):
    token = create_access_token(
        settings=settings,
        user_id=uuid.uuid4(),
        org_id=None,
        branch_ids=None,
        role_code=None,
        permissions=[],
    )
    tampered = token[:-4] + ("abcd" if token[-4:] != "abcd" else "efgh")
    with pytest.raises(AuthenticationError):
        decode_access_token(tampered, settings=settings)


@pytest.mark.unit
def test_access_token_rejects_wrong_keypair(settings: Settings):
    """
    A token signed under one ephemeral dev keypair must fail verification
    once the process-cached keypair changes -- proving decode_access_token
    actually checks the signature against the *current* public key rather
    than trusting the token's claims unconditionally.
    """
    from app.core.keys import _generate_ephemeral_keypair

    _generate_ephemeral_keypair.cache_clear()
    token = create_access_token(
        settings=settings, user_id=uuid.uuid4(), org_id=None, branch_ids=None, role_code=None, permissions=[]
    )
    _generate_ephemeral_keypair.cache_clear()  # forces a fresh (different) keypair on next resolve
    with pytest.raises(AuthenticationError):
        decode_access_token(token, settings=settings)
    _generate_ephemeral_keypair.cache_clear()
