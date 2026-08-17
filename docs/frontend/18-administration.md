# 7O -- Administration

## Route Structure

Single route: `/admin` with a 6-tab layout. Two tabs have further nested sub-tabs.

```
app/(app)/admin/page.tsx              PermissionGate(anyOf(["employees:read", "admin:read"]))
                                      -> AdministrationContent

components/admin/
  administration-content.tsx          6-tab orchestrator (Users, Roles & Permissions, Feature Flags,
                                      Audit & Security, Notifications, System)

  users-admin-panel.tsx               Paginated user table with action dropdown per row.
  change-role-dialog.tsx              Dialog to change a user's role.
  lock-account-dialog.tsx             Dialog to lock a user account with duration (1-10080 min).
  user-sessions-dialog.tsx            Lists active sessions for a user with revoke action.

  roles-permissions-panel.tsx         Read-only view of roles and their permission sets.
  feature-flags-panel.tsx             Toggle switches for per-org feature flags.

  audit-security-panel.tsx            4 inner tabs:
    audit-log-tab.tsx                 Searchable audit log with CSV export.
    security-policies-tab.tsx         Password/lockout policy configuration.
    ip-restrictions-tab.tsx           IP allowlist management.
    api-keys-tab.tsx                  API key management.

  notification-admin-panel.tsx        Notification template editor + broadcast sender.
  system-panel.tsx                    4 inner tabs:
    health-tab.tsx                    System health checks.
    configuration-tab.tsx             Runtime configuration viewer/editor.
    ai-admin-tab.tsx                  AI model management and usage stats.
    data-retention-tab.tsx            Data retention policy configuration.
```

## Components

- **AdministrationContent** -- top-level 6-tab container. Routes to the correct panel based on
  active tab.
- **UsersAdminPanel** -- paginated user table. Each row has an action dropdown (change role, lock
  account, view sessions). Three dialogs handle the write operations. Search and role-filter inputs
  above the table.
- **RolesPermissionsPanel** -- read-only display of all roles and their assigned permissions. No
  create/edit/delete for roles. Grid layout showing role name and its permission list.
- **FeatureFlagsPanel** -- per-org feature flag toggles. Each flag is a switch with a description.
  Toggling calls the update endpoint immediately (no confirmation dialog for non-dangerous flags).
- **AuditSecurityPanel** -- 4 inner tabs (Audit Log, Security Policies, IP Restrictions, API Keys).
  Audit log has search, date range filter, and CSV export via `href` download. Security policies
  shows password rules and lockout thresholds. IP restrictions manages an allowlist. API keys
  shows active keys with revoke action.
- **NotificationAdminPanel** -- notification template editor (edit message templates per category) +
  broadcast sender (send a notification to all users or a filtered subset).
- **SystemPanel** -- 4 inner tabs (Health, Configuration, AI Admin, Data Retention). Health shows
  service status checks. Configuration shows runtime settings. AI Admin shows model usage stats.
  Data Retention shows and configures retention policies per data type. System tab requires
  `admin:read` and is only accessible to platform admins, not normal tenant users.

## API Endpoints

31 endpoints total. Grouped by domain:

### Roles & Permissions (read-only)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /admin/roles | List all roles with their permissions |
| GET | /admin/permissions | List all available permissions |

### User Management (14 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /admin/users | Paginated user list with search/filter |
| GET | /admin/users/{id} | Single user detail |
| PATCH | /admin/users/{id}/role | Change user's role |
| POST | /admin/users/{id}/lock | Lock account with duration |
| POST | /admin/users/{id}/unlock | Unlock account |
| GET | /admin/users/{id}/sessions | List active sessions |
| DELETE | /admin/users/{id}/sessions/{sessionId} | Revoke a session |
| GET | /admin/users/{id}/effective-permissions | Effective permission set |
| POST | /admin/users/{id}/deactivate | Deactivate user |
| POST | /admin/users/{id}/reactivate | Reactivate user |
| PATCH | /admin/users/{id}/profile | Update profile fields |
| POST | /admin/users/invite | Send invitation email |
| GET | /admin/users/activity | User activity summary |
| GET | /admin/users/export | Export user list as CSV |

