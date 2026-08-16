# 11. Plant Lifecycle (7G)

## Scope

7G covers Module 6's individual plant records: registration, profile edits, status transitions, branch/zone moves, archival, images, movement history, and the full timeline -- plus the five immutable per-plant record types (Growth, Health, Watering, Fertilizer, Environmental) and Health & Disease (disease reports and their treatments).

`/plants` is the list screen; `/plants/[id]` is the Plant Profile, the first dynamic route in this app, with one tab per record type. `/plants/species` (7F) and `/plants` (7G) are deliberately separate screens for separate resources -- a `Species` describes a kind of plant in the abstract (care attributes, taxonomy); a `Plant` is one physical, branch-located, individually tracked specimen.

## Data layer

- `lib/api/plants.ts` -- registration/profile/status/move/archive/images/timeline wrappers for `/plants/*`.
- `lib/api/plant-records.ts` -- the five immutable record types' `list*`/`record*` functions. No `update*`/`delete*` anywhere: `plant_records.py`'s own module docstring says every record here is GET+POST only, so the UI never offers editing a past entry.
- `lib/api/disease-reports.ts` -- disease report create/confirm/dismiss and treatment list/apply.
- `lib/plants/queries.ts` / `lib/plants/mutations.ts` -- TanStack Query hooks over the above, following 7E/7F's `*Keys` factory + `use*Query`/`use*Mutation` pattern.
- `lib/validation/plants.ts` -- Zod schemas using the established `z.string()` + `.refine()` numeric-field pattern (see docs/frontend/09-organization-management.md's defect writeup for why `z.coerce.number()`/`.default()` break `zodResolver`).

## Permission model

`Plant` is branch-scoped, not just org-scoped: `plants:read`/`write`/`transfer` are "B" (branch-scoped) for Horticulturist/Sales Staff (Sales Staff has read only, no write/transfer) and "F" (org-wide) for Owner/Org Admin/Branch Manager, per `docs/ux/07-role-permission-matrix.md`. The backend enforces this on every route; the frontend adds no client-side branch filtering of its own -- `GET /plants` already returns only what the caller's role permits.

`growth:*`, `health:*`, `environmental:*`, `watering:*` are "F" for Owner/Org Admin, "B" for Branch Manager/Horticulturist, and denied entirely for Sales Staff. Each of the five record tabs on the Plant Profile is independently permission-gated (`PermissionGate` around the `TabsTrigger`/`TabsContent` pair), so a Sales Staff member sees a materially different set of tabs than a Horticulturist looking at the exact same plant -- not just disabled buttons, but tabs that don't exist for them at all.

Fertilizer routes are gated on `watering:read`/`watering:write`, not a separate `fertilizer:*` permission -- no such permission code was ever seeded server-side (`plant_records.py`'s docstring: fertilizing is folded under general watering care, mirroring `FertilizerLog`'s own docstring). The Fertilizer tab reuses the Watering permission for both its `TabsTrigger` gate and its "Record application" button.

Disease Reports/Treatments are genuinely Module 6 / Health & Disease scope, not 7L's AI Disease *Detection* -- `disease_reports.py`'s own route summaries say a report "also feeds Health Records' treatment history." `disease:approve` (confirm/dismiss a draft) is a narrower permission than `disease:write` (log a report, apply a treatment); the Health tab's `DiseaseReportCard` gates each action independently. Confirming an above-threshold report auto-transitions the plant to `Under Treatment` server-side -- the card doesn't try to reflect that itself; it just invalidates the plant detail query on success.

## Status transitions and moves are backend-enforced, not client-validated

`PlantStatus` (`in_production | ready_for_sale | under_treatment | sold | deceased`) has a real state machine defined server-side (`docs/ux/13-digital-twin-lifecycle.md`). `TransitionStatusDialog` offers every status as an option regardless of the plant's current one -- it does not attempt to pre-filter to "legal" next states. An illegal choice comes back as a real 409, surfaced via `toast.apiError` in the mutation's `onError`, and the dialog stays open so the user can pick differently. The same approach applies to `MovePlantDialog`: moving a plant to a different branch requires `plants:transfer` on *both* the source and destination branch (two separate backend authorization checks per `lib/api/plants.ts`'s docstring), and a 403 from either surfaces the same way.

## Registration form scope

`RegisterPlantRequest` also carries `supplier_id`/`purchase_price`/`purchase_date`/`planted_at`, deliberately not exposed in `RegisterPlantDialog`: no Supplier resource or UI exists anywhere in Phase 7 yet, and `planted_at` defaults server-side to "now," which is correct for the overwhelming majority of real registrations. This mirrors 7F's decision to leave `growth_curve_baseline` read-only.

## Two real defects found and fixed this phase

**1. `RecordEntryList<T extends {id: string}>` doesn't fit `PlantTimelineEntryResponse`.** The shared list scaffold built for the five record tabs (loading/empty/error/pagination in one place) assumes each item has a stable `id`. `PlantTimelineEntryResponse` is a projection over several source event tables, keyed by `source_id` + `event_type`, with no `id` field of its own. `TimelineTab` was written as a small, separate component instead of forcing a fake `id` onto the type -- keyed on `${event_type}-${source_id}`, which is unique per page in practice (the same source record can't produce two entries of the same `event_type`).

**2. Missing `GET /api/v1/species/:id` MSW handler, surfaced by the first real caller of a 7F hook.** `lib/catalog/queries.ts`'s `useSpeciesDetailQuery` was written in 7F but had no real consumer at the time -- `SpeciesDetailDialog` takes the species as a prop from the already-loaded list row rather than re-fetching it by id. So `test/msw/catalog-handlers.ts` never needed a detail-by-id handler, and the gap stayed invisible through all of 7F's own tests. 7G's `PlantHeader` only has a `species_id` (not the full species object), so it's the first component that actually calls `useSpeciesDetailQuery` -- and its test immediately hit a real "MSW Error: intercepted a request without a matching request handler" for `GET /api/v1/species/:id`. Fixed by adding the handler to `catalog-handlers.ts` (not `plants-handlers.ts` -- `/species/:id` is rightfully a catalog resource regardless of which phase's component calls it first), documented in that file with the full root-cause chain.

## MSW handler registration order

`test/msw/plants-handlers.ts` is registered in `test/msw/server.ts` *before* `shellHandlers`, for the same reason `catalogHandlers` is (see docs/frontend/10-plant-catalog.md): `shellHandlers` already owns a deliberately-empty `GET /api/v1/plants` stub for 7C's global-search fan-out, and MSW resolves the first matching handler in registration order. Without this ordering, every 7G test relying on the real plant-list fixture as its default would silently see the empty search stub instead. `/customers` and `/inventory` remain shadowed until 7I/7J add their own handler files -- `server.ts`'s own comment flags this for whoever builds those next.

## UI states

Every screen/tab: real loading skeletons, real empty states (distinguishing "no records yet" from "no matches" where filters apply), real error states with retry, and permission-gated actions/tabs. The five record tabs share `RecordEntryList`; Movement, Timeline, and Images are hand-rolled (unpaginated array, no-`id` projection, and a photo grid, respectively -- each a genuinely different shape than the others).

## Testing

**Vitest/RTL (written, executed, passing):** `components/plants/__tests__/plant-lifecycle.test.tsx`, 10 tests covering `PlantsPage` (permission-denied, list+search+status badges, registration form, empty state, error+retry) and `PlantDetailPage` (identity/species/status display + a real growth-measurement recording, disease-report confirmation, moving a plant, a 409 status-transition surfacing without silently closing the dialog, error+retry). All 10 pass against real MSW-mocked `apiClient` calls -- no fixtures return mock data shaped differently than the real backend's OpenAPI schema.

Full regression after 7G: 25 test files, 159 tests (149 carried over from 7A-7F, unmodified, plus these 10). **A real, disclosed sandbox limitation:** running the full suite with Vitest's default parallel worker pool is flaky in this specific sandbox (4 vCPU / 3.8 GB) -- two separate parallel runs produced different failure sets (`components/auth/__tests__/permission-gate.test.tsx` failed once with a React "Maximum update depth exceeded" error that does not reproduce in isolation; `lib/auth/__tests__/mutations.test.tsx` failed once with an unrelated unhandled-rejection error). Every one of the 25 files passes individually and passes when the whole suite is run serially (`vitest run --no-file-parallelism --pool=forks`), which is what's reported above. This is resource contention in this sandbox under parallel workers, not a logic defect in any tested code -- but it means CI running this suite on comparably constrained hardware should pin `--pool=forks` (or increase available cores) rather than trust an unqualified `vitest run`.

`npx tsc --noEmit`: 0 errors. `npx eslint .`: 0 errors, 3 informational warnings (2 pre-existing `react-hooks/incompatible-library` warnings on `form.watch()` calls -- one from 7E's `branch-form-dialog.tsx`, one new from `register-plant-dialog.tsx`'s species-then-variety cascading select, both the same accepted class from 7F's checkpoint). `npx next build`: succeeds; `/plants/[id]` correctly appears as a dynamic (ƒ) route.

**Playwright E2E (written, collected, not executed):** `e2e/plant-lifecycle.spec.ts`, 3 tests -- registering a plant and opening its real Plant Profile, recording a real growth measurement from the Growth tab, and the `/plants` route's auth-required redirect. Collected successfully via `npx playwright test --list`. Execution is blocked by the same sandbox constraint disclosed in every prior phase: no Chromium binary, no Postgres/Docker available here.

## Known Limitations

- Registration doesn't expose supplier/purchase-price/purchase-date/planted-at (see above) -- a real scope decision, not an oversight, given no Supplier resource exists anywhere in Phase 7 yet.
- Image "upload" registers an already-hosted URL (`UploadPlantImageRequest.url`/`thumbnail_url`/`caption`) -- there is no binary file-upload endpoint anywhere in Module 6's real API, so this is not a client-side file picker with a fake local preview.
- `PlantTimelineEntryResponse` and `movement-history` are both unpaginated-by-page-size-30-default/unpaginated-array reads respectively that this UI trusts the backend to keep reasonably sized; neither has a client-side cap.
- AI Disease *Detection* (running a model against an uploaded image to produce a prediction) is explicitly out of scope here -- that's 7L. This phase only supports manually logging a disease report and its treatments, though `DiseaseReportResponse.is_ai_sourced`/`ai_confidence` are displayed read-only when present, since a report can originate from an AI prediction recorded by a different (future) code path.
