import type {
  CustomerAddressResponse,
  CustomerAnalyticsResponse,
  CustomerCommunicationResponse,
  CustomerContactResponse,
  CustomerNoteResponse,
  CustomerReportRow,
  CustomerResponse,
  CustomerTagResponse,
  PageCustomerCommunicationResponse,
  PageCustomerNoteResponse,
  PageCustomerResponse,
} from "@/lib/api/customers";

/** Shared fixtures for 7J Customer/CRM tests -- mirrors test/fixtures/inventory.ts's pattern. */

export function makeCustomer(overrides: Partial<CustomerResponse> = {}): CustomerResponse {
  return {
    id: "cust-11111111-1111-1111-1111-111111111101",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: "44444444-4444-4444-4444-444444444444",
    name: "Jordan Rivera",
    email: "jordan@example.com",
    phone: "555-0100",
    customer_type: "retail",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeCustomerPage(items: CustomerResponse[] = [makeCustomer()]): PageCustomerResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeCustomerContact(overrides: Partial<CustomerContactResponse> = {}): CustomerContactResponse {
  return {
    id: "contact-01",
    customer_id: makeCustomer().id,
    name: "Sam Lee",
    role: "Procurement Manager",
    email: "sam@example.com",
    phone: "555-0101",
    is_primary: true,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeCustomerAddress(overrides: Partial<CustomerAddressResponse> = {}): CustomerAddressResponse {
  return {
    id: "address-01",
    customer_id: makeCustomer().id,
    address_type: "shipping",
    line1: "100 Greenway Ave",
    line2: null,
    city: "Portland",
    state: "OR",
    postal_code: "97201",
    country: "US",
    is_default: true,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

export function makeCustomerTag(overrides: Partial<CustomerTagResponse> = {}): CustomerTagResponse {
  return { id: "tag-01", customer_id: makeCustomer().id, tag: "vip", ...overrides };
}

export function makeCustomerNote(overrides: Partial<CustomerNoteResponse> = {}): CustomerNoteResponse {
  return {
    id: "note-01",
    customer_id: makeCustomer().id,
    author_user_id: "11111111-1111-1111-1111-111111111111",
    note: "Prefers delivery on Fridays.",
    pinned: false,
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeCustomerNotePage(items: CustomerNoteResponse[] = [makeCustomerNote()]): PageCustomerNoteResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeCustomerCommunication(overrides: Partial<CustomerCommunicationResponse> = {}): CustomerCommunicationResponse {
  return {
    id: "comm-01",
    customer_id: makeCustomer().id,
    channel: "email",
    direction: "outbound",
    subject: "Order confirmation",
    notes: "Sent order confirmation and delivery window.",
    logged_by_user_id: "11111111-1111-1111-1111-111111111111",
    occurred_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeCustomerCommunicationPage(
  items: CustomerCommunicationResponse[] = [makeCustomerCommunication()],
): PageCustomerCommunicationResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeCustomerAnalytics(overrides: Partial<CustomerAnalyticsResponse> = {}): CustomerAnalyticsResponse {
  return {
    customer_id: makeCustomer().id,
    total_orders: 4,
    total_spent: 620.5,
    average_order_value: 155.13,
    last_purchase_at: "2026-07-15T00:00:00Z",
    ...overrides,
  };
}

export function makeCustomerReportRow(overrides: Partial<CustomerReportRow> = {}): CustomerReportRow {
  return {
    customer_id: makeCustomer().id,
    name: "Jordan Rivera",
    total_orders: 4,
    total_spent: 620.5,
    average_order_value: 155.13,
    last_purchase_at: "2026-07-15T00:00:00Z",
    ...overrides,
  };
}
