"""
Unit tests for app/services/auth_service.py — the core of Module 2.
Covers every item in the module's own validation checklist: JWT issuance/
claims, refresh rotation, role/permission resolution on the token, logout
+ revocation, password reset flow, and account lockout.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.core.security import decode_access_token, hash_opaque_token, verify_password
from app.db.enums import SecurityEventType
from app.models.identity import Invite

pytestmark = pytest.mark.unit


# ----------------------------------------------------------------------
# Login
# ----------------------------------------------------------------------
async def test_login_success_issues_valid_access_and_refresh_tokens(harness, device):
    user = await harness.create_user(password="Correct-Horse12")

    result = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)

    assert result.user.id == user.id
    payload = decode_access_token(result.access_token, settings=harness.settings)
    assert payload["sub"] == str(user.id)
    stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(result.refresh_token))
    assert stored is not None
    assert stored.revoked_at is None


async def test_login_success_resets_failed_attempts_and_stamps_last_login(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    user.failed_login_attempts = 2

    await harness.service.login(email=user.email, password="Correct-Horse12", device=device)

    assert user.failed_login_attempts == 0
    assert user.last_login_at is not None


async def test_login_wrong_password_raises_generic_error(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await harness.service.login(email=user.email, password="WrongPassword1", device=device)


async def test_login_unknown_email_raises_same_generic_error(harness, device):
    # Same message/shape as wrong-password -- prevents user enumeration.
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await harness.service.login(email="nobody@example.com", password="whatever123A", device=device)


async def test_login_wrong_password_increments_failed_attempts(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    with pytest.raises(AuthenticationError):
        await harness.service.login(email=user.email, password="wrong", device=device)
    assert user.failed_login_attempts == 1


async def test_account_locks_after_max_failed_attempts(harness, device):
    user = await harness.create_user(password="Correct-Horse12")  # harness limit = 3
    for _ in range(3):
        with pytest.raises(AuthenticationError):
            await harness.service.login(email=user.email, password="wrong", device=device)

    assert user.locked_until is not None
    assert user.locked_until > datetime.now(timezone.utc)


async def test_locked_account_rejects_even_correct_password(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    for _ in range(3):
        with pytest.raises(AuthenticationError):
            await harness.service.login(email=user.email, password="wrong", device=device)

    with pytest.raises(AuthenticationError, match="temporarily locked"):
        await harness.service.login(email=user.email, password="Correct-Horse12", device=device)


async def test_login_logs_security_events(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    event_types = [e.event_type for e in harness.security_events.events]
    assert SecurityEventType.LOGIN_SUCCESS in event_types


async def test_account_lockout_logs_account_locked_event(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    for _ in range(3):
        with pytest.raises(AuthenticationError):
            await harness.service.login(email=user.email, password="wrong", device=device)
    event_types = [e.event_type for e in harness.security_events.events]
    assert SecurityEventType.ACCOUNT_LOCKED in event_types


async def test_inactive_account_cannot_login(harness, device):
    user = await harness.create_user(password="Correct-Horse12", is_active=False)
    with pytest.raises(AuthenticationError):
        await harness.service.login(email=user.email, password="Correct-Horse12", device=device)


# ----------------------------------------------------------------------
# Role / permission resolution on the issued token
# ----------------------------------------------------------------------
async def test_access_token_carries_resolved_role_and_permissions(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    org_id = uuid.uuid4()
    harness.grant_role(
        user, org_id=org_id, role_code="branch_manager", permission_codes=["plants:read", "plants:write"]
    )

    result = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    payload = decode_access_token(result.access_token, settings=harness.settings)

    assert payload["org_id"] == str(org_id)
    assert payload["role"] == "branch_manager"
    assert sorted(payload["permissions"]) == ["plants:read", "plants:write"]


async def test_user_with_no_role_assignment_gets_empty_permissions(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    result = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    payload = decode_access_token(result.access_token, settings=harness.settings)
    assert payload["org_id"] is None
    assert payload["permissions"] == []


# ----------------------------------------------------------------------
# Refresh rotation + replay detection
# ----------------------------------------------------------------------
async def test_refresh_rotates_to_a_new_token_and_revokes_the_old_one(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    first = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)

    second = await harness.service.refresh(raw_refresh_token=first.refresh_token, device=device)

    assert second.refresh_token != first.refresh_token
    old_stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(first.refresh_token))
    assert old_stored.revoked_at is not None
    assert old_stored.replaced_by_id is not None


async def test_refresh_preserves_family_id_across_rotation(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    first = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    old_stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(first.refresh_token))

    second = await harness.service.refresh(raw_refresh_token=first.refresh_token, device=device)
    new_stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(second.refresh_token))

    assert new_stored.family_id == old_stored.family_id


async def test_refresh_with_unknown_token_raises(harness, device):
    with pytest.raises(AuthenticationError):
        await harness.service.refresh(raw_refresh_token="not-a-real-token", device=device)


async def test_refresh_with_expired_token_raises(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    result = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(result.refresh_token))
    stored.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

    with pytest.raises(AuthenticationError, match="expired"):
        await harness.service.refresh(raw_refresh_token=result.refresh_token, device=device)


async def test_replaying_an_already_rotated_token_is_detected_and_revokes_the_family(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    first = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    second = await harness.service.refresh(raw_refresh_token=first.refresh_token, device=device)

    # Attacker (or a race) replays the already-rotated-away first token.
    with pytest.raises(AuthenticationError, match="revoked"):
        await harness.service.refresh(raw_refresh_token=first.refresh_token, device=device)

    # The entire family -- including the token that replay just issued
    # moments ago -- must now be revoked, not just the replayed one.
    second_stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(second.refresh_token))
    assert second_stored.revoked_at is not None

    event_types = [e.event_type for e in harness.security_events.events]
    assert SecurityEventType.TOKEN_REUSE_DETECTED in event_types


async def test_refresh_of_already_logged_out_token_raises_without_touching_the_family(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    result = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    await harness.service.logout(raw_refresh_token=result.refresh_token)

    with pytest.raises(AuthenticationError):
        await harness.service.refresh(raw_refresh_token=result.refresh_token, device=device)

    # A plain logout-then-reuse is not a detected replay (no
    # replaced_by_id was ever set), so no TOKEN_REUSE_DETECTED event.
    event_types = [e.event_type for e in harness.security_events.events]
    assert SecurityEventType.TOKEN_REUSE_DETECTED not in event_types


# ----------------------------------------------------------------------
# Logout / session management
# ----------------------------------------------------------------------
async def test_logout_revokes_only_the_presented_token(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    session_a = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    session_b = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)

    await harness.service.logout(raw_refresh_token=session_a.refresh_token)

    a_stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(session_a.refresh_token))
    b_stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(session_b.refresh_token))
    assert a_stored.revoked_at is not None
    assert b_stored.revoked_at is None


async def test_logout_is_idempotent(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    result = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    await harness.service.logout(raw_refresh_token=result.refresh_token)
    await harness.service.logout(raw_refresh_token=result.refresh_token)  # must not raise


async def test_logout_all_revokes_every_session(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    session_a = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    session_b = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)

    await harness.service.logout_all(user_id=user.id)

    a_stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(session_a.refresh_token))
    b_stored = await harness.refresh_tokens.get_by_hash(hash_opaque_token(session_b.refresh_token))
    assert a_stored.revoked_at is not None
    assert b_stored.revoked_at is not None


async def test_list_sessions_only_returns_active_ones(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    session_a = await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    await harness.service.logout(raw_refresh_token=session_a.refresh_token)

    active = await harness.service.list_sessions(user_id=user.id)
    assert len(active) == 1


async def test_revoke_session_by_id(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    [session] = await harness.service.list_sessions(user_id=user.id)

    await harness.service.revoke_session(user_id=user.id, session_id=session.id)

    assert await harness.service.list_sessions(user_id=user.id) == []


async def test_revoke_nonexistent_session_raises_not_found(harness):
    user = await harness.create_user(password="Correct-Horse12")
    with pytest.raises(NotFoundError):
        await harness.service.revoke_session(user_id=user.id, session_id=uuid.uuid4())


# ----------------------------------------------------------------------
# Password reset
# ----------------------------------------------------------------------
async def test_password_reset_request_sends_an_email_for_a_real_user(harness):
    user = await harness.create_user(password="Correct-Horse12")
    await harness.service.request_password_reset(email=user.email, ip_address="1.2.3.4")
    assert len(harness.email_sender.sent) == 1
    assert harness.email_sender.sent[0]["to"] == user.email


async def test_password_reset_request_for_unknown_email_does_not_error_or_send(harness):
    await harness.service.request_password_reset(email="nobody@example.com", ip_address="1.2.3.4")
    assert harness.email_sender.sent == []  # nothing to send, but no exception either


async def test_password_reset_confirm_changes_password_and_revokes_all_sessions(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    await harness.service.login(email=user.email, password="Correct-Horse12", device=device)
    await harness.service.request_password_reset(email=user.email, ip_address="1.2.3.4")

    # Recover the raw token from the fake token store's persisted hash is
    # not possible (only the hash is stored, by design) -- so read it back
    # off the fake email sender instead, exactly like a user clicking the
    # emailed link would.
    body = harness.email_sender.sent[0]["body"]
    raw_token = body.split("token=")[1].split()[0].strip()

    await harness.service.confirm_password_reset(raw_token=raw_token, new_password="New-Correct-Horse99")

    refreshed = await harness.users.get_by_id(user.id)
    assert verify_password("New-Correct-Horse99", refreshed.password_hash)
    assert await harness.service.list_sessions(user_id=user.id) == []


async def test_password_reset_confirm_with_bad_token_raises(harness):
    with pytest.raises(ValidationError):
        await harness.service.confirm_password_reset(raw_token="not-a-real-token", new_password="New-Correct-Horse99")


async def test_password_reset_token_is_single_use(harness):
    user = await harness.create_user(password="Correct-Horse12")
    await harness.service.request_password_reset(email=user.email, ip_address=None)
    raw_token = harness.email_sender.sent[0]["body"].split("token=")[1].split()[0].strip()

    await harness.service.confirm_password_reset(raw_token=raw_token, new_password="New-Correct-Horse99")
    with pytest.raises(ValidationError):
        await harness.service.confirm_password_reset(raw_token=raw_token, new_password="Another-Horse123")


# ----------------------------------------------------------------------
# Change password (authenticated)
# ----------------------------------------------------------------------
async def test_change_password_success_revokes_other_sessions(harness, device):
    user = await harness.create_user(password="Correct-Horse12")
    await harness.service.login(email=user.email, password="Correct-Horse12", device=device)

    await harness.service.change_password(
        user_id=user.id, current_password="Correct-Horse12", new_password="Brand-New-Horse42"
    )

    refreshed = await harness.users.get_by_id(user.id)
    assert verify_password("Brand-New-Horse42", refreshed.password_hash)
    assert await harness.service.list_sessions(user_id=user.id) == []


async def test_change_password_wrong_current_password_raises(harness):
    user = await harness.create_user(password="Correct-Horse12")
    with pytest.raises(AuthenticationError):
        await harness.service.change_password(
            user_id=user.id, current_password="WrongOne123", new_password="Brand-New-Horse42"
        )


# ----------------------------------------------------------------------
# Email verification
# ----------------------------------------------------------------------
async def test_email_verification_request_and_confirm(harness):
    user = await harness.create_user(password="Correct-Horse12")
    assert user.is_email_verified is False

    await harness.service.request_email_verification(user_id=user.id)
    raw_token = harness.email_sender.sent[0]["body"].split("token=")[1].split()[0].strip()

    await harness.service.confirm_email_verification(raw_token=raw_token)
    assert user.is_email_verified is True


async def test_email_verification_confirm_with_bad_token_raises(harness):
    with pytest.raises(ValidationError):
        await harness.service.confirm_email_verification(raw_token="garbage")


async def test_already_verified_user_does_not_get_a_second_email(harness):
    user = await harness.create_user(password="Correct-Horse12", is_email_verified=True)
    await harness.service.request_email_verification(user_id=user.id)
    assert harness.email_sender.sent == []


# ----------------------------------------------------------------------
# Invite acceptance
# ----------------------------------------------------------------------
async def test_accept_invite_creates_a_user_and_logs_them_in(harness, device):
    invite = Invite(
        id=uuid.uuid4(),
        nursery_id=uuid.uuid4(),
        invited_by_user_id=uuid.uuid4(),
        email="newhire@example.com",
        role_id=uuid.uuid4(),
        token="invite-token-abc",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    harness.invites.invites[invite.token] = invite

    result = await harness.service.accept_invite(
        token="invite-token-abc", password="Brand-New-Horse42", device=device
    )

    assert result.user.email == "newhire@example.com"
    assert invite.accepted_at is not None
    assert result.access_token  # a real, usable token pair was issued


async def test_accept_invite_with_expired_token_raises(harness, device):
    invite = Invite(
        id=uuid.uuid4(),
        nursery_id=uuid.uuid4(),
        invited_by_user_id=uuid.uuid4(),
        email="newhire@example.com",
        role_id=uuid.uuid4(),
        token="expired-token",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    harness.invites.invites[invite.token] = invite

    with pytest.raises(ValidationError):
        await harness.service.accept_invite(token="expired-token", password="Brand-New-Horse42", device=device)


async def test_accept_invite_for_already_registered_email_raises_conflict(harness, device):
    await harness.create_user(email="taken@example.com", password="Correct-Horse12")
    invite = Invite(
        id=uuid.uuid4(),
        nursery_id=uuid.uuid4(),
        invited_by_user_id=uuid.uuid4(),
        email="taken@example.com",
        role_id=uuid.uuid4(),
        token="dup-token",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    harness.invites.invites[invite.token] = invite

    with pytest.raises(ConflictError):
        await harness.service.accept_invite(token="dup-token", password="Brand-New-Horse42", device=device)
