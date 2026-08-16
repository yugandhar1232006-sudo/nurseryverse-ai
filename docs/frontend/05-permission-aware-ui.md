# Permission-Aware UI — Phase 7A (Foundation)

## The rule

**Frontend permission checks are UX only.** The backend's AuthorizationService/PermissionService (`apps/api/app/services/{authorization_service,permission_service}.py`) is the actual security boundary and re-checks every request regardless of what the UI shows or hides. A `true` from any function in `lib/auth/permissions.ts` means "don't bother the user with a control the backend would reject" — it never means "this action is authorized." The backend call can still 403 (role changed in another tab, permission revoked mid-session) and that has to be handled on its own merits (see `03-api-integration-guide.md`'s 403 row), not treated as impossible because the UI thought it was allowed.

## Permission strings

`<module>:<action>` (e.g. `"plants:write"`), exactly as returned by `GET /api/v1/auth/me`'s `permissions: string[]` field, catalogued in `docs/ux/07-role-permission-matrix.md`.

## `lib/auth/permissions.ts` — pure functions

- `hasPermission(permissions, required)`
- `hasAnyPermission(permissions, required[])`
- `hasAllPermissions(permissions, required[])`
- `canAccessBranch(accessibleBranchIds, branchId)`
- `canAccessResource({ permissions, requiredPermission, userOrgId, resourceOrgId })`

All pure — no store dependency — so they're independently testable and reusable server-side (RSC) or client-side.

## `canAccessBranch` — a documented design decision, not an oversight

The backend has an internal branch-scoping concept (`ResolvedAccess.branch_ids`/`is_org_wide()` in `permission_service.py`), but it is **not exposed on `MeResponse`** — there is no `GET /auth/me` field or dedicated endpoint returning "the current user's accessible branch IDs" today. Rather than inventing a fake client-side approximation of that scope, `canAccessBranch` takes the accessible-branch-id list as an explicit argument:

```ts
canAccessBranch(accessibleBranchIds: readonly string[], branchId: string): boolean
```

mirroring the backend's own convention exactly: an **empty** list means org-wide (matches `is_org_wide()`'s `len(branch_ids) == 0`), a non-empty list means scoped to exactly those IDs. Callers source the list from wherever the backend already scoped it for them — typically the `GET /api/v1/branches` response, which the backend's own RLS/AuthorizationService has already filtered to what the current user can see, fetched via TanStack Query. If a screen ever needs a branch-access answer before that data has loaded, that's a genuine gap worth raising as a real backend defect (extending `MeResponse`) through the established defect process — explain it, get it approved, fix it, add a regression test — not something to fake with an invented client-side heuristic.

## `usePermissions()` — the ergonomic hook

`lib/auth/use-permissions.ts` binds the pure functions to `sessionStore`'s current user:

```tsx
const { can, canAny, canAll } = usePermissions();
if (can("plants:write")) { /* show the edit control */ }
```

Fails closed: with no authenticated user (`resolving` or `unauthenticated`), `permissions` is `[]` and every check returns `false`. There is deliberately no `usePermissions()` variant that defaults to "allow" while loading.

## What's built vs. what's next

7A ships the utilities and the hook. The actual consuming patterns — a `<Can>` wrapper component, route-level guards in `middleware.ts`, disabled-with-tooltip vs. hidden-entirely conventions for denied actions — land in 7B (route guards) and 7C (nav/shell, where the first real conditional rendering happens). This doc will grow those sections as they're built rather than speculating on them now.
