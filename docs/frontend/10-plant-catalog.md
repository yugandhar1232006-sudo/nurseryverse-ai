# 7F — Plant Catalog

## Architecture

```
lib/api/catalog.ts              Typed wrappers for Module 5's /plant-categories, /species/*,
                                 /plant-varieties/* routes
lib/catalog/queries.ts          catalogKeys + usePlantCategoriesQuery/useSpeciesListQuery/
                                 useSpeciesDetailQuery/usePlantVarietiesQuery
lib/catalog/mutations.ts        6 mutation hooks: create/update/archive species, create/update/
                                 archive variety
lib/validation/catalog.ts       Zod schemas for the Species and Variety forms

components/catalog/
  species-panel.tsx             The main /plants/species screen: search + category filter +
                                 paginated table + create
  species-form-dialog.tsx       Create/edit species (identity + care attributes)
  species-detail-dialog.tsx     Read-only care attributes + this species' real varieties list,
                                 with its own create/edit/archive
  variety-form-dialog.tsx       Create/edit a variety, scoped to one species

app/(app)/plants/species/page.tsx   Rewritten from a ComingSoon placeholder (PermissionGate on
                                     species:read, unchanged from 7C)
```

`app/(app)/plants/page.tsx` (the `/plants` route itself, gated on `plants:read`) is intentionally
**not** touched this phase -- it's Module 6's individual plant-record list, which is 7G's scope, not
7F's. The 7C-era nav (`nav-config.ts`) already treats `/plants` and `/plants/species` as siblings
under one "Plants" section for exactly this reason.

## Two resources, one screen; a third with no UI at all

