"""
Module 2 (Authentication) business logic: login, refresh-token rotation
with replay detection, logout (single-device and all-devices), account
lockout, email verification, password reset, and change-password.

Every method takes only repository interfaces (app/repositories/interfaces.py)
and pure request data — no FastAPI, no SQLAlchemy session, no HTTP concerns
here, so the entire lockout/rotation/replay state machine is unit-testable
with in-memory fakes (tests/fakes/repositories.py) and identical to what
production runs against real Postgres.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.db.enums import SecurityEventType
from app.models.auth import EmailVerificationToken, PasswordResetToken, RefreshToken, SecurityEvent
from app.models.identity import User
from app.repositories.interfaces import (
    EmailVerificationTokenRepository,
    InviteRepository,
    PasswordResetTokenRepository,
    PermissionRepository,
    RefreshTokenRepository,
    SecurityEventRepository,
    UserRepository,
)
from app.services.email_sender import EmailSender
from app.services.permission_service import PermissionService

_GENERIC_LOGIN_ERROR = "Invalid email or password."


@dataclass(frozen=True)
class DeviceContext:
    """Captured once per request by the route layer (from headers), not guessed by the service."""

    device_name: str | None
    user_agent: str | None
    ip_address: str | None


@dataclass(frozen=True)
class AuthResult:
    user: User
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        email_verification_repo: EmailVerificationTokenRepository,
        password_reset_repo: PasswordResetTokenRepository,
        security_event_repo: SecurityEventRepository,
        permission_repo: PermissionRepository,
        invite_repo: InviteRepository,
        email_sender: EmailSender,
    ) -> None:
        self._settings = settings
        self._users = user_repo
        self._refresh_tokens = refresh_token_repo
        self._email_verification_tokens = email_verification_repo
        self._password_reset_tokens = password_reset_repo
        self._security_events = security_event_repo
        self._permissions = PermissionService(permission_repo)
        self._invites = invite_repo
        self._email_sender = email_sender

    # ------------------------------------------------------------------
    # Signup (creates a User identity only)
    # ------------------------------------------------------------------
    async def signup(
        self, *, email: str, password: str, full_name: str, device: DeviceContext
    ) -> AuthResult:
        """
        `docs/architecture/07-api-design.md` documents `POST /auth/signup`
        as part of Auth's public interface from the start; Module 2 built
        every other listed endpoint but not this one -- the same kind of
        documented-but-deferred gap `accept_invite`'s own docstring already
        called out for Employee provisioning. Completed here, alongside
        that gap, while building Module 4 (Nursery & Organization
        Management), since organization creation (`POST /orgs`,
        `app/services/organization_service.py` +
        `app/services/employee_service.py`'s `provision_owner`) is what
        actually needs an authenticated identity to exist first.

        Deliberately creates *only* the `User` row, exactly like
        `accept_invite` deliberately creates only the `User` row -- this
        method has no idea whether the caller is about to create a new
        Nursery (`POST /orgs`) or has some other reason to hold an
        identity with no org membership yet. Mixing "create a login" and
        "create an organization" into one method would make this the only
        service in the codebase that reaches across the Auth/Organization
        bounded-context boundary; the route layer orchestrates both calls
        in the same request instead (same pattern `POST /auth/invite/accept`
        already uses for `EmployeeService.provision_from_invite`).
        """
        normalized_email = email.strip().lower()
        if await self._users.get_by_email(normalized_email) is not None:
            raise ConflictError("An account already exists for this email address.")

        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            is_active=True,
            is_email_verified=False,
        )
        await self._users.add(user)
        await self._log_event(SecurityEventType.LOGIN_SUCCESS, user_id=user.id, email=user.email, device=device)
        return await self._issue_token_pair(user, device=device, family_id=uuid.uuid4())

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    async def login(self, *, email: str, password: str, device: DeviceContext) -> AuthResult:
        now = datetime.now(timezone.utc)
        normalized_email = email.strip().lower()
        user = await self._users.get_by_email(normalized_email)

        if user is None:
            await self._log_event(
                SecurityEventType.LOGIN_FAILED, email=normalized_email, device=device
            )
            raise AuthenticationError(_GENERIC_LOGIN_ERROR)

        if user.locked_until is not None and _as_aware(user.locked_until) > now:
            await self._log_event(
                SecurityEventType.LOGIN_FAILED, user_id=user.id, email=user.email, device=device,
                metadata={"reason": "account_locked"},
            )
            raise AuthenticationError(
                "Account is temporarily locked due to repeated failed login attempts. "
                "Try again later or reset your password."
            )

        if not user.is_active:
            await self._log_event(
                SecurityEventType.LOGIN_FAILED, user_id=user.id, email=user.email, device=device,
                metadata={"reason": "inactive"},
            )
            raise AuthenticationError(_GENERIC_LOGIN_ERROR)

        if not verify_password(password, user.password_hash):
            await self._register_failed_attempt(user, now=now, device=device)
            raise AuthenticationError(_GENERIC_LOGIN_ERROR)

        # Successful login: reset lockout state, opportunistically rehash
        # under current Argon2id params, stamp last_login_at.
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        await self._log_event(SecurityEventType.LOGIN_SUCCESS, user_id=user.id, email=user.email, device=device)

        return await self._issue_token_pair(user, device=device, family_id=uuid.uuid4())

    async def _register_failed_attempt(self, user: User, *, now: datetime, device: DeviceContext) -> None:
        user.failed_login_attempts += 1
        locked = user.failed_login_attempts >= self._settings.AUTH_MAX_FAILED_LOGIN_ATTEMPTS
        locked_until: datetime | None = None
        if locked:
            locked_until = now + timedelta(minutes=self._settings.AUTH_LOCKOUT_DURATION_MINUTES)
            user.locked_until = locked_until

        await self._log_event(
            SecurityEventType.LOGIN_FAILED, user_id=user.id, email=user.email, device=device,
            metadata={"failed_attempts": user.failed_login_attempts},
        )
        if locked_until is not None:
            # Phase 6 Module 14 (Production Readiness) defect fix: reads
            # the local `locked_until` (assigned two lines above, in the
            # same `if locked:` branch) rather than `user.locked_until`
            # (the ORM attribute) here -- functionally identical (they
            # hold the same value), but mypy can narrow a local variable's
            # `datetime | None` type across control flow, and cannot do
            # the same for an ORM instance attribute re-read after
            # assignment. `mypy app` flagged the original
            # `user.locked_until.isoformat()` as a potential None-access;
            # this was never reachable with None in practice (the
            # assignment above always runs first, in the same branch), but
            # the fix makes that provable to the type checker instead of
            # relying on the two branches staying in sync by convention.
            await self._log_event(
                SecurityEventType.ACCOUNT_LOCKED, user_id=user.id, email=user.email, device=device,
                metadata={"locked_until": locked_until.isoformat()},
            )

        # `login()` raises the generic wrong-password error right after
        # this returns, and the request-level session (app/db/session.py)
        # rolls back on any exception -- so without this explicit commit
        # the counter increment above would be silently discarded and the
        # lockout threshold could never be reached. Committed *before* the
        # raise; see UserRepository.commit()'s docstring.
        await self._users.commit()

    # ------------------------------------------------------------------
    # Refresh token rotation + replay detection
    # ------------------------------------------------------------------
    async def refresh(self, *, raw_refresh_token: str, device: DeviceContext) -> AuthResult:
        now = datetime.now(timezone.utc)
        token_hash = hash_opaque_token(raw_refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)

        if stored is None:
            raise AuthenticationError("Invalid refresh token.")

        if stored.revoked_at is not None:
            if stored.replaced_by_id is not None:
                # This token was already rotated away and is being
                # presented again -- a replay. Revoke the whole family:
                # whoever holds this token may hold others from the same
                # chain.
                await self._refresh_tokens.revoke_family(stored.family_id, now=now)
                await self._log_event(
                    SecurityEventType.TOKEN_REUSE_DETECTED,
                    user_id=stored.user_id,
                    device=device,
                    metadata={"family_id": str(stored.family_id)},
                )
            raise AuthenticationError("Refresh token has been revoked.")

        if _as_aware(stored.expires_at) <= now:
            raise AuthenticationError("Refresh token has expired.")

        user = await self._users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Account is no longer active.")

        # Rotate: revoke the presented token, chain-link it to a freshly
        # issued one in the same family.
        stored.last_used_at = now
        result = await self._issue_token_pair(user, device=device, family_id=stored.family_id)
        new_token_hash = hash_opaque_token(result.refresh_token)
        new_stored = await self._refresh_tokens.get_by_hash(new_token_hash)
        stored.revoked_at = now
        stored.replaced_by_id = new_stored.id if new_stored else None
        await self._refresh_tokens.revoke(stored, now=now)

        await self._log_event(SecurityEventType.TOKEN_REFRESHED, user_id=user.id, device=device)
        return result

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------
    async def logout(self, *, raw_refresh_token: str) -> None:
        token_hash = hash_opaque_token(raw_refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)
        if stored is None or stored.revoked_at is not None:
            return  # Idempotent: logging out an already-invalid token is not an error.
        now = datetime.now(timezone.utc)
        await self._refresh_tokens.revoke(stored, now=now)
        await self._log_event(SecurityEventType.LOGOUT, user_id=stored.user_id)

    async def logout_all(self, *, user_id: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)
        await self._refresh_tokens.revoke_all_for_user(user_id, now=now)
        await self._log_event(SecurityEventType.LOGOUT_ALL, user_id=user_id)

    async def list_sessions(self, *, user_id: uuid.UUID) -> list[RefreshToken]:
        return await self._refresh_tokens.list_active_for_user(user_id)

    async def revoke_session(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        sessions = await self._refresh_tokens.list_active_for_user(user_id)
        target = next((s for s in sessions if s.id == session_id), None)
        if target is None:
            raise NotFoundError("Session not found.")
        await self._refresh_tokens.revoke(target, now=datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------
    async def request_email_verification(self, *, user_id: uuid.UUID) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if user.is_email_verified:
            return

        raw_token, token_hash = generate_opaque_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self._settings.AUTH_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
        )
        await self._email_verification_tokens.add(
            EmailVerificationToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
        )
        await self._log_event(SecurityEventType.EMAIL_VERIFICATION_SENT, user_id=user.id, email=user.email)

        verify_url = f"{self._settings.FRONTEND_BASE_URL}/verify-email?token={raw_token}"
        await self._email_sender.send(
            to=user.email,
            subject="Verify your NurseryVerse AI email address",
            body_text=f"Hi {user.full_name},\n\nVerify your email: {verify_url}\n\nThis link expires in {self._settings.AUTH_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} hours.",
        )

    async def confirm_email_verification(self, *, raw_token: str) -> None:
        token_hash = hash_opaque_token(raw_token)
        stored = await self._email_verification_tokens.get_by_hash(token_hash)
        now = datetime.now(timezone.utc)
        if stored is None or stored.used_at is not None or _as_aware(stored.expires_at) <= now:
            raise ValidationError("Verification token is invalid or has expired.")

        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise NotFoundError("User not found.")

        user.is_email_verified = True
        await self._email_verification_tokens.mark_used(stored, now=now)
        await self._log_event(SecurityEventType.EMAIL_VERIFIED, user_id=user.id, email=user.email)

    # ------------------------------------------------------------------
    # Password reset (forgot password)
    # ------------------------------------------------------------------
    async def request_password_reset(self, *, email: str, ip_address: str | None) -> None:
        # Always returns normally regardless of whether the email exists —
        # revealing account existence via response shape/timing here would
        # be a user-enumeration vulnerability. The security event is still
        # logged either way.
        user = await self._users.get_by_email(email.strip().lower())
        if user is None:
            await self._log_event(SecurityEventType.PASSWORD_RESET_REQUESTED, email=email)
            return

        raw_token, token_hash = generate_opaque_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.AUTH_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        await self._password_reset_tokens.add(
            PasswordResetToken(
                user_id=user.id, token_hash=token_hash, expires_at=expires_at, requested_ip=ip_address
            )
        )
        await self._log_event(SecurityEventType.PASSWORD_RESET_REQUESTED, user_id=user.id, email=user.email)

        reset_url = f"{self._settings.FRONTEND_BASE_URL}/reset-password?token={raw_token}"
        await self._email_sender.send(
            to=user.email,
            subject="Reset your NurseryVerse AI password",
            body_text=f"Hi {user.full_name},\n\nReset your password: {reset_url}\n\nThis link expires in {self._settings.AUTH_PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes. If you didn't request this, you can ignore this email.",
        )

    async def confirm_password_reset(self, *, raw_token: str, new_password: str) -> None:
        token_hash = hash_opaque_token(raw_token)
        stored = await self._password_reset_tokens.get_by_hash(token_hash)
        now = datetime.now(timezone.utc)
        if stored is None or stored.used_at is not None or _as_aware(stored.expires_at) <= now:
            raise ValidationError("Password reset token is invalid or has expired.")

        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise NotFoundError("User not found.")

        user.password_hash = hash_password(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None
        await self._password_reset_tokens.mark_used(stored, now=now)
        # A password reset is treated as "this account may have been
        # compromised" -- revoke every existing session, not just log the
        # event, forcing re-authentication everywhere.
        await self._refresh_tokens.revoke_all_for_user(user.id, now=now)
        await self._log_event(SecurityEventType.PASSWORD_RESET_COMPLETED, user_id=user.id, email=user.email)

    # ------------------------------------------------------------------
    # Change password (authenticated)
    # ------------------------------------------------------------------
    async def change_password(
        self, *, user_id: uuid.UUID, current_password: str, new_password: str
    ) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect.")

        user.password_hash = hash_password(new_password)
        now = datetime.now(timezone.utc)
        await self._refresh_tokens.revoke_all_for_user(user.id, now=now)
        await self._log_event(SecurityEventType.PASSWORD_CHANGED, user_id=user.id, email=user.email)

    # ------------------------------------------------------------------
    # Invite acceptance (sets the initial password for an invited user)
    # ------------------------------------------------------------------
    async def accept_invite(self, *, token: str, password: str, device: DeviceContext) -> AuthResult:
        invite = await self._invites.get_by_token(token)
        now = datetime.now(timezone.utc)
        if invite is None or invite.accepted_at is not None or _as_aware(invite.expires_at) <= now:
            raise ValidationError("Invite token is invalid or has expired.")

        existing = await self._users.get_by_email(invite.email.strip().lower())
        if existing is not None:
            raise ConflictError("An account already exists for this email.")

        user = User(
            email=invite.email.strip().lower(),
            password_hash=hash_password(password),
            full_name=invite.email.split("@")[0],  # Module 5 (User Management) collects the real name
            is_active=True,
            is_email_verified=True,  # invite delivery to this address is itself a form of verification
        )
        await self._users.add(user)
        await self._invites.mark_accepted(invite, now=now)
        # Log the newly-provisioned user straight in, same as a normal
        # login would, so the client doesn't need a second round-trip.
        return await self._issue_token_pair(user, device=device, family_id=uuid.uuid4())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _issue_token_pair(
        self, user: User, *, device: DeviceContext, family_id: uuid.UUID
    ) -> AuthResult:
        access = await self._permissions.resolve_for_user(user.id)
        access_token = create_access_token(
            settings=self._settings,
            user_id=user.id,
            org_id=access.org_id,
            branch_ids=access.branch_ids,
            role_code=access.role_code,
            permissions=access.permissions,
        )

        raw_refresh_token, refresh_hash = generate_opaque_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self._settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self._refresh_tokens.add(
            RefreshToken(
                user_id=user.id,
                token_hash=refresh_hash,
                family_id=family_id,
                device_name=device.device_name,
                user_agent=device.user_agent,
                ip_address=device.ip_address,
                expires_at=expires_at,
            )
        )

        return AuthResult(
            user=user,
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def _log_event(
        self,
        event_type: SecurityEventType,
        *,
        user_id: uuid.UUID | None = None,
        email: str | None = None,
        device: DeviceContext | None = None,
        metadata: dict | None = None,
    ) -> None:
        await self._security_events.log(
            SecurityEvent(
                user_id=user_id,
                email=email,
                event_type=event_type,
                ip_address=device.ip_address if device else None,
                user_agent=device.user_agent if device else None,
                event_metadata=metadata,
            )
        )


def _as_aware(value: datetime) -> datetime:
    """Fakes/SQLite-free unit tests may hand back naive datetimes; treat naive as UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
