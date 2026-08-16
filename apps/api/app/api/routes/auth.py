"""
Module 2 (Authentication) REST API. Every endpoint returns the standard
error envelope on failure (app/core/error_handlers.py — nothing here
raises a bare HTTPException) and is documented for OpenAPI via docstrings
+ `response_model`/`responses`, per the module's "every endpoint must
include ... OpenAPI documentation" requirement.

Rate limiting is applied per-IP on the two endpoints that are the classic
brute-force/enumeration targets (login, password-reset-request);
everything else relies on the account-lockout mechanism (login only) or
requires an authenticated bearer token, which already bounds abuse.

**Cookies vs. bearer tokens.** The default and primary mode returns the
refresh token in the JSON body — appropriate for a same-origin SPA or a
mobile client that stores it itself, and immune to CSRF by construction
(nothing about it is automatically attached by the browser). When
`Settings.AUTH_USE_REFRESH_COOKIE=true` (a deployment choice, not a
per-request one), the refresh token instead moves into an httpOnly,
Secure, SameSite cookie the browser *does* attach automatically — which
is exactly what makes it CSRF-exposed, so cookie mode also issues a
non-httpOnly CSRF cookie and requires the matching value echoed back in
an `X-CSRF-Token` header on every state-changing auth request (the
standard double-submit-cookie pattern: an attacker's cross-site form can
make the browser send the cookie, but can't read it to also set the
header).
"""
from __future__ import annotations

import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response, status

from app.api.deps import (
    get_auth_service,
    get_current_user,
    get_device_context,
    get_employee_service,
    get_invite_repository,
    get_permission_service,
    get_rate_limiter,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.rate_limit import RateLimiter
from app.core.responses import ErrorResponse
from app.models.identity import User
from app.repositories.interfaces import InviteRepository
from app.schemas.auth import (
    AcceptInviteRequest,
    ChangePasswordRequest,
    EmailVerificationConfirmRequest,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequestRequest,
    RefreshRequest,
    SessionResponse,
    SignupRequest,
    TokenPairResponse,
)
from app.services.auth_service import AuthResult, AuthService, DeviceContext
from app.services.employee_service import EmployeeService
from app.services.permission_service import PermissionService

router = APIRouter()

# Phase 6 Module 14 (Production Readiness) defect fix: explicitly typed
# to match FastAPI's own `responses` parameter signature
# (`dict[int | str, dict[str, Any]] | None`) -- without this annotation,
# mypy infers a narrower type from the literal dict body (keys as plain
# `int`, values as `dict[str, type[ErrorResponse] | str]`), which doesn't
# structurally match what `responses=` (used at every call site below)
# expects, and `mypy app` flagged every one of those call sites. This is
# a pre-existing gap from Module 2 (this file's original author never ran
# a full `mypy app` pass against it), not something introduced here.
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    422: {"model": ErrorResponse, "description": "Validation error"},
    429: {"model": ErrorResponse, "description": "Rate limited"},
}

CSRF_COOKIE_NAME = "nv_csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


def _set_auth_cookies(response: Response, result: AuthResult, settings: Settings) -> TokenPairResponse:
    """
    Cookie mode: set the refresh token (httpOnly) and a CSRF token
    (readable by JS, double-submit pattern) as cookies, and omit the raw
    refresh token from the JSON body so it never lands in
    `localStorage`/JS-readable state. Bearer mode (default): no cookies,
    refresh token goes in the body as normal.
    """
    if not settings.AUTH_USE_REFRESH_COOKIE:
        return TokenPairResponse(
            access_token=result.access_token, refresh_token=result.refresh_token, expires_in=result.expires_in
        )

    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=result.refresh_token,
        httponly=True,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )
    csrf_token = secrets.token_urlsafe(24)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,  # must be JS-readable so the client can echo it into the header
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )
    return TokenPairResponse(access_token=result.access_token, refresh_token="", expires_in=result.expires_in)


def _require_csrf_match(csrf_cookie: str | None, csrf_header: str | None) -> None:
    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise AuthenticationError("Missing or invalid CSRF token.")


def _resolve_refresh_token(body_token: str | None, cookie_token: str | None, settings: Settings) -> str:
    if settings.AUTH_USE_REFRESH_COOKIE:
        if not cookie_token:
            raise AuthenticationError("Missing refresh token cookie.")
        return cookie_token
    if not body_token:
        raise AuthenticationError("Missing refresh token.")
    return body_token


