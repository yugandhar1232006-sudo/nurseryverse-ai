import type {
  InventoryLocationResponse,
  InventoryResponse,
  InventorySummaryResponse,
  PageInventoryResponse,
  PageStockMovementResponse,
  PageStockReservationResponse,
  StockMovementResponse,
  StockReservationResponse,
  StockValuationResponse,
  TransferReportResponse,
  UnitResponse,
  WasteReportResponse,
} from "@/lib/api/inventory";

/** Shared fixtures for 7I Inventory tests -- mirrors test/fixtures/plants.ts's pattern. */

export function makeUnit(overrides: Partial<UnitResponse> = {}): UnitResponse {
  return {
    id: "unit-each-01",
    code: "each",
    name: "Each",
    unit_type: "count",
    ...overrides,
  };
}

export function makeInventoryLocation(overrides: Partial<InventoryLocationResponse> = {}): InventoryLocationResponse {
  return {
    id: "loc-11111111-1111-1111-1111-111111111101",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: "44444444-4444-4444-4444-444444444444",
    parent_location_id: null,
    location_type: "greenhouse",
    name: "Greenhouse 1",
    code: "GH1",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeInventoryItem(overrides: Partial<InventoryResponse> = {}): InventoryResponse {
  return {
    id: "inv-99999999-9999-9999-9999-999999999901",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: "44444444-4444-4444-4444-444444444444",
    species_id: null,
    category_id: "cat-houseplant-01",
    unit_id: "unit-each-01",
    location_id: "loc-11111111-1111-1111-1111-111111111101",
    name: "4in nursery pots",
    quantity: 100,
    reserved_quantity: 10,
    damaged_quantity: 2,
    disposed_quantity: 0,
    available_quantity: 88,
    unit_cost: 0.5,
    unit_price: 1.25,
    low_stock_threshold: 20,
    archived_at: null,
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeInventoryPage(items: InventoryResponse[] = [makeInventoryItem()]): PageInventoryResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeStockMovement(overrides: Partial<StockMovementResponse> = {}): StockMovementResponse {
  return {
    id: "mv-aaaaaaaa-1111-1111-1111-111111111101",
    inventory_id: makeInventoryItem().id,
    movement_type: "incoming",
    quantity_delta: 50,
    quantity_after: 100,
    reason: null,
    from_location_id: null,
    to_location_id: "loc-11111111-1111-1111-1111-111111111101",
    plant_id: null,
    reservation_id: null,
    transfer_group_id: null,
    reference_sale_id: null,
    reference_purchase_order_id: null,
    note: "Initial receipt",
    performed_by_user_id: "11111111-1111-1111-1111-111111111111",
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeStockMovementPage(items: StockMovementResponse[] = [makeStockMovement()]): PageStockMovementResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeStockReservation(overrides: Partial<StockReservationResponse> = {}): StockReservationResponse {
  return {
    id: "res-bbbbbbbb-2222-2222-2222-222222222201",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: "44444444-4444-4444-4444-444444444444",
    inventory_id: makeInventoryItem().id,
    quantity: 10,
    status: "active",
    reference_type: "sales_order",
    reference_id: null,
    reserved_by_user_id: "11111111-1111-1111-1111-111111111111",
    reserved_at: "2026-08-01T00:00:00Z",
    released_at: null,
    expires_at: null,
    note: null,
    ...overrides,
  };
}

export function makeStockReservationPage(items: StockReservationResponse[] = [makeStockReservation()]): PageStockReservationResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeInventorySummary(overrides: Partial<InventorySummaryResponse> = {}): InventorySummaryResponse {
  return {
    line_count: 5,
    total_quantity: 500,
    total_reserved_quantity: 20,
    total_damaged_quantity: 5,
    total_disposed_quantity: 0,
    total_available_quantity: 475,
    low_stock_count: 1,
    total_valuation: 250.0,
    ...overrides,
  };
}

export function makeStockValuation(overrides: Partial<StockValuationResponse> = {}): StockValuationResponse {
  return {
    line_count: 5,
    total_cost_value: 250.0,
    total_retail_value: 625.0,
    potential_margin: 375.0,
    ...overrides,
  };
}

export function makeWasteReport(overrides: Partial<WasteReportResponse> = {}): WasteReportResponse {
  return {
    movement_count: 0,
    total_quantity_disposed: 0,
    movements: [],
    ...overrides,
  };
}

export function makeTransferReport(overrides: Partial<TransferReportResponse> = {}): TransferReportResponse {
  return {
    movement_count: 0,
    movements: [],
    ...overrides,
  };
}
