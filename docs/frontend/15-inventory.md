# 7I — Inventory Management

## Route Structure

```
app/(app)/inventory/page.tsx         inventory:read — 3-tab hub (Stock, Locations, Reports)
app/(app)/inventory/[id]/page.tsx    inventory:read — 2-tab detail (Movements, Reservations)
```

`/inventory` is a 3-tab hub: Stock (main inventory list), Locations (warehouse/shed/bin
hierarchy), Reports (6 sub-reports for inventory analytics). `/inventory/[id]` is a per-line
detail page with Movements and Reservations tabs.

## Architecture

```
lib/api/inventory.ts              Typed wrappers for Module 8 /inventory/* routes
lib/inventory/queries.ts          inventoryKeys factory + per-endpoint query hooks
lib/inventory/mutations.ts        Mutation hooks for CRUD + 8 per-line actions
lib/validation/inventory.ts       Zod schemas for all 10 inventory forms

components/inventory/
  inventory-list.tsx              Paginated table with debounced search + status filter
  inventory-header.tsx            Line identity + current status + action buttons
  inventory-summary-cards.tsx     KPI cards: total items, low stock count, reserved count

  create-inventory-dialog.tsx     New inventory line (product, branch, location, quantity)
  receive-stock-dialog.tsx        Record incoming stock
  transfer-stock-dialog.tsx       Move between locations
  reserve-stock-dialog.tsx        Reserve for order
  adjust-stock-dialog.tsx         Quantity adjustment with signed delta + reason
  mark-damaged-dialog.tsx         Mark items as damaged
  dispose-dialog.tsx              Dispose of items
  sell-dialog.tsx                 Record sale of items
  archive-dialog.tsx              Archive inventory line
  create-location-dialog.tsx      New location (warehouse/shed/bin hierarchy)

  locations-panel.tsx             Location hierarchy browser
  reports-panel.tsx               6 sub-reports: stock levels, movement history, valuation,
                                  aging, low-stock alerts, turnover
  movements-tab.tsx               Movement history for a line
  reservations-tab.tsx            Active + historical reservations for a line
```

## Components

`InventoryList` renders a `DataTable` with debounced search (product name, SKU) and status
filter. Each row shows product, quantity, location, status badge, and last-updated timestamp.
Summary cards above the table show total items, low-stock count, and reserved count.

The 10 dialog components each handle a specific inventory action. All follow the same pattern:
react-hook-form with a Zod schema, POST to the appropriate endpoint, invalidate relevant
queries on success, and close only on success (not on backdrop click or Escape).

`AdjustStockDialog` accepts a signed delta (positive or negative integer) with a reason
enum: `cycle_count`, `damage_discovered`, `data_correction`, `other`. The signed delta
pattern means "add 5" is `delta: 5` and "remove 3" is `delta: -3`, rather than separate
add/subtract forms.

`CreateLocationDialog` supports the warehouse -> shed -> bin hierarchy. Locations are nested:
a warehouse contains sheds, a shed contains bins. The dialog renders a cascading selector
(parent warehouse, then parent shed) based on the selected level.

`ReportsPanel` contains 6 sub-reports rendered as tabbed content:
1. Stock Levels (current quantities by location)
2. Movement History (all movements across lines)
3. Stock Valuation (total value by location/product)
4. Aging Analysis (days since last movement)
5. Low Stock Alerts (items below reorder point)
6. Turnover Rate (movement frequency metrics)

## API Endpoints

```
CRUD:
  GET    /inventory                              List inventory lines (paginated)
  POST   /inventory                              Create inventory line
  GET    /inventory/{id}                         Line detail
  PUT    /inventory/{id}                         Update line

Per-line actions (8):
  POST   /inventory/{id}/receive                 Receive stock (+ quantity)
  POST   /inventory/{id}/transfer                Transfer to different location
  POST   /inventory/{id}/reserve                 Reserve for order
  POST   /inventory/{id}/release                 Release reservation
  POST   /inventory/{id}/adjust                  Adjust quantity (signed delta)
  POST   /inventory/{id}/damage                  Mark as damaged
  POST   /inventory/{id}/dispose                 Dispose of items
  POST   /inventory/{id}/sell                    Record sale
  POST   /inventory/{id}/archive                 Archive line

Locations:
  GET    /inventory/locations                    List locations
  POST   /inventory/locations                    Create location
  GET    /inventory/locations/{id}               Location detail

Reports:
  GET    /inventory/reports/stock-levels         Current stock by location
  GET    /inventory/reports/movement-history     All movements
  GET    /inventory/reports/valuation            Stock valuation
  GET    /inventory/reports/aging                Aging analysis
  GET    /inventory/reports/low-stock            Low stock alerts
  GET    /inventory/reports/turnover             Turnover metrics
  GET    /inventory/reports/summary              Aggregated summary
```

## Query Keys & Mutations

