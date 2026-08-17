# 7N -- Reports & Analytics

## Route Structure

Single route: `/reports` with a 2-tab layout (Reports, Scheduled). The Reports tab contains the
catalog grid and report history; the Scheduled tab lists and manages scheduled report definitions.

```
app/(app)/reports/page.tsx            PermissionGate(reports:read) -> ReportsContent
components/reports/
  reports-content.tsx                 Tabbed orchestrator: Reports tab + Scheduled tab
  report-history-panel.tsx            Left: catalog grid (card per report type).
                                      Right: history list for selected type.
  generate-report-dialog.tsx          Dialog to pick parameters and trigger generation.
  scheduled-reports-panel.tsx         List of scheduled reports with pause/resume/delete/run-now.
  scheduled-report-dialog.tsx         Create new scheduled report definition.
```

## Components

- **ReportsContent** -- top-level tab container. Manages which tab is active.
- **ReportHistoryPanel** -- the Reports tab body. Left column: a grid of catalog cards, each showing
  the report's name, description, and icon from the backend catalog response (not hardcoded labels).
  Right column: a list of previously generated reports for the selected catalog item, with status
  badges (pending, completed, failed) and download links.
- **GenerateReportDialog** -- opens when the user clicks "Generate" on a catalog card. Shows a
  narrowed filter set: `date_from` / `date_to` date pickers. Only 18 of the report types accept
  date filters; the others show no filter inputs. Submits a `POST /reports` which returns 202.
- **ScheduledReportsPanel** -- the Scheduled tab body. Lists scheduled report definitions with
  frequency, next-run time, status (active/paused). Actions: pause, resume, run now, delete.
- **ScheduledReportDialog** -- create a new scheduled report definition. Frequency selector
  (daily/weekly/monthly), time-of-day picker, report type picker from catalog. Datetime validation
  ensures the schedule's start date is in the future.

## API Endpoints

### Report Catalog & Generation

| Method | Path | Purpose |
|--------|------|---------|
| GET | /reports/catalog | List available report types (names, descriptions, parameters) |
| POST | /reports | Generate a report (returns 202 with report ID, async) |
| GET | /reports | List previously generated reports (history) |
| GET | /reports/{id} | Single report detail + status |
| GET | /reports/{id}/download | Download generated report file |

### Scheduled Reports

| Method | Path | Purpose |
|--------|------|---------|
| GET | /reports/scheduled | List all scheduled report definitions |
| POST | /reports/scheduled | Create a new schedule |
| PATCH | /reports/scheduled/{id} | Update a schedule |
| DELETE | /reports/scheduled/{id} | Delete a schedule |
| POST | /reports/scheduled/{id}/pause | Pause a schedule |
| POST | /reports/scheduled/{id}/resume | Resume a paused schedule |
| POST | /reports/scheduled/{id}/run-due | Trigger immediate run |

## Query Keys & Mutations

Query key factory (`reportKeys`):

- `reportKeys.catalog` -- the report type catalog. Stale time: 10 minutes (catalog changes rarely).
- `reportKeys.history` -- paginated list of generated reports. Polls every 4 seconds while any
  report has `status: pending`. Stops polling when all reports reach a terminal state.
- `reportKeys.detail(id)` -- single report status. Polls every 3 seconds while `status: pending`.
- `reportKeys.scheduled` -- list of scheduled report definitions.

Mutations (7 total):

- **generateReport** -- `POST /reports`. On success, invalidates `reportKeys.all` (entire namespace).
- **createSchedule** -- `POST /reports/scheduled`. Invalidates `reportKeys.all`.
- **updateSchedule** -- `PATCH /reports/scheduled/{id}`. Invalidates `reportKeys.all`.
- **deleteSchedule** -- `DELETE /reports/scheduled/{id}`. Invalidates `reportKeys.all`.
- **pauseSchedule** -- `POST /reports/scheduled/{id}/pause`. Invalidates `reportKeys.all`.
- **resumeSchedule** -- `POST /reports/scheduled/{id}/resume`. Invalidates `reportKeys.all`.
- **runScheduleNow** -- `POST /reports/scheduled/{id}/run-due`. Invalidates `reportKeys.all`.

