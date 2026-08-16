/**
 * Permission-aware UI utilities. These are UX-only conveniences for
 * hiding/disabling controls a user has no permission to use -- the real
 * security boundary is the backend's AuthorizationService/PermissionService
 * (apps/api/app/services/{authorization_service,permission_service}.py),
 * enforced again on every request regardless of what the UI shows. Never
 * treat a `true` from these functions as proof an action is allowed; it
 * only means "don't bother the user with a control the backend would
 * reject anyway." The backend call can still 403 (role changed in
 * another tab, permission revoked mid-session, etc.) and must be handled
 * on its own merits (see lib/api/error.ts's ApiError + the 403 UX
 * pattern documented in docs/frontend/06-permission-aware-ui.md once
 * written).
 *
 * Permission strings are `<module>:<action>` (e.g. "plants:write"),
 * exactly as returned by `GET /api/v1/auth/me`'s `permissions: string[]`
 * field and as catalogued in docs/ux/07-role-permission-matrix.md.
 */

export function hasPermission(permissions: readonly string[], required: string): boolean {
  return permissions.includes(required);
}

export function hasAnyPermission(permissions: readonly string[], required: readonly string[]): boolean {
  return required.some((perm) => permissions.includes(perm));
}

export function hasAllPermissions(permissions: readonly string[], required: readonly string[]): boolean {
  return required.every((perm) => permissions.includes(perm));
}

/**
 * Branch-scoping check, mirroring the backend's own
 * `ResolvedAccess.is_org_wide()` convention exactly (see
 * apps/api/app/services/permission_service.py): an empty
 * `accessibleBranchIds` list means org-wide access (every branch is
 * accessible), a non-empty list means the user's role is scoped to
 * exactly those branches.
 *
 * There is currently no field on `MeResponse` exposing this scope
 * directly -- by design, not oversight: `canAccessBranch` takes the
 * accessible-branch-id list as an explicit argument rather than reading
 * an implicit global, so callers source it from whatever the real
 * backend already scoped for them (e.g. the branch list returned by
 * `GET /api/v1/branches`, which the backend's own RLS/AuthorizationService
 * has already filtered to what this user can see -- see that route's
 * docs). If a screen needs a branch-access answer before that data has
 * loaded, that's a genuine gap worth raising as a backend defect
 * (extending `MeResponse`), not something to fake client-side.
 */
export function canAccessBranch(accessibleBranchIds: readonly string[], branchId: string): boolean {
  if (accessibleBranchIds.length === 0) return true; // org-wide
  return accessibleBranchIds.includes(branchId);
}

/**
 * Combines a permission check with an org-tenancy check for a specific
 * resource -- e.g. "can this user edit this specific plant record".
 * `resourceOrgId` should come from the resource itself (never assumed);
 * a mismatch here would mean the resource wasn't scoped to the current
 * org, which the backend's RLS policies prevent from happening in the
 * first place, but the UI shouldn't render an edit affordance for
 * cross-tenant data even transiently.
 */
export function canAccessResource(params: {
  permissions: readonly string[];
  requiredPermission: string;
  userOrgId: string | null;
  resourceOrgId: string | null;
}): boolean {
  const { permissions, requiredPermission, userOrgId, resourceOrgId } = params;
  if (!userOrgId || !resourceOrgId || userOrgId !== resourceOrgId) return false;
  return hasPermission(permissions, requiredPermission);
}