@router.post(
    "/signup",
    response_model=TokenPairResponse,
    responses={409: {"model": ErrorResponse, "description": "Email already registered"}, **_ERROR_RESPONSES},
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user identity",
    description=(
        "Creates only the authentication identity (no organization). "
        "A caller with no existing organization membership typically "
        "follows this with `POST /orgs` (Module 4) to create one and "
        "become its Owner."
    ),
)
async def signup(
    body: SignupRequest,
    response: Response,
    device: DeviceContext = Depends(get_device_context),
    auth_service: AuthService = Depends(get_auth_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> TokenPairResponse:
    await rate_limiter.check(
        f"signup:{device.ip_address or 'unknown'}",
        limit=settings.AUTH_SIGNUP_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    device_with_name = DeviceContext(
        device_name=body.device_name, user_agent=device.user_agent, ip_address=device.ip_address
    )
    result = await auth_service.signup(
        email=body.email, password=body.password, full_name=body.full_name, device=device_with_name
    )
    return _set_auth_cookies(response, result, settings)


@router.post(
    "/login",
    response_model=TokenPairResponse,
    responses=_ERROR_RESPONSES,
    summary="Log in with email + password",
    description=(
        "Returns a short-lived JWT access token and a long-lived opaque "
        "refresh token. Failed attempts count toward account lockout "
        "(configurable via AUTH_MAX_FAILED_LOGIN_ATTEMPTS)."
    ),
)
async def login(
    body: LoginRequest,
    response: Response,
    device: DeviceContext = Depends(get_device_context),
    auth_service: AuthService = Depends(get_auth_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> TokenPairResponse:
    await rate_limiter.check(
        f"login:{device.ip_address or 'unknown'}",
        limit=settings.AUTH_LOGIN_RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )
    device_with_name = DeviceContext(
        device_name=body.device_name, user_agent=device.user_agent, ip_address=device.ip_address
    )
    result = await auth_service.login(email=body.email, password=body.password, device=device_with_name)
    return _set_auth_cookies(response, result, settings)


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    responses=_ERROR_RESPONSES,
    summary="Rotate a refresh token for a new access/refresh pair",
    description=(
        "The presented refresh token is revoked and replaced. Presenting "
        "an already-rotated (reused) token revokes every token in its "
        "rotation family, per the replay-attack-prevention design."
    ),
)
async def refresh(
    body: RefreshRequest,
    response: Response,
    device: DeviceContext = Depends(get_device_context),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
    refresh_cookie: str | None = Cookie(default=None, alias="nv_refresh_token"),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER_NAME),
) -> TokenPairResponse:
    if settings.AUTH_USE_REFRESH_COOKIE:
        _require_csrf_match(csrf_cookie, csrf_header)
    raw_token = _resolve_refresh_token(body.refresh_token, refresh_cookie, settings)
    result = await auth_service.refresh(raw_refresh_token=raw_token, device=device)
    return _set_auth_cookies(response, result, settings)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Log out this device (revoke one refresh token)",
)
async def logout(
    body: LogoutRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
    refresh_cookie: str | None = Cookie(default=None, alias="nv_refresh_token"),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
    csrf_header: str | None = Header(default=None, alias=CSRF_HEADER_NAME),
) -> MessageResponse:
    if settings.AUTH_USE_REFRESH_COOKIE:
        _require_csrf_match(csrf_cookie, csrf_header)
    raw_token = _resolve_refresh_token(body.refresh_token, refresh_cookie, settings)
    await auth_service.logout(raw_refresh_token=raw_token)
    if settings.AUTH_USE_REFRESH_COOKIE:
        response.delete_cookie(settings.AUTH_REFRESH_COOKIE_NAME, path="/")
        response.delete_cookie(CSRF_COOKIE_NAME, path="/")
    return MessageResponse(message="Logged out.")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Log out every device (revoke all refresh tokens for the current user)",
)
async def logout_all(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth_service.logout_all(user_id=current_user.id)
    return MessageResponse(message="Logged out of all devices.")


@router.get(
    "/sessions",
    response_model=list[SessionResponse],
    summary="List active sessions/devices for the current user",
)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[SessionResponse]:
    sessions = await auth_service.list_sessions(user_id=current_user.id)
    return [
        SessionResponse(
            id=s.id,
            device_name=s.device_name,
            ip_address=s.ip_address,
            issued_at=s.issued_at,
            last_used_at=s.last_used_at,
            expires_at=s.expires_at,
        )
        for s in sessions
    ]


@router.delete(
    "/sessions/{session_id}",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse, "description": "Session not found"}},
    summary="Revoke a specific session/device",
)
async def revoke_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth_service.revoke_session(user_id=current_user.id, session_id=session_id)
    return MessageResponse(message="Session revoked.")