All 7 mutations invalidate the entire `reportKeys.all` namespace. This is aggressive -- a change to
a scheduled report also refetches the history list, for example -- but safe. Report operations are
low-frequency (a user generates a report a handful of times per session, not dozens of times per
second), so the over-fetch cost is negligible and the consistency guarantee is worth it.

## Validation

`generateReportSchema` (Zod):

- `date_from` / `date_to`: optional `Date` fields, validated as a pair (if one is provided, both
  must be). `date_from` must be before `date_to`. Only presented in the UI for the 18 report types
  that accept date filters -- the catalog response drives which fields appear.

`scheduledReportSchema` (Zod):

- `frequency`: enum (`daily`, `weekly`, `monthly`)
- `time_of_day`: string in `HH:MM` format
- `start_date`: must be a future datetime. Validated with a `.refine()` that compares against
  `new Date()` at form-submission time, not at schema-definition time.
- `report_type`: string, must match a valid catalog ID.

## Permission Gates

- **Page-level** (`/reports`): `reports:read` -- controls whether the entire Reports page renders.
  Users without this permission never see the `/reports` route.
- **Generate / create / pause / resume / delete actions**: `reports:export` -- controls write
  operations on reports. The generate button, schedule creation, pause/resume toggles, and delete
  action are all individually gated on `reports:export`. A user with `reports:read` but not
  `reports:export` can view history and download completed reports but cannot generate new ones or
  manage schedules.

## Patterns

- **Async 202 polling workflow**: `POST /reports` returns 202 (accepted) with a report ID, not the
  report itself. The frontend polls `GET /reports/{id}` every 3 seconds until `status` reaches a
  terminal state (completed or failed). The 4-second history poll catches reports that complete
  between detail polls.
- **Catalog-driven labels**: report names, descriptions, and parameter schemas come from
  `GET /reports/catalog`, not hardcoded in the frontend. Adding a new report type on the backend
  automatically surfaces it in the UI without a frontend deploy.
- **Aggressive namespace invalidation**: all mutations invalidate `reportKeys.all`. See note above.
- **Narrowed filter set**: only `date_from` / `date_to` are exposed in the generate dialog. Other
  report-specific parameters (branch_id, category_id) are not yet in the UI despite being accepted
  by some backend endpoints. The catalog response indicates which parameters a report type accepts;
  the UI only renders fields the catalog advertises.

## Known Limitations

- **No inline date filter on history list**: the history panel shows all past reports for a catalog
  type with no date range filter. Users cannot narrow the history list by generation date.
- **No SSE / Webhook push for report completion**: the frontend polls for report status. There is
  no server-sent event or webhook to push a "report ready" notification. The 3-second poll is the
  only mechanism for detecting completion.
- **Missing `onError` on 2 mutations**: `pauseSchedule` and `resumeSchedule` do not have `onError`
  handlers wired up. A failed pause/resume will silently drop the error rather than showing a toast.
  The other 5 mutations have proper error handling.
- **No update dialog for scheduled reports**: the `ScheduledReportDialog` handles creation only.
  Editing an existing schedule is not yet supported in the UI -- the `PATCH /reports/scheduled/{id}`
  endpoint exists but no dialog calls it. Users must delete and recreate to change a schedule.

## Test Coverage

- **E2E** (2 tests):
  1. Generate + download: creates a report from the catalog, polls until completion, downloads the
     resulting file.
  2. Scheduled + pause: creates a scheduled report, pauses it, verifies the paused status, resumes.
     Written and reviewed against real components; not execution-verified in this sandbox (no
     Postgres/Docker).
- **Vitest/RTL** (7 tests): catalog grid rendering, generate report dialog with date filters,
  history list with status badges, polling behavior (status transitions), schedule CRUD operations,
  permission gating on generate button, empty states. All passing against MSW-mocked responses.