```
inventoryKeys.all                           ['inventory'] (root)
inventoryKeys.list(filters?)                ['inventory', 'list', filters]
inventoryKeys.detail(id)                    ['inventory', 'detail', id]
inventoryKeys.summary                       ['inventory', 'summary']
inventoryKeys.units                         ['inventory', 'units']
inventoryKeys.locations(filters?)           ['inventory', 'locations', filters]
inventoryKeys.locationDetail(id)            ['inventory', 'location', id]
inventoryKeys.movements(id)                 ['inventory', 'movements', id]
inventoryKeys.reservations(id)              ['inventory', 'reservations', id]
inventoryKeys.report(type, params?)         ['inventory', 'report', type, params]
```

Stale times: `units` has 5-minute staleTime (reference data rarely changes). `list`, `detail`,
and `summary` use the default 15-second staleTime.

Shared helper: `invalidateLine(queryClient, id)` invalidates both `inventoryKeys.detail(id)`
and `inventoryKeys.list()` (prefix match) -- every per-line action calls this helper to keep
both the detail view and the list in sync.

All mutations toast success/error messages using the shared `toast` utility. No silent
failures -- every action provides user feedback.

## Validation

```
createInventorySchema       product_name, product_sku?, branch_id, location_id?,
                            quantity, unit_of_measure, reorder_point?, cost_price?
receiveStockSchema          quantity, supplier?, reference?, notes?
transferStockSchema         target_location_id, quantity, reason
reserveStockSchema          order_id?, quantity, notes?
adjustStockSchema           delta (signed integer, non-zero), reason (enum), notes?
markDamagedSchema           quantity, damage_reason, notes?
disposeSchema               quantity, disposal_reason, notes?
sellSchema                  quantity, sale_reference?, notes?
archiveSchema               reason
createLocationSchema        name, type (warehouse/shed/bin), parent_id?
```

All schemas use the `string + refine` pattern for fields that arrive as strings from form
inputs but need to be numbers (quantity, cost_price, reorder_point). `adjustStockSchema`
enforces `delta !== 0` via refine -- zero adjustments are rejected as meaningless.

## Permission Gates

```
inventory:read          Route-level gate on /inventory and /inventory/[id]
                        View stock, locations, reports, movements, reservations
inventory:write         Create lines, receive stock, transfer, reserve, release,
                        sell, create/edit locations
inventory:adjust        Adjust stock, mark damaged, dispose, archive, fulfill
```

`inventory:adjust` is a separate permission from `inventory:write` for destructive quantity
modifications. A Stock Manager can receive and transfer stock (`inventory:write`) but cannot
adjust quantities or dispose of items (`inventory:adjust`). This separation matches the
operational distinction between routine stock movements and inventory corrections.

## Patterns

- **Debounced search.** `InventoryList` uses a debounced search input (300ms) that refetches
  the list with a `search` query parameter. Same pattern as 7F's species search and 7G's
  plant list.
- **React state-during-render for auto-selection.** When creating a new inventory line, if the
  user selects a product with only one possible location, the location is auto-selected by
  setting state during render (before the return), not in a `useEffect`. This avoids the
  flash-of-empty-select pattern.
- **RecordEntryList reuse.** Movement and reservation histories reuse the generic
  `RecordEntryList<T>` component from 7G, maintaining consistent list presentation across
  the app.
- **Dialogs close only on success.** Every dialog validates the form, submits to the API, and
  only calls `onOpenChange(false)` in the success callback. Failed submissions keep the dialog
  open with error feedback. No backdrop-click or Escape-to-close on dirty forms.
- **API-first types.** All TypeScript interfaces are derived from the OpenAPI schema, not
  hand-written. The only exception is `inventoryKeys.units` where the backend response is a
  simple string list that doesn't need a generated type.

## Known Limitations

- No barcode/QR scanning. Inventory identification is by product name/SKU text search only.
  A real warehouse operation would benefit from barcode integration.
- Location hierarchy is 3 levels max (warehouse -> shed -> bin). Deeper nesting is not
  supported by the data model or the UI.
- Stock valuation uses `cost_price` from the inventory line, not a moving-average or FIFO
  calculation. This is a simplification; real inventory accounting would need more sophisticated
  costing methods.
- Reservation release (`POST /inventory/{id}/release`) exists in the API but the UI only
  surfaces reservation creation. A reservation management surface (list active reservations,
  release individual ones) would be a natural follow-up.
- Reports are rendered as tables in the browser. No CSV/PDF export is implemented.

## Test Coverage

- **Playwright** (`e2e/inventory.spec.ts`, 4 tests): create an inventory line and see it in the
  list; receive stock against a line and verify quantity increased; adjust stock with a negative
  delta and verify the adjustment appears in movements; create a location and use it in a new
  inventory line. All use real org creation via `POST /orgs`. Written and collected; **not
  execution-verified** in this sandbox.
- **Vitest/RTL** (`components/inventory/__tests__/`, 13 tests across 2 test files):
  - `inventory-list.test.tsx`: list rendering with search, status filter, summary cards,
    permission gating on action buttons, empty state, error state with retry
  - `inventory-detail.test.tsx`: movement history rendering, reservation list, adjust stock
    form with signed delta validation, receive stock form, transfer dialog with location
    cascading, mark damaged form, dialog-close-only-on-success behavior, location hierarchy
    rendering in locations panel
- **Full regression**: all prior suites plus the new 13 tests pass. `npx tsc --noEmit` clean.
  `npx eslint .` clean.
