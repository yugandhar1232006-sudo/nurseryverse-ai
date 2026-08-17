# 7H — Digital Twin

## Route Structure

No dedicated route. The Digital Twin lives as a nested tab within `/plants/[id]` (Module 7G's
plant detail page). The tab contains 4 sub-tabs:

```
/ plants / [id] # digital-twin
                 |-- Overview        Current twin snapshot
                 |-- Timeline        Paginated version history
                 |-- Versions        Version browser + comparison dialog
                 |-- Events          Raw domain event log
```

The parent route is `app/(app)/plants/[id]/page.tsx`, gated on `plants:read`. The Digital Twin
tab adds no additional permission gate beyond what the parent already enforces.

## Architecture

```
lib/api/digital-twin.ts          Typed wrappers for all GET /plants/{id}/digital-twin/* routes
lib/digital-twin/queries.ts      twinKeys factory + per-endpoint query hooks
lib/digital-twin/mutations.ts    Single mutation: useVerifyTwinConsistencyMutation

components/plants/digital-twin/
  twin-overview.tsx              Current snapshot display (identity, status, metrics)
  twin-timeline-panel.tsx        Paginated version list with diff highlights
  version-history-panel.tsx      Full version browser + CompareDialog (2-version diff)
  event-history-panel.tsx        Raw domain events table with type filter

components/plants/
  digital-twin-tab.tsx           Orchestrator: 4 Radix Tabs, one per sub-panel above
```

## Components

`twin-overview.tsx` renders the current twin snapshot as a card layout: identity fields,
current status, last-modified timestamp, and computed metrics. The snapshot is a point-in-time
projection, not live data -- it reflects the state at last event replay.

`twin-timeline-panel.tsx` shows a paginated list of twin versions. Each version entry displays
the version number, timestamp, triggering event type, and a summary of changed fields.
Pagination follows the same cursor-based pattern as other list views in the project.

`version-history-panel.tsx` provides a version browser (select a version to view its full
state) and a `CompareDialog` that diffs exactly 2 selected versions. The comparison is
structural: field-by-field diff with added/removed/changed highlighting. The 2-version limit is
a deliberate UX constraint -- more than 2 versions in a single diff view produces unreadable
results.

`event-history-panel.tsx` renders raw domain events (the source events that produced twin
versions). Each event row shows event type, timestamp, aggregate ID, and payload summary.
Filterable by event type. This is the lowest-level view of what happened, before projection
into versions.

## API Endpoints

All endpoints are **read-only GET** requests. No endpoint in this module accepts POST, PUT,
or DELETE.

```
GET    /plants/{id}/digital-twin                 Current twin snapshot
GET    /plants/{id}/digital-twin/timeline        Paginated version timeline
GET    /plants/{id}/digital-twin/versions        Full version list
GET    /plants/{id}/digital-twin/versions/compare?v1=X&v2=Y   Two-version diff
GET    /plants/{id}/digital-twin/snapshot         Snapshot at specific version
GET    /plants/{id}/digital-twin/events           Raw domain events
GET    /plants/{id}/digital-twin/verify           Consistency verification
```

`/verify` is a GET endpoint but is modeled as a mutation in the frontend because it triggers
a server-side consistency check (replaying events and comparing against the stored projection)
and returns a verification result. This is the only endpoint where the CQRS read-side
temporarily acts like a command.

## Query Keys & Mutations

```
twinKeys.all                         ['digital-twin'] (root)
twinKeys.detail(id)                  ['digital-twin', id]
twinKeys.timeline(id)                ['digital-twin', 'timeline', id]
twinKeys.versions(id)                ['digital-twin', 'versions', id]
twinKeys.compare(id, v1, v2)         ['digital-twin', 'compare', id, v1, v2]
twinKeys.snapshot(id, version?)      ['digital-twin', 'snapshot', id, version]
twinKeys.events(id)                  ['digital-twin', 'events', id]
```

