# 7G — Plant Lifecycle

## Route Structure

```
app/(app)/plants/page.tsx              plants:read — paginated plant list
app/(app)/plants/[id]/page.tsx         plants:read — 12-tab plant detail
app/(app)/plants/species/page.tsx      species:read — species catalog (shipped in 7F)
```

`/plants` is the per-org plant list. `/plants/[id]` is the full detail surface with 12 tabs:
Overview, Growth, Health, Watering, Fertilizer, Environmental, Movement, Images, Timeline,
Digital Twin, Passport, AI Predictions. `/plants/species` is Module 7F's territory and is not
touched by this phase.

## Architecture

```
lib/api/plants.ts                 Typed wrappers for Module 6 /plants/* routes (CRUD + records)
lib/api/disease-reports.ts        Disease report + treatment endpoints
lib/plant/queries.ts              plantKeys factory + per-endpoint query hooks
lib/plant/mutations.ts            16 mutation hooks (CRUD, records, disease, archive, move)
lib/validation/plant.ts           Zod schemas for every 7G form

components/plants/
  plants-list.tsx                 Paginated table with status filter + debounced search
  plant-header.tsx                Plant identity + current status badge + action buttons
  register-plant-dialog.tsx       Create form: species, variety, branch, location, quantity
  transition-status-dialog.tsx    State-machine transition (server decides valid targets)
  move-plant-dialog.tsx           Branch/location transfer with reason
  archive-plant-dialog.tsx        Soft-delete with confirmation
  plant-status-badge.tsx          Color-coded lifecycle status indicator
  record-entry-list.tsx           Generic immutable-record list component (<T>)
  disease-report-card.tsx         Disease report with severity + treatment history
  overview-tab.tsx                Identity, status, location summary
  growth-tab.tsx                  Growth measurements via RecordEntryList<GrowthRecord>
  health-tab.tsx                  Health observations + disease reports
  watering-tab.tsx                Watering log via RecordEntryList<WateringRecord>
  fertilizer-tab.tsx              Fertilizer log (reuses watering permission model)
  environmental-tab.tsx           Environmental readings
  movement-tab.tsx                Movement/transfer history
  images-tab.tsx                  Plant photographs (URL-only, no upload)
  timeline-tab.tsx                Unified chronological event feed
  digital-twin-tab.tsx            Delegates to Module 7H components
  passport-tab.tsx                EU plant passport display + generation
  ai-predictions-tab.tsx          Per-plant AI predictions (delegates to 7L)
```

## Components

`PlantsList` renders a `DataTable` with `PlantStatusBadge` per row. `PlantHeader` shows identity
and current status, with action buttons for status transitions, move, and archive -- each gated
on its own permission.

`RegisterPlantDialog` uses react-hook-form with `registerPlantSchema`. Fields: name, species
(lookup from `/species`), variety (conditional on species), branch, planting_location, quantity,
planting_date. On submit POSTs to `/plants`.

`TransitionStatusDialog` fetches valid target states from the server (POST `/plants/{id}/status`
with the current status) rather than computing them client-side. The state machine is
server-side only -- the frontend never decides which transitions are legal.

`MovePlantDialog` accepts new branch_id + planting_location + reason. Cascades location
selection from branch, matching the pattern 7E established for branch-scoped selectors.

`RecordEntryList<T>` is a generic, reusable component for immutable record logs. Each record
type (growth, health, watering, fertilizer, environmental) gets its own tab but shares the same
list layout. Records cannot be edited or deleted after creation -- this is an immutability
constraint enforced both client-side (no edit/delete actions rendered) and server-side.

`DiseaseReportCard` displays a single disease report with severity badge, affected parts, and a
nested treatment history list. Treatments are append-only.

## API Endpoints

```
GET    /plants                              List plants (paginated, filterable)
POST   /plants                              Register new plant
GET    /plants/{id}                         Plant detail
POST   /plants/{id}                         Update plant
POST   /plants/{id}/status                  Transition lifecycle status
POST   /plants/{id}/move                    Move to different branch/location
POST   /plants/{id}/archive                 Soft-archive

GET    /plants/{id}/images                  List images (URL-only)
POST   /plants/{id}/images                  Add image reference

GET    /plants/{id}/timeline                Chronological event feed

POST   /plants/{id}/growth                 Record growth measurement
POST   /plants/{id}/health                 Record health observation
POST   /plants/{id}/watering               Record watering event
POST   /plants/{id}/fertilizer             Record fertilizer application
POST   /plants/{id}/environmental          Record environmental reading

GET    /plants/{id}/disease-reports        List disease reports
POST   /plants/{id}/disease-reports        Create disease report
POST   /plants/{id}/disease-reports/{rid}/treatments   Add treatment
POST   /plants/{id}/disease-reports/{rid}/approve      Approve report
```

## Query Keys & Mutations

`plantKeys` factory exposes a structured key hierarchy for targeted invalidation:

```
plantKeys.all           ['plants'] (root invalidation)
plantKeys.list(filters) ['plants', 'list', filters]
plantKeys.detail(id)    ['plants', 'detail', id]
plantKeys.images(id)    ['plants', 'images', id]
plantKeys.timeline(id)  ['plants', 'timeline', id]
plantKeys.movementHistory(id)  ['plants', 'movement', id]
plantKeys.growth(id)    ['plants', 'growth', id]
plantKeys.health(id)    ['plants', 'health', id]
plantKeys.watering(id)  ['plants', 'watering', id]
plantKeys.fertilizer(id) ['plants', 'fertilizer', id]
plantKeys.environmental(id) ['plants', 'environmental', id]
plantKeys.diseaseReports(id) ['plants', 'disease-reports', id]
plantKeys.treatments(id, reportId) ['plants', 'treatments', id, reportId]
```

16 mutations covering: `useCreatePlantMutation`, `useUpdatePlantMutation`,
`useTransitionStatusMutation`, `useMovePlantMutation`, `useArchivePlantMutation`,
`useAddImageMutation`, `useRecordGrowthMutation`, `useRecordHealthMutation`,
`useRecordWateringMutation`, `useRecordFertilizerMutation`,
`useRecordEnvironmentalMutation`, `useCreateDiseaseReportMutation`,
`useAddTreatmentMutation`, `useApproveDiseaseReportMutation` plus 2 others. All record
mutations invalidate the specific record-type key for that plant. Status transition also
invalidates `plantKeys.detail(id)` and `plantKeys.list()`.

## Validation

```
registerPlantSchema       name, species_id, variety_id?, branch_id, planting_location?,
                          quantity, planting_date?
movePlantSchema           branch_id, planting_location, reason
transitionStatusSchema    target_status, reason?
recordGrowthSchema        height_cm, stem_diameter_mm?, notes?
recordHealthSchema        health_status, symptoms?, affected_parts?, notes?
recordWateringSchema      amount_ml, method?, notes?
recordFertilizerSchema    fertilizer_type, amount, unit, notes?
recordEnvironmentalSchema temperature_c, humidity_pct?, light_level?, notes?
```

All record schemas share a common `notes` optional field. The backend validates the actual
state machine transitions and record constraints; the frontend schemas are a first-pass filter
for obvious errors (required fields, type coercion).

## Permission Gates

```
plants:read              Route-level gate on /plants and /plants/[id]
plants:write             Register, update, archive actions
plants:transfer          Move plant between branches
growth:read/write        Growth tab visibility + record form
health:read/write        Health tab visibility + record form
watering:read/write      Watering tab visibility + record form
environmental:read/write Environmental tab visibility + record form
fertilizer:read/write    Fertilizer tab -- reuses watering:* perms (see below)
disease:write            Create/approve disease reports
disease:read             View disease reports (implied by health:read in practice)
passport:read            Passport tab visibility
passport:generate        Generate passport action
ai_predictions:read      AI Predictions tab visibility (content delegated to 7L)
ai_predictions:run       Run prediction actions (delegated to 7L)
species:read             Species lookup in register form
```

Fertilizer reuses `watering:*` permissions because the backend has no separate
`fertilizer:*` permission set -- fertilizer applications are conceptually a subset of
plant-care records that share the same access model. The tab labels it clearly, but the
gating check is `watering:read`/`watering:write`.

## Patterns

- **All records are immutable.** Once a growth, health, watering, fertilizer, or environmental
  record is created, it cannot be edited or deleted. `RecordEntryList` renders no edit/delete
  actions. This is enforced server-side as well.
- **State machine is server-side only.** The frontend never computes valid transitions.
  `TransitionStatusDialog` asks the server "what are my options?" and renders whatever it gets
  back. This prevents client-server state drift.
- **Images are URL-only.** No file upload. Plant images are external URLs -- the frontend
  validates they look like URLs but does not handle binary upload, storage, or processing.
- **No sensor data.** Environmental records are manually entered. There is no IoT/sensor
  integration feeding automatic readings.
- **Fertilizer permissions share watering.** See Permission Gates above -- this is a backend
  design decision, not a frontend shortcut.

## Known Limitations

- `RecordEntryList` has no edit or delete -- this is intentional (immutability), but means
  typos in recorded data require a correcting entry, not an in-place fix.
- Image handling is URL-only. No upload, no thumbnail generation, no image optimization.
  A real photo-management feature would need backend upload support.
- The Digital Twin and AI Predictions tabs are thin delegates to Modules 7H and 7L
  respectively -- they add no plant-lifecycle-specific logic of their own.
- Plant passport generation depends on the backend's EU passport compliance module; if that
  module is not deployed, the tab shows a "not available" state rather than degrading silently.

## Test Coverage

- **Playwright** (`e2e/plant-lifecycle.spec.ts`, 3 tests): register a plant and see it in the
  list; record a growth measurement on a real plant detail page; auth-required redirect. All
  sign up fresh and create an org via `POST /orgs` for real permission provisioning.
  Written and collected; **not execution-verified** in this sandbox (no Chromium/Postgres).
- **Vitest/RTL** (`components/plants/__tests__/`, 15 tests across 3 test files):
  - `plants-list.test.tsx`: list rendering, status filter, debounced search, permission-denied
    state, empty state
  - `plant-detail.test.tsx`: tab navigation, status transition dialog, move dialog, archive
    confirmation, record entry list rendering
  - `plant-records.test.tsx`: growth/health/watering record forms, immutability (no edit/delete
    actions), disease report card rendering
- **Full regression**: all prior Vitest/RTL suites continue to pass alongside the new 15 tests.
  `npx tsc --noEmit` clean. `npx eslint .` clean.
