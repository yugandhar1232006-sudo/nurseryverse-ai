import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 9's Sales REST API (`/quotations/*`,
 * `/sales-orders/*`, `/sales/*`, `/invoices/*`, `/returns/*`,
 * `/refunds/*`). Customers/CRM live in `lib/api/customers.ts` instead --
 * `sales.py` and `customers.py` are two separate route files server-side
 * even though both belong to Module 9.
 *
 * Money fields (`unit_price`, `*_amount`, `amount`) are typed `string` in
 * every *Response* schema (Decimal serialized as a pre-rounded 2-place
 * string server-side -- `_money()` in `sales_service.py` unconditionally
 * quantizes with `ROUND_HALF_UP`) and `number | string` in every
 * *Request* schema (accepts either). The frontend never re-derives a
 * total from `tax_rate` client-side -- the rate itself isn't persisted
 * anywhere past `Quotation`/`SalesOrder` creation, only the resulting
 * dollar `tax_amount`, so all totals shown are exactly what the backend
 * computed and returned.
 *
 * Permission model (see `sales.py`'s route declarations): `sales:read`
 * gates quotation/order/sale/return GETs, `sales:write` gates the normal
 * create/status-change/confirm/cancel/checkout/approve/reject flows,
 * `sales:void` gates completing a return (the inventory-restocking,
 * irreversible step), `invoices:read`/`invoices:write` gate
 * invoice/payment/refund GETs and writes respectively.
 *
 * Two real 409 conflict classes to handle the same way 7I already does:
 * `invalid_status_transition` (quotation/order/return state machines) and
 * `insufficient_stock` (SalesOrder confirm/checkout calling into Module
 * 8's `InventoryService` for bulk-stock lines -- the exact same
 * discriminated-context `ConflictError` 7I's Adjust/Sell dialogs handle,
 * reused verbatim here, not reinvented).
 */

export type QuotationStatus = components["schemas"]["QuotationStatus"];
export type QuotationResponse = components["schemas"]["QuotationResponse"];
export type PageQuotationResponse = components["schemas"]["Page_QuotationResponse_"];
export type QuotationItemResponse = components["schemas"]["QuotationItemResponse"];
export type LineItemRequest = components["schemas"]["LineItemRequest"];
export type CreateQuotationRequest = components["schemas"]["CreateQuotationRequest"];
export type QuotationStatusChangeRequest = components["schemas"]["QuotationStatusChangeRequest"];

export type SalesOrderStatus = components["schemas"]["SalesOrderStatus"];
export type OrderPaymentStatus = components["schemas"]["OrderPaymentStatus"];
export type SalesOrderResponse = components["schemas"]["SalesOrderResponse"];
export type PageSalesOrderResponse = components["schemas"]["Page_SalesOrderResponse_"];
export type OrderItemResponse = components["schemas"]["OrderItemResponse"];
export type CreateSalesOrderRequest = components["schemas"]["CreateSalesOrderRequest"];
export type CancelOrderRequest = components["schemas"]["CancelOrderRequest"];

export type SaleStatus = components["schemas"]["SaleStatus"];
export type SaleResponse = components["schemas"]["SaleResponse"];
export type PageSaleResponse = components["schemas"]["Page_SaleResponse_"];
export type SaleItemResponse = components["schemas"]["SaleItemResponse"];

export type InvoiceStatus = components["schemas"]["InvoiceStatus"];
export type InvoiceResponse = components["schemas"]["InvoiceResponse"];
export type InvoiceItemResponse = components["schemas"]["InvoiceItemResponse"];

export type PaymentMethod = components["schemas"]["PaymentMethod"];
export type PaymentResponse = components["schemas"]["PaymentResponse"];
export type RecordPaymentRequest = components["schemas"]["RecordPaymentRequest"];

export type ReturnStatus = components["schemas"]["ReturnStatus"];
export type ReturnItemCondition = components["schemas"]["ReturnItemCondition"];
export type ReturnResponse = components["schemas"]["ReturnResponse"];
export type PageReturnResponse = components["schemas"]["Page_ReturnResponse_"];
export type ReturnItemResponse = components["schemas"]["ReturnItemResponse"];
export type ReturnItemRequest = components["schemas"]["ReturnItemRequest"];
export type CreateReturnRequest = components["schemas"]["CreateReturnRequest"];
export type RejectReturnRequest = components["schemas"]["RejectReturnRequest"];

export type RefundStatus = components["schemas"]["RefundStatus"];
export type RefundResponse = components["schemas"]["RefundResponse"];
export type PageRefundResponse = components["schemas"]["Page_RefundResponse_"];
export type ProcessRefundRequest = components["schemas"]["ProcessRefundRequest"];

export type SalesReportResponse = components["schemas"]["SalesReportResponse"];
export type RevenueReportRow = components["schemas"]["RevenueReportRow"];

// ------------------------------------------------------------------
// Quotations
// ------------------------------------------------------------------

export interface ListQuotationsParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
  customer_id?: string;
  status_filter?: QuotationStatus;
}

