"""
Module 3's authorization engine. `AuthorizationService.authorize(...)` is
the single choke point every permission/tenant/ownership check in the
system goes through -- app/api/deps.py's `require_permission`,
`require_org_match`, `require_branch_match`, and
`require_ownership_or_permission` dependencies are thin FastAPI wrappers
around this one method, so there is exactly one place that decides
"is this allowed", not N slightly-different copies scattered across
routes.

Design: `authorize()` never raises. It returns an `AuthorizationDecision`
-- an explicit, inspectable record of what was checked and why it passed
or failed (the module's "every authorization decision must be
explainable" requirement). The FastAPI dependency layer is what turns a
`allowed=False` decision into a raised `PermissionDeniedError` (or
`AuthenticationError` for the no-org-context case) and persists it to the
audit trail; keeping `authorize()` itself exception-free makes it trivial
to unit test every branch (see tests/unit/test_authorization_service.py)
without any HTTP/exception-handling machinery involved.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.db.enums import AuthorizationDenialReason
from app.models.authorization import AuthorizationDenial
from app.models.identity import User
from app.repositories.interfaces import AuthorizationDenialRepository
from app.services.permission_service import PermissionService, ResolvedAccess


@dataclass(frozen=True)
class RequestContext:
    """Per-request metadata needed for the audit trail. Analogous to Module 2's DeviceContext."""

    request_id: str | None
    ip_address: str | None


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    permission: str
    explanation: str
    reason: AuthorizationDenialReason | None = None
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    access: ResolvedAccess | None = None
    nursery_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None


class AuthorizationService:
    def __init__(
        self,
        *,
        permission_service: PermissionService,
        denial_repo: AuthorizationDenialRepository,
    ) -> None:
        self._permissions = permission_service
        self._denials = denial_repo

    async def authorize(
        self,
        *,
        user: User,
        permission: str,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        target_nursery_id: uuid.UUID | None = None,
        target_branch_id: uuid.UUID | None = None,
        resource_owner_user_id: uuid.UUID | None = None,
        context: RequestContext | None = None,
        persist_denial: bool = True,
    ) -> AuthorizationDecision:
        """
        Nursery -> Branch -> Resource, in that order, matching the
        module's required enforcement hierarchy: an org mismatch is
        checked (and denied) before a branch mismatch is even considered,
        since a branch that doesn't belong to the caller's org isn't a
        meaningful comparison to begin with. Ownership is checked last,
        as an *alternative* path to access when the permission the caller
        holds is scoped narrower than the action (e.g. a "read own
        records" style permission).
        """
        if not user.is_active:
            return await self._deny(
                user=user,
                permission=permission,
                reason=AuthorizationDenialReason.ACCOUNT_INACTIVE,
                explanation="The user account is not active.",
                resource_type=resource_type,
                resource_id=resource_id,
                nursery_id=target_nursery_id,
                branch_id=target_branch_id,
                context=context,
                persist=persist_denial,
            )

        access = await self._permissions.resolve_for_user(user.id)

        if target_nursery_id is not None:
            if access.org_id is None:
                return await self._deny(
                    user=user,
                    permission=permission,
                    reason=AuthorizationDenialReason.NO_ORG_CONTEXT,
                    explanation="The user has no organization membership to authorize against.",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    nursery_id=target_nursery_id,
                    branch_id=target_branch_id,
                    context=context,
                    access=access,
                    persist=persist_denial,
                )
            if access.org_id != target_nursery_id:
                return await self._deny(
                    user=user,
                    permission=permission,
                    reason=AuthorizationDenialReason.CROSS_TENANT_ORG,
                    explanation=(
                        f"User belongs to organization {access.org_id}, not the requested "
                        f"organization {target_nursery_id}."
                    ),
                    resource_type=resource_type,
                    resource_id=resource_id,
                    nursery_id=target_nursery_id,
                    branch_id=target_branch_id,
                    context=context,
                    access=access,
                    persist=persist_denial,
                )

        if target_branch_id is not None and not access.is_org_wide():
            if target_branch_id not in access.branch_ids:
                return await self._deny(
                    user=user,
                    permission=permission,
                    reason=AuthorizationDenialReason.CROSS_TENANT_BRANCH,
                    explanation=(
                        f"User's role is scoped to branches {[str(b) for b in access.branch_ids]}, "
                        f"which does not include the requested branch {target_branch_id}."
                    ),
                    resource_type=resource_type,
                    resource_id=resource_id,
                    nursery_id=target_nursery_id,
                    branch_id=target_branch_id,
                    context=context,
                    access=access,
                    persist=persist_denial,
                )

        has_permission = permission in access.permissions
        is_owner = resource_owner_user_id is not None and resource_owner_user_id == user.id

        if not has_permission and not is_owner:
            return await self._deny(
                user=user,
                permission=permission,
                reason=(
                    AuthorizationDenialReason.NOT_OWNER
                    if resource_owner_user_id is not None
                    else AuthorizationDenialReason.MISSING_PERMISSION
                ),
                explanation=(
                    f"User's role ('{access.role_code}') does not grant '{permission}', "
                    + (
                        "and the user does not own this resource."
                        if resource_owner_user_id is not None
                        else f"which is required for this action. Granted permissions: {access.permissions}."
                    )
                ),
                resource_type=resource_type,
                resource_id=resource_id,
                nursery_id=target_nursery_id,
                branch_id=target_branch_id,
                context=context,
                access=access,
                persist=persist_denial,
            )

        explanation = (
            f"Allowed via ownership (user {user.id} owns this {resource_type or 'resource'})."
            if is_owner and not has_permission
            else f"User's role ('{access.role_code}') grants '{permission}'."
        )
        return AuthorizationDecision(
            allowed=True,
            permission=permission,
            explanation=explanation,
            resource_type=resource_type,
            resource_id=resource_id,
            access=access,
            nursery_id=target_nursery_id,
            branch_id=target_branch_id,
        )

    async def _deny(
        self,
        *,
        user: User,
        permission: str,
        reason: AuthorizationDenialReason,
        explanation: str,
        resource_type: str | None,
        resource_id: uuid.UUID | None,
        nursery_id: uuid.UUID | None,
        branch_id: uuid.UUID | None,
        context: RequestContext | None,
        persist: bool,
        access: ResolvedAccess | None = None,
    ) -> AuthorizationDecision:
        if persist:
            await self._denials.log(
                AuthorizationDenial(
                    user_id=user.id,
                    permission_code=permission,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    nursery_id=nursery_id,
                    branch_id=branch_id,
                    reason=reason,
                    explanation=explanation[:500],
                    request_id=context.request_id if context else None,
                    ip_address=context.ip_address if context else None,
                )
            )
        return AuthorizationDecision(
            allowed=False,
            permission=permission,
            explanation=explanation,
            reason=reason,
            resource_type=resource_type,
            resource_id=resource_id,
            access=access,
            nursery_id=nursery_id,
            branch_id=branch_id,
        )
