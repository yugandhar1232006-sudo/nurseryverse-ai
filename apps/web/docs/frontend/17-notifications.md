# 17. Notifications & Communication (7M)

## Scope

7M covers PG-58, the Notification Preferences panel on `/settings`'s "Notifications" tab -- the one real remaining end-user surface Module 11's notification system needed on the frontend. Everything else notification-related was already built in 7C (the notification center panel, unread badge, mark-read/mark-all-read, the live WebSocket hub) and is not touched here.

**Route-split reasoning, decided during research and not revisited:** `apps/api/app/api/routes/notifications.py` has 11 real routes. Four are 7C-owned (`GET /notifications`, `GET /notifications/unread-count`, `PATCH /notifications/{id}/read`, `POST /notifications/mark-all-read`) plus the WebSocket. Two are this phase's (`GET`/`PUT /notifications/preferences`). The remaining four -- `GET/POST /notifications/templates`, `POST /notifications/system-alerts`, `POST /notifications/retry-due` -- are template authoring, org-wide alert broadcast, and a delivery-retry sweep: all admin/operator actions, not end-user preference management, and were deliberately left for 7O Administration rather than folded in here.

## Data layer

- `lib/api/notifications.ts` (extended, additive) -- added `NotificationChannel`, `NotificationFrequency`, `NotificationPreferenceResponse`, `NotificationPreferenceUpdateRequest` types and `listPreferences()` / `updatePreferences()`. The latter's docstring documents a real doc-vs-code discrepancy: `docs/ux/09-page-inventory.md`'s PG-58 entry cites `PATCH /notifications/preferences`; the real route (`update_preferences` in `notifications.py`) is `PUT`, confirmed directly against the route file and `schema.d.ts`, not assumed from the doc.
- `lib/notifications/queries.ts` (extended) -- `notificationKeys.preferences()` + `usePreferencesQuery()`, gated on authenticated session, following every other hook in this file.
- `lib/notifications/mutations.ts` (extended) -- `useUpdatePreferencesMutation()`. Its docstring documents a second real finding from reading `PreferenceRepository.upsert` (`apps/api/app/repositories/sqlalchemy_repositories.py`) directly: the `PUT` route is a **per-(category, channel) upsert, not a bulk replace**. Sending a subset of rows leaves every omitted row untouched server-side -- it does **not** delete or reset them. Because of this, `NotificationPreferencesPanel` always sends one explicit row per visible grid cell on save, including unchecked ones (`enabled: false`), never an omission -- omitting an unchecked cell would silently fail to persist a user's "off" choice for a category/channel pair that already had a saved "on" row.
- `lib/validation/notifications.ts` -- `notificationPreferencesSchema`, Zod validation for the shared quiet-hours (`HH:MM`, matching `branch-form-dialog.tsx`'s existing `timePattern`) and frequency fields, with a `.refine()` pair requiring both a start and an end if either is set.

## Missing-row default behavior (verified, not guessed)

Read directly from `PreferenceService.resolve_channels` (`apps/api/app/notifications/preferences.py`): a (category, channel) pair with no saved row is **not** "off." The real dispatch fallback (`_DEFAULT_ENABLED`) is `in_app: true`, `email: true`, `sms: false`, `push: false`. `NotificationPreferencesPanel`'s grid mirrors this exactly as its initial (pre-save) state for any cell without a saved row, rather than defaulting everything to unchecked -- what a user sees on first visit matches what's actually happening today, not an arbitrary UI default.

## UI

`components/settings/notification-preferences-panel.tsx`, gated on `notifications:manage_preferences` via `PermissionGate` (a fallback card explains the denial rather than a raw empty screen). Two cards:

- **Channels by category**: a `Table` with one row per real `NotificationCategory` (22 values, human-readable labels) and one column per visible `NotificationChannel`. The SMS column is shown only when `useOrgSettingsQuery()`'s real `sms_enabled` field is true (PG-58's stated FR-17.3 plan-gating rule) -- this reuses the same query `OrgSettingsCard` already calls on the "Organization" tab, so switching to "Notifications" after visiting "Organization" doesn't add a second network round trip within the query's 5-minute `staleTime`.
- **Quiet hours & frequency**: one shared start/end time pair (native `<input type="time">`, matching `branch-form-dialog.tsx`'s operating-hours precedent), an IANA timezone text input, and a frequency `Select` (immediate/daily digest/weekly digest).

**Scope decision, disclosed in the component's own docstring and in the panel's description text, not hidden:** the real schema supports a distinct quiet-hours window and frequency per (category, channel) row, but a 22 x 4 grid of individual time pickers was judged unusable UX and outside what the UX research called for. This panel applies one shared quiet-hours window and frequency to every row it saves. The shared controls are pre-filled from the first saved row that has a non-null quiet-hours value, purely as a starting point; saving normalizes every row to that one shared value.

## Testing

**Vitest/RTL (written, executed, passing):** `components/settings/__tests__/notification-preferences-panel.test.tsx`, 3 tests -- permission-denied fallback without `notifications:manage_preferences`; real saved preference rows reflected in the grid with the SMS column hidden when the org has SMS off; the SMS column shown when SMS is on, unsaved cells reflecting the real backend default (in_app/email on, SMS/push off), and a real save that sends an explicit `enabled: false` row for a cell the user unchecked plus all 88 (22 x 4) visible cells, not a partial diff.

New fixtures/handlers: `test/fixtures/notifications.ts` (`makePreference`), two new handlers added to the existing `test/msw/shell-handlers.ts` (`GET`/`PUT /api/v1/notifications/preferences`) -- placed there rather than a new file, matching that file's existing home for every other `/notifications/*` route.

Full regression after 7M: **35 test files, 224 tests, all passing, zero regressions** against every carried-over 7A-7L test. Verified with `vitest run --no-file-parallelism --pool=forks`, batched into six groups of five-to-six files.

`npx tsc --noEmit`: 0 errors. `npx eslint` across every 7M file: 0 errors. `npx next build`: succeeds; `/settings` builds correctly with the new Notifications tab content.

**Playwright E2E (written, collected, not executed):** `e2e/notification-preferences.spec.ts`, 1 test -- signs up, creates an org, opens the Notifications tab, unchecks a real default-on cell (Low stock via Email), saves, reloads the page, and confirms the unchecked state survived the reload against the real backend. Collected via `npx playwright test --list` (1 test confirmed, parses cleanly). Execution remains blocked by the same disclosed sandbox constraint as every prior phase: no Chromium binary and no Postgres/Docker available in this environment.

## Known Limitations

- **Quiet hours and frequency are applied uniformly across the whole grid on save**, not per (category, channel) row, even though the real API supports per-row granularity -- a deliberate, disclosed UX scope decision (see above), not a technical limitation.
- **No template management, system-alert broadcast, or retry-sweep UI** -- those three real routes exist but are administrative, not end-user preference management, and are deferred to 7O.
- **The SMS gate is read-only from this panel's perspective** -- turning `sms_enabled` on/off for the org happens on the existing "Organization" tab (`OrgSettingsCard`, 7E), not here; this panel only reacts to that setting.

## Task status

Marks 7M (Notifications & Communication) complete: the PG-58 preference data layer, the category x channel matrix + quiet-hours/frequency panel wired into `/settings`, full test coverage (3 new Vitest/RTL tests + 1 new Playwright E2E spec written/collected), zero regressions across the full 35-file/224-test suite, and this architecture doc.