### Feature Flags (3 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /admin/feature-flags | List all feature flags and their states |
| PATCH | /admin/feature-flags/{key} | Toggle a single flag |
| GET | /admin/feature-flags/{key}/history | Flag change history |

### Audit & Security (4 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /admin/audit-log | Paginated audit log entries |
| GET | /admin/security/policies | Current security policies |
| PUT | /admin/security/policies | Update security policies |
| GET | /admin/audit-log/export | Export audit log as CSV |

### System (8 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /admin/system/health | Health check results |
| GET | /admin/system/configuration | Runtime configuration |
| PATCH | /admin/system/configuration | Update configuration |
| GET | /admin/system/ai/models | AI model list and usage |
| GET | /admin/system/ai/stats | AI usage statistics |
| GET | /admin/system/data-retention | Retention policies |
| PUT | /admin/system/data-retention | Update retention policies |
| POST | /admin/system/alerts | Create system alert |

### Notification Admin (3 endpoints)

| Method | Path | Purpose |
|--------|------|---------|
| GET | /admin/notifications/templates | List notification templates |
| PUT | /admin/notifications/templates/{id} | Update a template |
| POST | /admin/notifications/broadcast | Send broadcast notification |

## Query Keys & Mutations

Query key factory (`adminKeys`):

- `adminKeys.roles` -- role list. Stale time: 10 minutes (roles change rarely).
- `adminKeys.permissions` -- permission list. Stale time: 10 minutes.
- `adminKeys.users` -- paginated user list.
- `adminKeys.userDetail(id)` -- single user detail.
- `adminKeys.featureFlags` -- feature flag list.
- `adminKeys.auditLog` -- audit log entries.
- `adminKeys.securityPolicies` -- security policy config.
- `adminKeys.systemHealth` -- health check results.
- `adminKeys.systemConfiguration` -- runtime config.
- `adminKeys.aiModels` / `adminKeys.aiStats` -- AI admin data (both require `nursery_id`).
- `adminKeys.dataRetention` -- retention policies (requires `nursery_id`).

All `admin:read` queries use `retry: false` -- if the user lacks permission, the request 403s once
and does not retry, avoiding noisy repeated failures in the console.

Mutations (15 total):

- **changeUserRole** -- `PATCH /admin/users/{id}/role`. Invalidates user queries.
- **lockAccount** -- `POST /admin/users/{id}/lock`. Invalidates user queries.
- **unlockAccount** -- `POST /admin/users/{id}/unlock`. Invalidates user queries.
- **revokeSession** -- `DELETE /admin/users/{id}/sessions/{sessionId}`. Invalidates user detail.
- **deactivateUser** / **reactivateUser** -- invalidates user queries.
- **updateUserProfile** -- `PATCH /admin/users/{id}/profile`. Invalidates user queries.
- **inviteUser** -- `POST /admin/users/invite`. Invalidates user list.
- **toggleFeatureFlag** -- `PATCH /admin/feature-flags/{key}`. Invalidates featureFlags.
- **updateSecurityPolicies** -- `PUT /admin/security/policies`. Invalidates securityPolicies.
- **updateSystemConfiguration** -- `PATCH /admin/system/configuration`. Invalidates systemConfig.
- **updateDataRetention** -- `PUT /admin/system/data-retention`. Invalidates dataRetention.
- **createSystemAlert** -- `POST /admin/system/alerts`.
- **updateNotificationTemplate** -- `PUT /admin/notifications/templates/{id}`.
- **sendBroadcast** -- `POST /admin/notifications/broadcast`.

All user-state mutations share a `invalidateUser` helper that invalidates both `adminKeys.users` and
`adminKeys.userDetail(id)` in a single call, ensuring the list and detail views stay in sync.

