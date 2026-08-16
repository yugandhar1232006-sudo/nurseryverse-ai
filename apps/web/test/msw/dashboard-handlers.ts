import { http, HttpResponse } from "msw";

import {
  makeAIDashboard,
  makeCustomerDashboard,
  makeExecutiveDashboard,
  makeFinancialDashboard,
  makeInventoryDashboard,
  makeNurseryDashboard,
  makePlantDashboard,
  makeSalesDashboard,
} from "@/test/fixtures/dashboards";
import { makeBranchSummary } from "@/test/fixtures/dashboards";

const BASE = "http://localhost:8000";

/** Default, happy-path handlers for 7D's Module 12 dashboard/analytics routes -- same real-`apiClient` interception approach as shell-handlers.ts. */
export const dashboardHandlers = [
  http.get(`${BASE}/api/v1/dashboards/executive`, () => HttpResponse.json(makeExecutiveDashboard())),
  http.get(`${BASE}/api/v1/dashboards/nursery`, () => HttpResponse.json(makeNurseryDashboard())),
  http.get(`${BASE}/api/v1/dashboards/branch/:branchId`, () => HttpResponse.json(makeBranchSummary())),
  http.get(`${BASE}/api/v1/dashboards/plant`, () => HttpResponse.json(makePlantDashboard())),
  http.get(`${BASE}/api/v1/dashboards/inventory`, () => HttpResponse.json(makeInventoryDashboard())),
  http.get(`${BASE}/api/v1/dashboards/sales`, () => HttpResponse.json(makeSalesDashboard())),
  http.get(`${BASE}/api/v1/dashboards/customer`, () => HttpResponse.json(makeCustomerDashboard())),
  http.get(`${BASE}/api/v1/dashboards/ai`, () => HttpResponse.json(makeAIDashboard())),
  http.get(`${BASE}/api/v1/dashboards/financial`, () => HttpResponse.json(makeFinancialDashboard())),
  http.get(`${BASE}/api/v1/analytics/branch-performance`, () => HttpResponse.json([makeBranchSummary()])),
];