export async function listQuotations(params: ListQuotationsParams = {}): Promise<PageQuotationResponse> {
  return unwrap(() => apiClient.GET("/api/v1/quotations", { params: { query: params } }));
}

export async function createQuotation(body: CreateQuotationRequest): Promise<QuotationResponse> {
  return unwrap(() => apiClient.POST("/api/v1/quotations", { body }));
}

export async function getQuotation(id: string): Promise<QuotationResponse> {
  return unwrap(() => apiClient.GET("/api/v1/quotations/{id}", { params: { path: { id } } }));
}

export async function getQuotationItems(id: string): Promise<QuotationItemResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/quotations/{id}/items", { params: { path: { id } } }));
}

/** DRAFT->{SENT,REJECTED,EXPIRED}; SENT->{ACCEPTED,REJECTED,EXPIRED,DRAFT}; ACCEPTED/REJECTED/EXPIRED/CONVERTED terminal -- an invalid transition is a real 409. */
export async function changeQuotationStatus(id: string, body: QuotationStatusChangeRequest): Promise<QuotationResponse> {
  return unwrap(() => apiClient.POST("/api/v1/quotations/{id}/status", { params: { path: { id } }, body }));
}

/** Only an ACCEPTED quotation converts (409 otherwise) -- distinct from `changeQuotationStatus`, which cannot itself reach CONVERTED. */
export async function convertQuotation(id: string): Promise<SalesOrderResponse> {
  return unwrap(() => apiClient.POST("/api/v1/quotations/{id}/convert", { params: { path: { id } } }));
}

// ------------------------------------------------------------------
// Sales Orders
// ------------------------------------------------------------------

export interface ListSalesOrdersParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
  customer_id?: string;
  order_status?: SalesOrderStatus;
}

export async function listSalesOrders(params: ListSalesOrdersParams = {}): Promise<PageSalesOrderResponse> {
  return unwrap(() => apiClient.GET("/api/v1/sales-orders", { params: { query: params } }));
}

export async function createSalesOrder(body: CreateSalesOrderRequest): Promise<SalesOrderResponse> {
  return unwrap(() => apiClient.POST("/api/v1/sales-orders", { body }));
}

export async function getSalesOrder(id: string): Promise<SalesOrderResponse> {
  return unwrap(() => apiClient.GET("/api/v1/sales-orders/{id}", { params: { path: { id } } }));
}

export async function getSalesOrderItems(id: string): Promise<OrderItemResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/sales-orders/{id}/items", { params: { path: { id } } }));
}

/** DRAFT only (409 otherwise) -- reserves bulk-stock inventory per line via Module 8's real `InventoryService.reserve_stock()`; a real `insufficient_stock` 409 is possible here. */
export async function confirmSalesOrder(id: string): Promise<SalesOrderResponse> {
  return unwrap(() => apiClient.POST("/api/v1/sales-orders/{id}/confirm", { params: { path: { id } } }));
}

/** Rejected (409) if already FULFILLED/CANCELLED -- releases any taken reservations. */
export async function cancelSalesOrder(id: string, body: CancelOrderRequest): Promise<SalesOrderResponse> {
  return unwrap(() => apiClient.POST("/api/v1/sales-orders/{id}/cancel", { params: { path: { id } }, body }));
}

/**
 * Idempotent -- if `order.sale_id` is already set, the backend returns
 * the order unchanged rather than erroring, so a duplicate click is safe.
 * Valid from DRAFT/CONFIRMED/PROCESSING (409 otherwise). Fulfills/sells
 * every line (real `insufficient_stock` 409 possible for a bulk-stock
 * line with no reservation), generates a Passport synchronously for every
 * plant-tracked line, and generates exactly one Invoice.
 */
export async function checkoutSalesOrder(id: string): Promise<SalesOrderResponse> {
  return unwrap(() => apiClient.POST("/api/v1/sales-orders/{id}/checkout", { params: { path: { id } } }));
}

// ------------------------------------------------------------------
// Sales (completed transactions) + Reports
// ------------------------------------------------------------------

export interface ListSalesParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
  customer_id?: string;
}

export async function listSales(params: ListSalesParams = {}): Promise<PageSaleResponse> {
  return unwrap(() => apiClient.GET("/api/v1/sales", { params: { query: params } }));
}

