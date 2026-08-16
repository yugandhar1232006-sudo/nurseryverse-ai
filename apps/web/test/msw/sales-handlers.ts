import { http, HttpResponse } from "msw";

import {
  makeInvoice,
  makeInvoiceItem,
  makeOrderItem,
  makePayment,
  makeQuotation,
  makeQuotationItem,
  makeQuotationPage,
  makeRefund,
  makeRefundPage,
  makeReturn,
  makeReturnItem,
  makeReturnPage,
  makeRevenueReportRow,
  makeSale,
  makeSaleItem,
  makeSalePage,
  makeSalesOrder,
  makeSalesOrderPage,
  makeSalesReport,
} from "@/test/fixtures/sales";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7J's Module 9 Sales routes
 * (`/quotations`, `/sales-orders`, `/sales`, `/invoices`, `/returns`,
 * `/refunds`). Route ordering mirrors `sales.py`'s real requirement:
 * `/sales/reports/summary` and `/sales/reports/revenue` must be listed
 * ahead of `/sales/:id`, or a report request would incorrectly match `:id`
 * first -- same rule 7I's `inventoryHandlers` follows for `/inventory/summary`.
 */
export const salesHandlers = [
  // Quotations
  http.get(`${BASE}/api/v1/quotations`, () => HttpResponse.json(makeQuotationPage())),
  http.post(`${BASE}/api/v1/quotations`, () => HttpResponse.json(makeQuotation())),
  http.get(`${BASE}/api/v1/quotations/:id`, () => HttpResponse.json(makeQuotation())),
  http.get(`${BASE}/api/v1/quotations/:id/items`, () => HttpResponse.json([makeQuotationItem()])),
  http.post(`${BASE}/api/v1/quotations/:id/status`, () => HttpResponse.json(makeQuotation({ status: "sent" }))),
  http.post(`${BASE}/api/v1/quotations/:id/convert`, () => HttpResponse.json(makeSalesOrder())),

  // Sales Orders
  http.get(`${BASE}/api/v1/sales-orders`, () => HttpResponse.json(makeSalesOrderPage())),
  http.post(`${BASE}/api/v1/sales-orders`, () => HttpResponse.json(makeSalesOrder())),
  http.get(`${BASE}/api/v1/sales-orders/:id`, () => HttpResponse.json(makeSalesOrder())),
  http.get(`${BASE}/api/v1/sales-orders/:id/items`, () => HttpResponse.json([makeOrderItem()])),
  http.post(`${BASE}/api/v1/sales-orders/:id/confirm`, () => HttpResponse.json(makeSalesOrder({ order_status: "confirmed" }))),
  http.post(`${BASE}/api/v1/sales-orders/:id/cancel`, () => HttpResponse.json(makeSalesOrder({ order_status: "cancelled" }))),
  http.post(`${BASE}/api/v1/sales-orders/:id/checkout`, () =>
    HttpResponse.json(makeSalesOrder({ order_status: "fulfilled", sale_id: makeSale().id, invoice_id: makeInvoice().id })),
  ),

  // Sales + Reports (static report routes registered before `/sales/:id`)
  http.get(`${BASE}/api/v1/sales/reports/summary`, () => HttpResponse.json(makeSalesReport())),
  http.get(`${BASE}/api/v1/sales/reports/revenue`, () => HttpResponse.json([makeRevenueReportRow()])),
  http.get(`${BASE}/api/v1/sales`, () => HttpResponse.json(makeSalePage())),
  http.get(`${BASE}/api/v1/sales/:id`, () => HttpResponse.json(makeSale())),
  http.get(`${BASE}/api/v1/sales/:id/items`, () => HttpResponse.json([makeSaleItem()])),
  http.post(`${BASE}/api/v1/sales/:sale_id/returns`, () => HttpResponse.json(makeReturn())),

  // Invoices + Payments
  http.get(`${BASE}/api/v1/invoices/:id`, () => HttpResponse.json(makeInvoice())),
  http.get(`${BASE}/api/v1/invoices/:id/items`, () => HttpResponse.json([makeInvoiceItem()])),
  http.post(`${BASE}/api/v1/invoices/:id/payments`, () => HttpResponse.json(makePayment())),
  http.get(`${BASE}/api/v1/invoices/:id/payments`, () => HttpResponse.json([makePayment()])),

  // Returns
  http.get(`${BASE}/api/v1/returns`, () => HttpResponse.json(makeReturnPage())),
  http.get(`${BASE}/api/v1/returns/:id`, () => HttpResponse.json(makeReturn())),
  http.get(`${BASE}/api/v1/returns/:id/items`, () => HttpResponse.json([makeReturnItem()])),
  http.post(`${BASE}/api/v1/returns/:id/approve`, () => HttpResponse.json(makeReturn({ status: "approved" }))),
  http.post(`${BASE}/api/v1/returns/:id/reject`, () => HttpResponse.json(makeReturn({ status: "rejected" }))),
  http.post(`${BASE}/api/v1/returns/:id/complete`, () => HttpResponse.json(makeReturn({ status: "completed" }))),

  // Refunds
  http.get(`${BASE}/api/v1/refunds`, () => HttpResponse.json(makeRefundPage())),
  http.post(`${BASE}/api/v1/refunds`, () => HttpResponse.json(makeRefund())),
  http.get(`${BASE}/api/v1/refunds/:id`, () => HttpResponse.json(makeRefund())),
];
