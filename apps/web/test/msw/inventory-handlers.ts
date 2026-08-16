import { http, HttpResponse } from "msw";

import {
  makeInventoryItem,
  makeInventoryLocation,
  makeInventoryPage,
  makeInventorySummary,
  makeStockMovement,
  makeStockMovementPage,
  makeStockReservation,
  makeStockReservationPage,
  makeStockValuation,
  makeTransferReport,
  makeUnit,
  makeWasteReport,
} from "@/test/fixtures/inventory";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7I's Module 8 Inventory & Stock
 * Management routes. Listed before `shellHandlers` in test/msw/server.ts
 * on purpose -- same handler-shadowing risk documented there for
 * `GET /api/v1/plants` (7C's global-search fan-out already registers its
 * own empty `/inventory` stub, per that file's own comment flagging this
 * exact file as the fix once 7I existed).
 *
 * Route ordering mirrors the real backend's own requirement
 * (`inventory.py`'s module docstring): every static report path
 * (`/inventory/summary`, `/inventory/low-stock`, etc.) is registered
 * before the parameterized `/inventory/:id`, or a report request would
 * incorrectly match `:id` first.
 */
export const inventoryHandlers = [
  http.get(`${BASE}/api/v1/units`, () => HttpResponse.json([makeUnit()])),

  http.post(`${BASE}/api/v1/inventory-locations`, () => HttpResponse.json(makeInventoryLocation())),
  http.get(`${BASE}/api/v1/inventory-locations`, () => HttpResponse.json([makeInventoryLocation()])),
  http.get(`${BASE}/api/v1/inventory-locations/:id`, () => HttpResponse.json(makeInventoryLocation())),
  http.post(`${BASE}/api/v1/inventory-locations/:id/deactivate`, () => HttpResponse.json(makeInventoryLocation({ is_active: false }))),

  http.get(`${BASE}/api/v1/inventory/summary`, () => HttpResponse.json(makeInventorySummary())),
  http.get(`${BASE}/api/v1/inventory/low-stock`, () => HttpResponse.json([makeInventoryItem({ quantity: 5, low_stock_threshold: 20 })])),
  http.get(`${BASE}/api/v1/inventory/valuation`, () => HttpResponse.json(makeStockValuation())),
  http.get(`${BASE}/api/v1/inventory/waste-report`, () => HttpResponse.json(makeWasteReport())),
  http.get(`${BASE}/api/v1/inventory/transfer-report`, () => HttpResponse.json(makeTransferReport())),
  http.get(`${BASE}/api/v1/inventory/movements`, () => HttpResponse.json(makeStockMovementPage())),
  http.get(`${BASE}/api/v1/inventory/reservations`, () => HttpResponse.json(makeStockReservationPage())),

  http.get(`${BASE}/api/v1/inventory`, () => HttpResponse.json(makeInventoryPage())),
  http.post(`${BASE}/api/v1/inventory`, () => HttpResponse.json(makeInventoryItem())),
  http.get(`${BASE}/api/v1/inventory/:id`, () => HttpResponse.json(makeInventoryItem())),
  http.get(`${BASE}/api/v1/inventory/:id/movements`, () => HttpResponse.json(makeStockMovementPage())),
  http.get(`${BASE}/api/v1/inventory/:id/reservations`, () => HttpResponse.json([makeStockReservation()])),

  http.post(`${BASE}/api/v1/inventory/:id/receive`, () => HttpResponse.json(makeInventoryItem({ quantity: 150 }))),
  http.post(`${BASE}/api/v1/inventory/:id/transfer`, () => HttpResponse.json(makeInventoryItem())),
  http.post(`${BASE}/api/v1/inventory/:id/reserve`, () => HttpResponse.json(makeStockReservation())),
  http.post(`${BASE}/api/v1/inventory/:id/adjust`, () => HttpResponse.json(makeInventoryItem())),
  http.post(`${BASE}/api/v1/inventory/:id/damage`, () => HttpResponse.json(makeInventoryItem({ damaged_quantity: 5 }))),
  http.post(`${BASE}/api/v1/inventory/:id/dispose`, () => HttpResponse.json(makeInventoryItem({ disposed_quantity: 5 }))),
  http.post(`${BASE}/api/v1/inventory/:id/sell`, () => HttpResponse.json(makeInventoryItem({ quantity: 90 }))),
  http.post(`${BASE}/api/v1/inventory/:id/archive`, () => HttpResponse.json(makeInventoryItem({ archived_at: "2026-08-10T00:00:00Z" }))),

  http.post(`${BASE}/api/v1/stock-reservations/:id/release`, () => HttpResponse.json(makeStockReservation({ status: "released" }))),
  http.post(`${BASE}/api/v1/stock-reservations/:id/fulfill`, () => HttpResponse.json(makeStockReservation({ status: "fulfilled" }))),
];