export async function getSale(id: string): Promise<SaleResponse> {
  return unwrap(() => apiClient.GET("/api/v1/sales/{id}", { params: { path: { id } } }));
}

export async function getSaleItems(id: string): Promise<SaleItemResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/sales/{id}/items", { params: { path: { id } } }));
}

export interface SalesReportParams {
  branch_id?: string;
  date_from?: string;
  date_to?: string;
}

/** Registered ahead of `/sales/{id}` server-side -- excludes VOIDED sales. */
export async function getSalesReport(params: SalesReportParams = {}): Promise<SalesReportResponse> {
  return unwrap(() => apiClient.GET("/api/v1/sales/reports/summary", { params: { query: params } }));
}

/** Day-granularity revenue rows, registered ahead of `/sales/{id}` server-side -- excludes VOIDED sales. */
export async function getRevenueReport(params: SalesReportParams = {}): Promise<RevenueReportRow[]> {
  return unwrap(() => apiClient.GET("/api/v1/sales/reports/revenue", { params: { query: params } }));
}

// ------------------------------------------------------------------
// Invoices + Payments
// ------------------------------------------------------------------

export async function getInvoice(id: string): Promise<InvoiceResponse> {
  return unwrap(() => apiClient.GET("/api/v1/invoices/{id}", { params: { path: { id } } }));
}

export async function getInvoiceItems(id: string): Promise<InvoiceItemResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/invoices/{id}/items", { params: { path: { id } } }));
}

/** Amount must be > 0 (422 otherwise); rejected with a real 409 (`context.reason === "invoice_void"`) if the invoice is VOID. Supports multiple/partial payments. */
export async function recordPayment(invoiceId: string, body: RecordPaymentRequest): Promise<PaymentResponse> {
  return unwrap(() => apiClient.POST("/api/v1/invoices/{id}/payments", { params: { path: { id: invoiceId } }, body }));
}

export async function listInvoicePayments(invoiceId: string): Promise<PaymentResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/invoices/{id}/payments", { params: { path: { id: invoiceId } } }));
}

// ------------------------------------------------------------------
// Returns
// ------------------------------------------------------------------

export interface ListReturnsParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
  status_filter?: ReturnStatus;
}

export async function listReturns(params: ListReturnsParams = {}): Promise<PageReturnResponse> {
  return unwrap(() => apiClient.GET("/api/v1/returns", { params: { query: params } }));
}

export async function createReturn(saleId: string, body: CreateReturnRequest): Promise<ReturnResponse> {
  return unwrap(() => apiClient.POST("/api/v1/sales/{sale_id}/returns", { params: { path: { sale_id: saleId } }, body }));
}

export async function getReturn(id: string): Promise<ReturnResponse> {
  return unwrap(() => apiClient.GET("/api/v1/returns/{id}", { params: { path: { id } } }));
}

export async function getReturnItems(id: string): Promise<ReturnItemResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/returns/{id}/items", { params: { path: { id } } }));
}

/** REQUESTED only (409 otherwise). */
export async function approveReturn(id: string): Promise<ReturnResponse> {
  return unwrap(() => apiClient.POST("/api/v1/returns/{id}/approve", { params: { path: { id } } }));
}

/** REQUESTED only (409 otherwise). */
export async function rejectReturn(id: string, body: RejectReturnRequest): Promise<ReturnResponse> {
  return unwrap(() => apiClient.POST("/api/v1/returns/{id}/reject", { params: { path: { id } }, body }));
}

/** APPROVED only (409 otherwise) -- `sales:void`-gated, the inventory-restocking, irreversible step. */
export async function completeReturn(id: string): Promise<ReturnResponse> {
  return unwrap(() => apiClient.POST("/api/v1/returns/{id}/complete", { params: { path: { id } } }));
}

// ------------------------------------------------------------------
// Refunds
// ------------------------------------------------------------------

export interface ListRefundsParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
  status_filter?: RefundStatus;
}

export async function listRefunds(params: ListRefundsParams = {}): Promise<PageRefundResponse> {
  return unwrap(() => apiClient.GET("/api/v1/refunds", { params: { query: params } }));
}

/** Amount must be > 0 (422 otherwise). No real payment-gateway integration -- created PENDING then immediately flipped to COMPLETED synchronously, no webhook wait. */
export async function processRefund(body: ProcessRefundRequest): Promise<RefundResponse> {
  return unwrap(() => apiClient.POST("/api/v1/refunds", { body }));
}

export async function getRefund(id: string): Promise<RefundResponse> {
  return unwrap(() => apiClient.GET("/api/v1/refunds/{id}", { params: { path: { id } } }));
}
