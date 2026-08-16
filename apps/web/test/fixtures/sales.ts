import type {
  InvoiceItemResponse,
  InvoiceResponse,
  OrderItemResponse,
  PageQuotationResponse,
  PageRefundResponse,
  PageReturnResponse,
  PageSalesOrderResponse,
  PageSaleResponse,
  PaymentResponse,
  QuotationItemResponse,
  QuotationResponse,
  RefundResponse,
  ReturnItemResponse,
  ReturnResponse,
  RevenueReportRow,
  SaleItemResponse,
  SaleResponse,
  SalesOrderResponse,
  SalesReportResponse,
} from "@/lib/api/sales";

/** Shared fixtures for 7J Sales/Quotation/Order/Invoice/Return/Refund tests -- mirrors test/fixtures/inventory.ts's pattern. */

const BRANCH_ID = "44444444-4444-4444-4444-444444444444";
const CUSTOMER_ID = "cust-11111111-1111-1111-1111-111111111101";

export function makeQuotation(overrides: Partial<QuotationResponse> = {}): QuotationResponse {
  return {
    id: "quote-01",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: BRANCH_ID,
    customer_id: CUSTOMER_ID,
    status: "draft",
    subtotal_amount: "100.00",
    discount_amount: "0.00",
    tax_amount: "8.00",
    total_amount: "108.00",
    valid_until: null,
    note: null,
    created_by_user_id: "11111111-1111-1111-1111-111111111111",
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeQuotationPage(items: QuotationResponse[] = [makeQuotation()]): PageQuotationResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeQuotationItem(overrides: Partial<QuotationItemResponse> = {}): QuotationItemResponse {
  return {
    id: "quote-item-01",
    quotation_id: makeQuotation().id,
    plant_id: null,
    inventory_id: "inv-01",
    description: "4in nursery pots",
    quantity: 10,
    unit_price: "10.00",
    discount_amount: "0.00",
    line_total: "100.00",
    ...overrides,
  };
}

export function makeSalesOrder(overrides: Partial<SalesOrderResponse> = {}): SalesOrderResponse {
  return {
    id: "order-01",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: BRANCH_ID,
    customer_id: CUSTOMER_ID,
    quotation_id: null,
    order_status: "draft",
    payment_status: "unpaid",
    subtotal_amount: "100.00",
    discount_amount: "0.00",
    tax_amount: "8.00",
    total_amount: "108.00",
    sale_id: null,
    invoice_id: null,
    created_by_user_id: "11111111-1111-1111-1111-111111111111",
    confirmed_at: null,
    fulfilled_at: null,
    cancelled_at: null,
    cancel_reason: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeSalesOrderPage(items: SalesOrderResponse[] = [makeSalesOrder()]): PageSalesOrderResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeOrderItem(overrides: Partial<OrderItemResponse> = {}): OrderItemResponse {
  return {
    id: "order-item-01",
    sales_order_id: makeSalesOrder().id,
    plant_id: null,
    inventory_id: "inv-01",
    quantity: 10,
    unit_price: "10.00",
    discount_amount: "0.00",
    tax_amount: "8.00",
    line_total: "108.00",
    reservation_id: null,
    ...overrides,
  };
}

export function makeSale(overrides: Partial<SaleResponse> = {}): SaleResponse {
  return {
    id: "sale-01",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: BRANCH_ID,
    customer_id: CUSTOMER_ID,
    status: "completed",
    subtotal_amount: "100.00",
    discount_amount: "0.00",
    tax_amount: "8.00",
    total_amount: "108.00",
    payment_method: "cash",
    sold_by_user_id: "11111111-1111-1111-1111-111111111111",
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeSalePage(items: SaleResponse[] = [makeSale()]): PageSaleResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeSaleItem(overrides: Partial<SaleItemResponse> = {}): SaleItemResponse {
  return {
    id: "sale-item-01",
    sale_id: makeSale().id,
    plant_id: null,
    inventory_id: "inv-01",
    quantity: 10,
    unit_price: "10.00",
    line_total: "100.00",
    ...overrides,
  };
}

export function makeInvoice(overrides: Partial<InvoiceResponse> = {}): InvoiceResponse {
  return {
    id: "invoice-01",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: BRANCH_ID,
    customer_id: CUSTOMER_ID,
    invoice_number: "INV-0001",
    status: "sent",
    subtotal_amount: "100.00",
    discount_amount: "0.00",
    tax_amount: "8.00",
    total_amount: "108.00",
    amount_paid: "0.00",
    payment_status: "unpaid",
    due_date: "2026-09-01",
    paid_at: null,
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeInvoiceItem(overrides: Partial<InvoiceItemResponse> = {}): InvoiceItemResponse {
  return {
    id: "invoice-item-01",
    invoice_id: makeInvoice().id,
    description: "4in nursery pots",
    quantity: 10,
    unit_price: "10.00",
    line_total: "100.00",
    ...overrides,
  };
}

export function makePayment(overrides: Partial<PaymentResponse> = {}): PaymentResponse {
  return {
    id: "payment-01",
    invoice_id: makeInvoice().id,
    amount: "50.00",
    method: "cash",
    reference: null,
    received_by_user_id: "11111111-1111-1111-1111-111111111111",
    received_at: "2026-08-05T00:00:00Z",
    ...overrides,
  };
}

export function makeReturn(overrides: Partial<ReturnResponse> = {}): ReturnResponse {
  return {
    id: "return-01",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: BRANCH_ID,
    sale_id: makeSale().id,
    customer_id: CUSTOMER_ID,
    status: "requested",
    reason: "Wrong item received",
    requested_by_user_id: "11111111-1111-1111-1111-111111111111",
    processed_by_user_id: null,
    processed_at: null,
    created_at: "2026-08-06T00:00:00Z",
    ...overrides,
  };
}

export function makeReturnPage(items: ReturnResponse[] = [makeReturn()]): PageReturnResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeReturnItem(overrides: Partial<ReturnItemResponse> = {}): ReturnItemResponse {
  return {
    id: "return-item-01",
    return_id: makeReturn().id,
    sale_item_id: makeSaleItem().id,
    quantity: 2,
    restock: true,
    condition: "resalable",
    line_refund_amount: "20.00",
    ...overrides,
  };
}

export function makeRefund(overrides: Partial<RefundResponse> = {}): RefundResponse {
  return {
    id: "refund-01",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: BRANCH_ID,
    return_id: makeReturn().id,
    invoice_id: null,
    sale_id: null,
    amount: "20.00",
    method: "cash",
    status: "completed",
    reference: null,
    processed_by_user_id: "11111111-1111-1111-1111-111111111111",
    processed_at: "2026-08-07T00:00:00Z",
    created_at: "2026-08-07T00:00:00Z",
    ...overrides,
  };
}

export function makeRefundPage(items: RefundResponse[] = [makeRefund()]): PageRefundResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeSalesReport(overrides: Partial<SalesReportResponse> = {}): SalesReportResponse {
  return { sale_count: 12, total_revenue: 1240.5, total_tax: 96.0, total_discount: 20.0, average_sale_value: 103.38, ...overrides };
}

export function makeRevenueReportRow(overrides: Partial<RevenueReportRow> = {}): RevenueReportRow {
  return { date: "2026-08-01", revenue: 108.0, ...overrides };
}