`useCurrentTwinQuery` has a 15-second `staleTime` -- twin data changes only when underlying
plant events are recorded, which is infrequent. Version and comparison queries are **lazy**:
they don't fire until the user opens the Versions sub-tab or clicks "Compare." This avoids
fetching expensive diff data for users who only glance at the Overview.

Mutations: only `useVerifyTwinConsistencyMutation` (GET modeled as mutation, see API section
above). **No write mutations exist.** The twin is event-sourced -- it is never directly
written to. All changes flow through plant lifecycle events (growth records, status
transitions, etc.) which the backend event store captures and the twin projection replays.

## Validation

No validation schemas. There are no user-input forms in this module. All data is read from
the server and rendered. The only "input" is version numbers for comparison, which are
constrained by the server's own version list (the frontend only offers versions the server
says exist).

## Permission Gates

```
plants:read   Sufficient for all Digital Twin views
```

No additional permissions are required. The Digital Twin tab is visible whenever the parent
plant detail page is visible (`plants:read`). There is no separate `digital-twin:read`
permission -- the twin is a projection of the plant's own data, not a distinct resource.

## Patterns

- **CQRS read-side projection.** The Digital Twin is a read-optimized materialization of the
  plant's event stream. The frontend treats it as a pure read surface -- no mutation logic, no
  optimistic updates, no cache invalidation from writes. When plant events change (via 7G's
  record-mutation hooks), the twin queries go stale naturally and refetch on the next access.
- **Structural immutability.** Twin data is never modified client-side. No local state
  mutations, no "draft" mode. What the server returns is what the UI renders.
- **Snapshot type is hand-written.** The OpenAPI schema emits the snapshot as
  `Record<string, never>` (an opaque dict). The frontend defines its own `TwinSnapshot`
  interface based on the actual backend response shape, since the generated type carries no
  useful information. This is documented with a comment linking back to the OpenAPI limitation.
- **Compare limited to 2 versions.** `CompareDialog` accepts exactly 2 version IDs. The backend
  endpoint also accepts exactly 2. This is a deliberate constraint for readability, not a
  technical limitation.
- **No polling or subscriptions.** Twin data is fetched on demand (tab open, version browse).
  There is no real-time update mechanism -- the user sees the twin state as of their last
  navigation or manual refresh.

## Known Limitations

- The snapshot type is hand-written because the backend OpenAPI schema emits
  `Record<string, never>`. If the backend schema changes, the frontend type must be updated
  manually. This is tracked as a known divergence.
- No real-time updates. If a plant event is recorded while the user has the Digital Twin tab
  open, the data goes stale after the 15-second `staleTime` and only refreshes on the next
  query trigger (tab switch, re-navigation, or manual refresh).
- Event history shows raw events without semantic enrichment. A domain event like
  `growth_recorded` is shown with its payload, not a human-readable "Growth recorded: 12cm
  height" summary. Enriched event descriptions would require backend support.
- The `verify` endpoint re-replays the full event stream. On plants with very long histories,
  this could be slow. The frontend shows a loading state but has no timeout or progress
  indicator.

## Test Coverage

- **Playwright** (`e2e/digital-twin.spec.ts`, 3 tests): verify a fresh plant has an empty
  twin; record a growth measurement and confirm a new twin version appears; verify consistency
  endpoint returns a valid result. All run against real plant data with org creation via
  `POST /orgs`. Written and collected; **not execution-verified** in this sandbox.
- **Vitest/RTL** (`components/plants/digital-twin/__tests__/`, 7 tests across 1 test file):
  - `digital-twin.test.tsx`: overview rendering with mock snapshot, timeline pagination,
    version comparison dialog (2-version selection), event history with type filter, verify
    consistency mutation triggering, empty state for new plants, lazy query loading (versions
    tab not fetched until opened)
- **Full regression**: all prior suites plus the new 7 tests pass. `npx tsc --noEmit` clean.
  `npx eslint .` clean.