`PlantCategory` is real, system-seeded reference data (migration 0002) with exactly one backend
route (`GET /plant-categories`) and no create/update/delete anywhere in Module 5 -- confirmed
directly in `species.py`'s module docstring, not assumed. It appears here purely as a read-only
filter/dropdown source, never as something this screen lets an Owner manage. `Species` and
`PlantVariety` are real per-org CRUD resources; `PlantVariety` is a flat `/plant-varieties`
collection (not nested under `/species/{id}/`, matching Module 4's `/branches` precedent per that
route file's own docstring), so the UI presents it as a species-scoped sub-list inside
`SpeciesDetailDialog` rather than its own top-level screen -- there's no product reason for a nursery
manager to browse varieties independent of the species they belong to.

## Permission model (real, not invented)

Both `Species` and `PlantVariety` share the single `species:read`/`species:write`/`species:delete`
permission triad (confirmed in both route files) -- there is no separate `varieties:*` permission set
in the backend, so `VarietyFormDialog`/the archive action inside `SpeciesDetailDialog` gate on
`species:write`/`species:delete`, the same as the parent Species screen, not a permission that
doesn't exist.

## Data honesty

- `disease_susceptibility` is edited as a single comma-separated text field, not a tag-picker with a
  controlled vocabulary -- the backend has no such vocabulary (`list[str] | None`, free text), so a
  picker UI would misrepresent it as a closed set of options it isn't.
- `growth_curve_baseline` (a list of `{days_since_planting, expected_height_cm}` points) is shown as
  a real point count in the detail view ("N recorded points") but is not editable in this phase and is
  not rendered as a chart -- see Known Limitations below.
- `PlantCategoryResponse.name` is looked up by `category_id` for the list's category badge and the
  detail view doesn't re-derive or rename it -- it's the real taxonomy name, not a frontend label.

## A real defect found and fixed: MSW handler shadowing across phases

**The defect:** the two 7F Vitest tests that rely on the *default* `GET /api/v1/species` fixture
(rather than calling `server.use(...)` themselves) both failed with "No species yet" instead of the
seeded fixture data -- even when run in complete isolation.

**Root cause:** `test/msw/shell-handlers.ts` (written in 7C) already registers its own
`GET /api/v1/species` handler -- a deliberately empty page, used as the default target for the
global-search fan-out (`components/layout/global-search.tsx`) so individual search tests can
`server.use()` a real result set per case. MSW's `setupServer` resolves the **first** matching
handler in registration order (a per-test `server.use()` call still wins, since it prepends to the
front), and `shellHandlers` was listed before the new `catalogHandlers` in `test/msw/server.ts` --
so `catalogHandlers`' real species fixture was silently shadowed by the older, unrelated empty stub
for every test that didn't override the route itself.

**The fix:** reordered `test/msw/server.ts` to register `catalogHandlers` before `shellHandlers`.
Documented directly in that file's comment, including the forward-looking warning that
`shellHandlers`' `/plants`, `/customers`, and `/inventory` stubs will pose the exact same shadowing
risk once 7G/7I/7J add their own dedicated handler files, so those should register ahead of
`shellHandlers` too.

**Regression coverage:** both previously-failing tests now pass as part of the 7F suite that runs on
every future regression pass; the fix itself is at the shared `server.ts` level, so it also protects
every other current and future test file from the same class of shadowing.

## UI states

Loading (`Skeleton`), empty (`EmptyState`, distinguishing "no species yet" from "no species match
your filters"), error-with-retry (`ErrorState`), and permission-denied (`PermissionDenied` at the
route level, `PermissionGate` around individual write/delete actions) -- the same 7A/7D/7E primitives,
no bespoke implementations.

## Testing

- **Vitest/RTL** (`components/catalog/__tests__/species-catalog.test.tsx`, 7 tests, all passing):
  route-level `PermissionDenied` for a role without `species:read`; real species list rendering with
  category badges + debounced search re-fetching the backend with the typed term; species creation
  through the real form; opening a species' detail view, verifying real care attributes render, and
  adding a variety through it; archiving a species through the `AlertDialog` confirmation; the "no
  species yet" vs. real-error-with-retry empty/error states.
- **Full regression**: all 24 Vitest/RTL test files (149 tests: 142 from 7A-7E + 7 new) pass.
  `npx tsc --noEmit` clean. `npx eslint .` clean (0 errors; the same 1 pre-existing
  `react-hooks/incompatible-library` informational warning from 7E, unrelated to this phase).
  `npx next build` production build succeeds, including the real `/plants/species` route.
- **Playwright** (`e2e/plant-catalog.spec.ts`, 3 tests): written and reviewed against the real
  components/routes; collected successfully (`npx playwright test --list` resolves all 3); **not
  execution-verified** in this sandbox -- no Chromium binary and no Postgres/Docker, the same
  disclosed constraint as every other `e2e/*.spec.ts` file in this project. Every test signs up fresh
  and creates a real org first (via the same `POST /orgs` onboarding flow 7E's own suite exercises),
  since `species:write` requires organization membership and this sandbox has no seed fixture to
  provision one otherwise. Covers: adding a species with a real category selection and seeing it in
  the list; adding a variety from a species' real detail view; the auth-required redirect.

## Known limitations

- `growth_curve_baseline` has no editor UI in this phase -- the backend accepts a list of
  `{days_since_planting, expected_height_cm}` points on create/update, but building a real curve-point
  editor (add/remove/reorder rows, or a chart-based input) was judged lower priority than the
  identity/care-attribute fields every species needs, given the scope of the remaining 7G-7O modules.
  The detail view shows a real point count so the data isn't hidden, just not editable here yet.
- No image handling for Species/PlantVariety -- confirmed directly against
  `apps/api/app/schemas/catalog.py`: neither `SpeciesResponse` nor `PlantVarietyResponse` has an
  image/photo field at all. This is a genuine backend scope boundary, not a frontend gap -- plant
  *instance* photos (an individual plant record's actual photograph) are a Module 6/7G concern
  instead, tracked for that phase.
- `PlantCategory` has no per-org management UI anywhere in the app, by design -- see "Two resources,
  one screen" above.
