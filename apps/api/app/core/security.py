"""
Cryptographic primitives for Module 2 (Authentication): password hashing,
JWT access-token signing/verification, and opaque-token generation/hashing
for refresh/verification/reset tokens.

Design decisions, per the module's explicit requirements:

- **Password hashing: Argon2id**, not bcrypt (argon2-cffi, not passlib).
  Argon2id is the OWASP-recommended default for new systems — memory-hard,
  resists both GPU/ASIC cracking (side-channel-resistant like Argon2i) and
  the pure-Argon2i weakness to cache-timing attacks in a way plain Argon2d
  doesn't, since it's the hybrid of both. Parameters below follow OWASP's
  2023 Argon2id guidance (m=19456 KiB, t=2, p=1) rather than argon2-cffi's
  library default (m=65536, t=3, p=4) — OWASP's profile is tuned to a
  ~decent-server target of well under 1 second per hash while still being
  expensive enough to blunt offline cracking; the library default is
  heavier than most API request budgets comfortably allow under load.

- **JWT: RS256**, asymmetric. The API signs with a private key; anything
  that only needs to *verify* a token (a future separate worker process,
  or resource server) only ever needs the public key — it structurally
  cannot forge a token even if compromised. HS256 would mean every service
  capable of verifying tokens also holds the secret capable of minting
  them.

- **Refresh/verification/reset tokens are opaque**, not JWTs. A JWT is
  self-describing and can't be individually revoked without a server-side
  denylist anyway — so for anything that needs revocation as a first-class
  operation (refresh tokens especially), a random opaque token whose
  *hash* is the only thing ever persisted (this module's "hash before
  storage" requirement) is both simpler and gives the DB row itself as the
  natural revocation point (`revoked_at`/`used_at`).
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.keys import resolve_jwt_keys

# OWASP-recommended Argon2id parameters (2023 cheat sheet, "second
# recommended option" tier — tuned for typical API server hardware).
_password_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,  # 19 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

JWT_TOKEN_TYPE_ACCESS = "access"


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        _password_hasher.verify(password_hash, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False
    return True


def needs_rehash(password_hash: str) -> bool:
    """
    True if a hash was created under older/weaker parameters than the
    current `_password_hasher` config — the service layer calls this
    right after a successful login and, if true, re-hashes the (already
    verified) plaintext and updates the stored hash. This is how a
    password-hashing parameter upgrade ever reaches existing users without
    a forced mass password reset.
    """
    return _password_hasher.check_needs_rehash(password_hash)


def generate_opaque_token() -> tuple[str, str]:
    """
    Returns `(raw_token, token_hash)`. `raw_token` is what's sent to the
    client (in the response body, or a verification/reset link) and never
    stored; `token_hash` (SHA-256 hex digest) is what's persisted. SHA-256
    is appropriate here — unlike a password, this token is already
    high-entropy random data (32 bytes / 256 bits from
    `secrets.token_urlsafe`), not a human-memorable secret, so a fast hash
    is fine: the security property being defended is "a stolen DB dump
    can't be replayed as the token", not "resist brute-forcing a
    low-entropy secret" (that's what Argon2id above is for).
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_opaque_token(raw_token)
    return raw_token, token_hash


def hash_opaque_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    settings: Settings,
    user_id: uuid.UUID,
    org_id: uuid.UUID | None,
    branch_ids: list[uuid.UUID] | None,
    role_code: str | None,
    permissions: list[str],
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "type": JWT_TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "org_id": str(org_id) if org_id else None,
        "branch_ids": [str(b) for b in branch_ids] if branch_ids else [],
        "role": role_code,
        "permissions": permissions,
    }
    keys = resolve_jwt_keys(settings)
    return jwt.encode(claims, keys.private_key, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str, *, settings: Settings) -> dict[str, Any]:
    keys = resolve_jwt_keys(settings)
    try:
        payload = jwt.decode(token, keys.public_key, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc
    if payload.get("type") != JWT_TOKEN_TYPE_ACCESS:
        raise AuthenticationError("Token is not an access token.")
    return payload
