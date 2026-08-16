"""
RBAC resolution — "permissions must come from the database, not
hardcoded" (Module 2's Authorization requirement, extended by Module 3's
Permission Engine requirements: resolver, cache, role resolver, effective
permissions, invalidation, multi-role-ready).

Reads a user's RoleAssignment(s), the assigned Role's granted Permissions
(via role_permissions), and the RoleAssignment's branch scope, entirely
from the tables Phase 5 already created. Nothing here hardcodes a role
name or a permission code to a business rule — the mapping lives only in
migration 0002's seeded `role_permissions` rows (mechanically parsed from
docs/ux/07-role-permission-matrix.md), so changing what a role can do is a
data change, not a code change.

Caching (Module 3): resolution is cached (Redis in production, in-memory
fallback — app/core/cache.py) keyed by user_id, with a short TTL as a
safety net plus explicit `invalidate_user()` for immediate invalidation
whenever a user's role/branch-scope actually changes (Module 4/5's
role-assignment endpoints must call this). Without explicit invalidation,
a revoked permission would otherwise remain effective for up to the cache
TTL -- explicit invalidation is what makes revocation actually immediate.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass

from app.core.cache import Cache
from app.repositories.interfaces import PermissionRepository

_CACHE_KEY_PREFIX = "perm:user:"
_DEFAULT_CACHE_TTL_SECONDS = 300  # 5 minutes -- a safety-net upper bound, not the primary invalidation path


@dataclass(frozen=True)
class ResolvedAccess:
    org_id: uuid.UUID | None
    role_id: uuid.UUID | None
    role_code: str | None
    branch_ids: list[uuid.UUID]
    permissions: list[str]

    def is_org_wide(self) -> bool:
        """
        Per RoleAssignmentBranchScope's own docstring (Phase 5): absent
        branch-scope rows for a role assignment mean "all branches", not
        "no branches" -- an org-wide role (Owner, Org Admin) simply never
        has branch_scopes rows at all. Centralized here so every caller
        (AuthorizationService, and eventually many route dependencies)
        applies the exact same interpretation of "empty branch_ids"
        instead of each re-deriving it.
        """
        return len(self.branch_ids) == 0

    def to_json(self) -> str:
        payload = asdict(self)
        payload["org_id"] = str(self.org_id) if self.org_id else None
        payload["role_id"] = str(self.role_id) if self.role_id else None
        payload["branch_ids"] = [str(b) for b in self.branch_ids]
        return json.dumps(payload)

    @classmethod
    def from_json(cls, raw: str) -> "ResolvedAccess":
        data = json.loads(raw)
        return cls(
            org_id=uuid.UUID(data["org_id"]) if data["org_id"] else None,
            role_id=uuid.UUID(data["role_id"]) if data["role_id"] else None,
            role_code=data["role_code"],
            branch_ids=[uuid.UUID(b) for b in data["branch_ids"]],
            permissions=list(data["permissions"]),
        )


class PermissionService:
    """
    The Permission Resolver + Role Resolver + Effective-Permissions
    computation, with an optional cache layer (Module 3). Constructing
    without a `cache` argument (Module 2's original usage) still works
    exactly as before -- every resolution just goes straight to the
    database, uncached. Passing a `Cache` (app/api/deps.py's
    `get_permission_service`, Module 3 onward) turns on caching
    transparently; callers never need to know which mode they're in.
    """

    def __init__(
        self,
        permission_repo: PermissionRepository,
        *,
        cache: Cache | None = None,
        cache_ttl_seconds: int = _DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._permission_repo = permission_repo
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def resolve_for_user(self, user_id: uuid.UUID) -> ResolvedAccess:
        cache_key = f"{_CACHE_KEY_PREFIX}{user_id}"
        if self._cache is not None:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return ResolvedAccess.from_json(cached)

        access = await self._resolve_from_database(user_id)

        if self._cache is not None:
            await self._cache.set(cache_key, access.to_json(), ttl_seconds=self._cache_ttl_seconds)

        return access

    async def resolve_all_for_user(self, user_id: uuid.UUID) -> list[ResolvedAccess]:
        """
        Multi-role support (future-ready, Module 3): resolves *every*
        RoleAssignment a user holds into a separate ResolvedAccess each,
        rather than just the first. v1's application-layer constraint
        (one Org per User -- RoleAssignment's docstring) means this
        returns 0 or 1 entries today; nothing about this method's shape
        needs to change if that constraint is ever lifted; only
        `list_role_assignments_for_user`'s underlying data would start
        returning more rows.
        """
        assignments = await self._permission_repo.list_role_assignments_for_user(user_id)
        results = []
        for assignment in assignments:
            results.append(await self._resolve_assignment(assignment))
        return results

    async def invalidate_user(self, user_id: uuid.UUID) -> None:
        """
        Must be called by any future code path that changes a user's role
        assignment, branch scope, or a role's permission set (Module 4's
        RBAC management endpoints, Module 5's employee role changes).
        Without this, a permission change only takes effect once the
        cache TTL naturally expires (up to 5 minutes) rather than
        immediately -- this is what makes revocation actually immediate.
        """
        if self._cache is not None:
            await self._cache.delete(f"{_CACHE_KEY_PREFIX}{user_id}")

    async def _resolve_from_database(self, user_id: uuid.UUID) -> ResolvedAccess:
        assignment = await self._permission_repo.get_role_assignment_for_user(user_id)
        if assignment is None:
            # A user with no RoleAssignment yet (e.g. mid-invite-acceptance,
            # before Module 5 wires up Employee+RoleAssignment creation)
            # simply has no org context and no permissions -- not an error.
            return ResolvedAccess(org_id=None, role_id=None, role_code=None, branch_ids=[], permissions=[])
        return await self._resolve_assignment(assignment)

    async def _resolve_assignment(self, assignment) -> ResolvedAccess:
        role = await self._permission_repo.get_role_with_permissions(assignment.role_id)
        permission_codes = sorted({p.code for p in role.permissions}) if role else []
        branch_ids = await self._permission_repo.get_branch_scope_ids(assignment.id)

        return ResolvedAccess(
            org_id=assignment.nursery_id,
            role_id=assignment.role_id,
            role_code=role.code if role else None,
            branch_ids=branch_ids,
            permissions=permission_codes,
        )