## Validation

- **changeRoleSchema**: `role_code` string, must match a valid role from `GET /admin/roles`.
- **lockAccountSchema**: `duration_minutes` integer, range 1-10080 (1 minute to 7 days). The UI
  shows presets (1 hour, 24 hours, 7 days) with a manual override.
- **notificationTemplateSchema**: template body validation, category matching, channel-specific
  character limits.
- **systemAlertSchema**: alert title, message, severity level (info/warning/critical), optional
  expiry datetime.

## Permission Gates

Layered permission model -- three levels, each independent:

- **Page-level**: `anyOf(["employees:read", "admin:read"])` -- if the user has either permission,
  the `/admin` route renders. This allows Branch Managers (who have `employees:read` but not
  `admin:read`) to access the Users tab without seeing System or Audit tabs.
- **Panel-level**: within the 6 tabs, individual tabs are gated:
  - System tab: `admin:read` (platform_admin only)
  - Notifications tab: `notifications:manage_preferences`
  - Audit & Security tab: `admin:read`
  - Users tab: `employees:read`
  - Roles & Permissions tab: `admin:read`
  - Feature Flags tab: `admin:read`
- **Component-level**: individual actions within panels have their own gates:
  - User actions (change role, lock, unlock, deactivate): `employees:write`
  - Feature flag toggles: `feature_flags:manage`
  - Platform-level flags: `admin:manage`
  - Broadcast notifications: `notifications:manage_preferences`

## Patterns

- **Nested Tabs**: Audit & Security has 4 inner tabs (Audit Log, Security Policies, IP Restrictions,
  API Keys). System has 4 inner tabs (Health, Configuration, AI Admin, Data Retention). Both use
  Radix `Tabs` nested inside the outer tab's content panel.
- **`retry: false` on admin reads**: prevents console noise when a user lacks permission. The 403
  response is handled once (showing a permission-denied state) and not retried.
- **`nursery_id` required for AI and retention queries**: `adminKeys.aiModels`, `adminKeys.aiStats`,
  and `adminKeys.dataRetention` all require a `nursery_id` parameter. These queries are disabled
  when no nursery is selected.
- **Audit log CSV export as `href` download**: the export button is an `<a>` tag pointing to
  `GET /admin/audit-log/export` with filter query params. The browser handles the download natively
  -- no client-side blob construction or file-saver library.

## Known Limitations

- **No custom role builder**: roles are system-defined and cannot be created or modified in the UI.
  `RolesPermissionsPanel` is read-only. Custom role creation would require backend schema changes
  beyond this phase's scope.
- **System tab inaccessible to normal tenants**: `admin:read` is only granted to `platform_admin`.
  A nursery Owner or Org Admin cannot see System health, configuration, AI stats, or data retention
  policies. This is by design (system-level operations are a platform concern) but means tenant
  admins have no self-service visibility into their system's health.
- **No cross-org user picker**: the admin user list is scoped to the current organization. A
  platform admin cannot browse users across orgs from this UI -- they would need to switch org
  context via the shell's org selector first.

## Test Coverage

- **E2E** (2 tests):
  1. Owner views users, roles, and feature flags: navigates to /admin, verifies the Users tab
     loads with real user rows, switches to Roles tab (read-only view), switches to Feature Flags
     (toggle visible).
  2. Lock / unlock account: locks a user account with a duration, verifies the locked badge appears,
     then unlocks and verifies the badge clears.
     Written and reviewed against real components; not execution-verified in this sandbox (no
     Postgres/Docker).
- **Vitest/RTL** (11 tests): page permission gating (employee:read grants access, neither permission
  denies), user list rendering with action dropdown, role change dialog validation, lock duration
  range enforcement, feature flag toggle optimistic update, audit log search, notification template
  edit, system health loading, user deactivation/reactivation flow, session list with revoke,
  nested tab navigation. All passing against MSW-mocked responses.
