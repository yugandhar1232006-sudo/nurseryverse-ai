import type {
  AIDashboardResponse,
  BranchSummaryResponse,
  CustomerDashboardResponse,
  ExecutiveDashboardResponse,
  FinancialDashboardResponse,
  InventoryDashboardResponse,
  NurseryDashboardResponse,
  PlantDashboardResponse,
  SalesDashboardResponse,
} from "@/lib/api/reports";

/** Shared fixtures for 7D Dashboard tests -- mirrors test/fixtures/shell.ts's pattern. */

export function makeBranchSummary(overrides: Partial<BranchSummaryResponse> = {}): BranchSummaryResponse {
  return {
    branch_id: "44444444-4444-4444-4444-444444444444",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_name: "Main Branch",
    revenue_today: 320.5,
    revenue_mtd: 8420.75,
    at_risk_plant_count: 2,
    low_stock_count: 1,
    pending_disease_reports: 0,
    last_refreshed_at: "2026-08-14T08:00:00Z",
    ...overrides,
  };
}

export function makeExecutiveDashboard(overrides: Partial<ExecutiveDashboardResponse> = {}): ExecutiveDashboardResponse {
  return {
    revenue_today: 320.5,
    revenue_mtd: 8420.75,
    active_plant_count: 512,
    at_risk_plant_count: 3,
    open_disease_reports: 1,
    branches: [makeBranchSummary()],
    revenue_trend: [
      { day: "2026-08-12", revenue: 200, sale_count: 4 },
      { day: "2026-08-13", revenue: 310, sale_count: 6 },
    ],
    last_refreshed_at: "2026-08-14T08:00:00Z",
    ...overrides,
  };
}

export function makeNurseryDashboard(overrides: Partial<NurseryDashboardResponse> = {}): NurseryDashboardResponse {
  return {
    nursery_id: "22222222-2222-2222-2222-222222222222",
    total_plants: 600,
    active_plant_count: 512,
    branch_count: 2,
    employee_count: 8,
    low_stock_count: 3,
    pending_disease_reports: 1,
    last_refreshed_at: "2026-08-14T08:00:00Z",
    ...overrides,
  };
}

export function makePlantDashboard(overrides: Partial<PlantDashboardResponse> = {}): PlantDashboardResponse {
  return {
    by_status: { in_production: 300, ready_for_sale: 200, sold: 100 },
    // The backend's OpenAPI schema declares `by_species` items as a bare
    // `object` (no properties), so the generator emits `Record<string,
    // never>[]` -- an intentionally opaque free-form dict, same as
    // `AtRiskPlantResponse.result` below. `plant-tab.tsx` casts it the
    // same way when reading it. This is a backend schema looseness, not
    // a frontend typing bug.
    by_species: [
      { species: "Ficus lyrata", count: 40 },
      { species: "Monstera deliciosa", count: 25 },
    ] as unknown as PlantDashboardResponse["by_species"],
    ...overrides,
  };
}

export function makeInventoryDashboard(overrides: Partial<InventoryDashboardResponse> = {}): InventoryDashboardResponse {
  return {
    total_line_items: 42,
    total_units_on_hand: 3120,
    total_inventory_value: 18450.25,
    low_stock_count: 2,
    low_stock_items: [{ id: "line-1", name: "Potting soil 20L", quantity: 4, low_stock_threshold: 10 }],
    ...overrides,
  };
}

export function makeSalesDashboard(overrides: Partial<SalesDashboardResponse> = {}): SalesDashboardResponse {
  return {
    transaction_count: 24,
    total_sales: 2140.5,
    average_sale_value: 89.19,
    ...overrides,
  };
}

export function makeCustomerDashboard(overrides: Partial<CustomerDashboardResponse> = {}): CustomerDashboardResponse {
  return {
    total_customers: 58,
    repeat_customer_count: 19,
    repeat_customer_rate: 0.327,
    top_customers: [
      {
        customer_id: "cust-1",
        nursery_id: "22222222-2222-2222-2222-222222222222",
        branch_id: null,
        customer_name: "Alex Rivera",
        total_orders: 5,
        total_spent: 412.3,
        first_purchase_at: "2026-02-01T00:00:00Z",
        last_purchase_at: "2026-08-10T00:00:00Z",
      },
    ],
    ...overrides,
  };
}

export function makeAIDashboard(overrides: Partial<AIDashboardResponse> = {}): AIDashboardResponse {
  return {
    at_risk_plants: [
      {
        plant_id: "plant-1",
        common_label: "Ficus #A102",
        // `AtRiskPlantResponse.result` is a bare `object` in the OpenAPI
        // schema (opaque free-form dict) -- see `by_species` comment above.
        result: { risk: "root_rot" } as unknown as Record<string, never>,
        confidence: 0.82,
        created_at: "2026-08-13T00:00:00Z",
      },
    ],
    prediction_accuracy: {
      nursery_id: "22222222-2222-2222-2222-222222222222",
      prediction_type: "disease_detection",
      scored_prediction_count: 40,
      correct_prediction_count: 33,
      last_refreshed_at: "2026-08-14T08:00:00Z",
    },
    ...overrides,
  };
}

export function makeFinancialDashboard(overrides: Partial<FinancialDashboardResponse> = {}): FinancialDashboardResponse {
  return {
    revenue: 8420.75,
    estimated_cogs: 3200.0,
    estimated_gross_profit: 5220.75,
    estimated_gross_margin: 0.62,
    outstanding_invoice_count: 3,
    outstanding_invoice_total: 640.0,
    ...overrides,
  };
}