@router.post(
    "/password/change",
    response_model=MessageResponse,
    responses=_ERROR_RESPONSES,
    summary="Change password (authenticated) — revokes all other sessions",
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth_service.change_password(
        user_id=current_user.id,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return MessageResponse(message="Password changed. All other sessions have been logged out.")


@router.post(
    "/password/reset/request",
    response_model=MessageResponse,
    responses={429: _ERROR_RESPONSES[429]},
    summary="Request a password reset email",
    description="Always returns success regardless of whether the email is registered, to prevent account enumeration.",
)
async def request_password_reset(
    body: PasswordResetRequestRequest,
    device: DeviceContext = Depends(get_device_context),
    auth_service: AuthService = Depends(get_auth_service),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> MessageResponse:
    await rate_limiter.check(
        f"password-reset:{device.ip_address or 'unknown'}",
        limit=settings.AUTH_PASSWORD_RESET_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    await auth_service.request_password_reset(email=body.email, ip_address=device.ip_address)
    return MessageResponse(message="If that email is registered, a reset link has been sent.")


@router.post(
    "/password/reset/confirm",
    response_model=MessageResponse,
    responses=_ERROR_RESPONSES,
    summary="Complete a password reset with the emailed token",
)
async def confirm_password_reset(
    body: PasswordResetConfirmRequest, auth_service: AuthService = Depends(get_auth_service)
) -> MessageResponse:
    await auth_service.confirm_password_reset(raw_token=body.token, new_password=body.new_password)
    return MessageResponse(message="Password has been reset. Please log in again.")


@router.post(
    "/verify-email/request",
    response_model=MessageResponse,
    summary="(Re)send the email verification link",
)
async def request_email_verification(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageResponse:
    await auth_service.request_email_verification(user_id=current_user.id)
    return MessageResponse(message="Verification email sent.")


@router.post(
    "/verify-email/confirm",
    response_model=MessageResponse,
    responses=_ERROR_RESPONSES,
    summary="Confirm an email verification token",
)
async def confirm_email_verification(
    body: EmailVerificationConfirmRequest, auth_service: AuthService = Depends(get_auth_service)
) -> MessageResponse:
    await auth_service.confirm_email_verification(raw_token=body.token)
    return MessageResponse(message="Email verified.")


@router.post(
    "/invite/accept",
    response_model=TokenPairResponse,
    responses=_ERROR_RESPONSES,
    status_code=status.HTTP_201_CREATED,
    summary="Accept an employee invite and set an initial password",
    description=(
        "Consumes an Invite (created via `POST /employees/invite`, Module 4) "
        "and provisions both the User's authentication identity and their "
        "Employee/RoleAssignment membership in the inviting organization, "
        "transactionally -- either both succeed or neither does."
    ),
)
async def accept_invite(
    body: AcceptInviteRequest,
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
    employee_service: EmployeeService = Depends(get_employee_service),
    invite_repo: InviteRepository = Depends(get_invite_repository),
    settings: Settings = Depends(get_settings),
) -> TokenPairResponse:
    device = get_device_context(request)
    request_id = getattr(request.state, "request_id", None)

    result = await auth_service.accept_invite(token=body.token, password=body.password, device=device)
    # Re-fetch the invite (now marked accepted by the call above) to learn
    # which org/role/branches it was for -- accept_invite's own contract
    # (Module 2) is "provision the User identity only," so this is Module
    # 4 completing the deferred half in the same request/DB transaction:
    # if provisioning fails here, `get_db_session`'s rollback-on-exception
    # (app/db/session.py) undoes the User creation too.
    invite = await invite_repo.get_by_token(body.token)
    if invite is not None:
        await employee_service.provision_from_invite(invite=invite, user=result.user, request_id=request_id)
    return _set_auth_cookies(response, result, settings)


@router.get(
    "/me",
    response_model=MeResponse,
    responses={401: _ERROR_RESPONSES[401]},
    summary="Current authenticated user, including resolved role and permissions",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    permission_service: PermissionService = Depends(get_permission_service),
) -> MeResponse:
    access = await permission_service.resolve_for_user(current_user.id)
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_email_verified=current_user.is_email_verified,
        org_id=access.org_id,
        role=access.role_code,
        permissions=access.permissions,
    )
