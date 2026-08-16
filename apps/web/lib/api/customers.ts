import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 9's Customer/CRM REST API
 * (`/customers/*`). Sales/Quotations/Invoices/Returns/Refunds live in
 * `lib/api/sales.ts` instead -- `customers.py` and `sales.py` are two
 * separate route files server-side even though both belong to Module 9,
 * and this split mirrors that.
 *
 * Permission model (see `customers.py`'s route declarations):
 * `customers:read` gates every GET, `customers:write` gates create/update
 * and every sub-resource add (contacts/addresses/tags/notes/
 * communications). There is deliberately no delete/edit wrapper for
 * contacts, addresses, or notes below -- `customer_service.py` has
 * `delete_contact`/`delete_address`/`delete_note` methods, but no route
 * exposes them, so the UI can only add/list these, not remove or edit
 * individual entries (tags are the one exception: `DELETE
 * /customers/{id}/tags/{tag}` is a real route).
 */

export type CustomerType = components["schemas"]["CustomerType"];
export type CustomerResponse = components["schemas"]["CustomerResponse"];
export type PageCustomerResponse = components["schemas"]["Page_CustomerResponse_"];
export type CreateCustomerRequest = components["schemas"]["CreateCustomerRequest"];
export type UpdateCustomerRequest = components["schemas"]["UpdateCustomerRequest"];

export type CustomerAddressType = components["schemas"]["CustomerAddressType"];
export type CustomerContactResponse = components["schemas"]["CustomerContactResponse"];
export type CreateCustomerContactRequest = components["schemas"]["CreateCustomerContactRequest"];
export type CustomerAddressResponse = components["schemas"]["CustomerAddressResponse"];
export type CreateCustomerAddressRequest = components["schemas"]["CreateCustomerAddressRequest"];
export type CustomerTagResponse = components["schemas"]["CustomerTagResponse"];
export type AddCustomerTagRequest = components["schemas"]["AddCustomerTagRequest"];
export type CustomerNoteResponse = components["schemas"]["CustomerNoteResponse"];
export type PageCustomerNoteResponse = components["schemas"]["Page_CustomerNoteResponse_"];
export type CreateCustomerNoteRequest = components["schemas"]["CreateCustomerNoteRequest"];

export type CommunicationChannel = components["schemas"]["CommunicationChannel"];
export type CommunicationDirection = components["schemas"]["CommunicationDirection"];
export type CustomerCommunicationResponse = components["schemas"]["CustomerCommunicationResponse"];
export type PageCustomerCommunicationResponse = components["schemas"]["Page_CustomerCommunicationResponse_"];
export type LogCommunicationRequest = components["schemas"]["LogCommunicationRequest"];

export type CustomerAnalyticsResponse = components["schemas"]["CustomerAnalyticsResponse"];
export type CustomerReportRow = components["schemas"]["CustomerReportRow"];

// `SaleResponse` is a Sales concept, so the purchase-history page type is
// imported here structurally rather than re-declared -- see lib/api/sales.ts.
export type PageSaleResponse = components["schemas"]["Page_SaleResponse_"];

// ------------------------------------------------------------------
// Customers: CRUD + Search
// ------------------------------------------------------------------

export interface ListCustomersParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
  customer_type?: CustomerType;
  tag?: string;
  search?: string;
  sort_by?: string;
  sort_dir?: string;
}

export async function listCustomers(params: ListCustomersParams = {}): Promise<PageCustomerResponse> {
  return unwrap(() => apiClient.GET("/api/v1/customers", { params: { query: params } }));
}

export async function createCustomer(body: CreateCustomerRequest): Promise<CustomerResponse> {
  return unwrap(() => apiClient.POST("/api/v1/customers", { body }));
}

export async function getCustomer(id: string): Promise<CustomerResponse> {
  return unwrap(() => apiClient.GET("/api/v1/customers/{id}", { params: { path: { id } } }));
}

export async function updateCustomer(id: string, body: UpdateCustomerRequest): Promise<CustomerResponse> {
  return unwrap(() => apiClient.PATCH("/api/v1/customers/{id}", { params: { path: { id } }, body }));
}

export async function getCustomerPurchaseHistory(id: string, page = 1, pageSize = 20): Promise<PageSaleResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/customers/{id}/purchase-history", { params: { path: { id }, query: { page, page_size: pageSize } } }),
  );
}

export async function getCustomerAnalytics(id: string): Promise<CustomerAnalyticsResponse> {
  return unwrap(() => apiClient.GET("/api/v1/customers/{id}/analytics", { params: { path: { id } } }));
}

// ------------------------------------------------------------------
// Contacts / Addresses / Tags
// ------------------------------------------------------------------

export async function addCustomerContact(id: string, body: CreateCustomerContactRequest): Promise<CustomerContactResponse> {
  return unwrap(() => apiClient.POST("/api/v1/customers/{id}/contacts", { params: { path: { id } }, body }));
}

export async function listCustomerContacts(id: string): Promise<CustomerContactResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/customers/{id}/contacts", { params: { path: { id } } }));
}

export async function addCustomerAddress(id: string, body: CreateCustomerAddressRequest): Promise<CustomerAddressResponse> {
  return unwrap(() => apiClient.POST("/api/v1/customers/{id}/addresses", { params: { path: { id } }, body }));
}

export async function listCustomerAddresses(id: string): Promise<CustomerAddressResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/customers/{id}/addresses", { params: { path: { id } } }));
}

export async function addCustomerTag(id: string, body: AddCustomerTagRequest): Promise<CustomerTagResponse> {
  return unwrap(() => apiClient.POST("/api/v1/customers/{id}/tags", { params: { path: { id } }, body }));
}

export async function listCustomerTags(id: string): Promise<CustomerTagResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/customers/{id}/tags", { params: { path: { id } } }));
}

export async function removeCustomerTag(id: string, tag: string): Promise<void> {
  await unwrap(() => apiClient.DELETE("/api/v1/customers/{id}/tags/{tag}", { params: { path: { id, tag } } }));
}

// ------------------------------------------------------------------
// Notes / Communications
// ------------------------------------------------------------------

export async function addCustomerNote(id: string, body: CreateCustomerNoteRequest): Promise<CustomerNoteResponse> {
  return unwrap(() => apiClient.POST("/api/v1/customers/{id}/notes", { params: { path: { id } }, body }));
}

export async function listCustomerNotes(id: string, page = 1, pageSize = 20): Promise<PageCustomerNoteResponse> {
  return unwrap(() => apiClient.GET("/api/v1/customers/{id}/notes", { params: { path: { id }, query: { page, page_size: pageSize } } }));
}

export async function logCustomerCommunication(id: string, body: LogCommunicationRequest): Promise<CustomerCommunicationResponse> {
  return unwrap(() => apiClient.POST("/api/v1/customers/{id}/communications", { params: { path: { id } }, body }));
}

export async function listCustomerCommunications(id: string, page = 1, pageSize = 20): Promise<PageCustomerCommunicationResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/customers/{id}/communications", { params: { path: { id }, query: { page, page_size: pageSize } } }),
  );
}

// ------------------------------------------------------------------
// Reporting
// ------------------------------------------------------------------

/** Top customers by spend -- registered ahead of `/customers/{id}` server-side, same route-ordering rule as every other module's report routes. */
export async function getCustomerReport(branchId?: string): Promise<CustomerReportRow[]> {
  return unwrap(() => apiClient.GET("/api/v1/customers/report", { params: { query: { branch_id: branchId } } }));
}
