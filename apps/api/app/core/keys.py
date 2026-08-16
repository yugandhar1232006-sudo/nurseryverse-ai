"""
JWT RS256 key resolution. Production must supply real, persistent
`JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` PEM strings via the environment
(generated once at deploy time and kept stable — rotating them
invalidates every outstanding token) — this module fails fast rather than
silently running an insecure default if `settings.is_production` and no
key is configured.

Development/test convenience: if no key is configured and the environment
is NOT production, an ephemeral RSA-2048 keypair is generated once per
process and cached (`lru_cache`) — real RS256 signing/verification, just
with a key that doesn't survive a restart, which is fine for local dev
(existing tokens simply stop verifying after a reload, the same as
restarting any dev server clears in-memory state) and is exactly what
lets `tests/conftest.py` and a fresh `docker compose up` work without
anyone hand-generating a keypair first.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import Settings


@dataclass(frozen=True)
class JwtKeyPair:
    private_key: str
    public_key: str


@lru_cache(maxsize=8)
def _generate_ephemeral_keypair() -> JwtKeyPair:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return JwtKeyPair(private_key=private_pem, public_key=public_pem)


def resolve_jwt_keys(settings: Settings) -> JwtKeyPair:
    if settings.JWT_PRIVATE_KEY and settings.JWT_PUBLIC_KEY:
        return JwtKeyPair(private_key=settings.JWT_PRIVATE_KEY, public_key=settings.JWT_PUBLIC_KEY)

    if settings.is_production:
        raise RuntimeError(
            "JWT_PRIVATE_KEY/JWT_PUBLIC_KEY must be set in production — refusing to start "
            "with an ephemeral signing key, which would invalidate every session on every "
            "process restart and cannot be trusted across multiple API instances."
        )

    # Cached per-process so every call within one running app gets the
    # same keypair (a fresh one each call would make every previously
    # issued token unverifiable within the same process).
    return _generate_ephemeral_keypair()
