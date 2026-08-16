"use client";

import { useQuery } from "@tanstack/react-query";

import * as customersApi from "@/lib/api/customers";
import { useSessionStore } from "@/store/session-store";

/** Query key factory for 7J's Customer/CRM reads, mirroring lib/inventory/queries.ts's pattern. */
export const customerKeys = {
  all: ["customers"] as const,
  list: (params: customersApi.ListCustomersParams) => [...customerKeys.all, "list", params] as const,
  detail: (id: string) => [...customerKeys.all, "detail", id] as const,
  purchaseHistory: (id: string, page: number) => [...customerKeys.all, "purchase-history", id, page] as const,
  analytics: (id: string) => [...customerKeys.all, "analytics", id] as const,
  contacts: (id: string) => [...customerKeys.all, "contacts", id] as const,
  addresses: (id: string) => [...customerKeys.all, "addresses", id] as const,
  tags: (id: string) => [...customerKeys.all, "tags", id] as const,
  notes: (id: string, page: number) => [...customerKeys.all, "notes", id, page] as const,
  communications: (id: string, page: number) => [...customerKeys.all, "communications", id, page] as const,
  report: (branchId: string) => [...customerKeys.all, "report", branchId] as const,
};

export function useCustomerListQuery(params: customersApi.ListCustomersParams) {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: customerKeys.list(params),
    queryFn: () => customersApi.listCustomers(params),
    enabled: orgId !== null,
    staleTime: 15 * 1000,
  });
}

export function useCustomerDetailQuery(id: string | null) {
  return useQuery({
    queryKey: customerKeys.detail(id ?? "none"),
    queryFn: () => customersApi.getCustomer(id as string),
    enabled: id !== null,
    staleTime: 15 * 1000,
  });
}

export function useCustomerPurchaseHistoryQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: customerKeys.purchaseHistory(id ?? "none", page),
    queryFn: () => customersApi.getCustomerPurchaseHistory(id as string, page),
    enabled: id !== null,
  });
}

export function useCustomerAnalyticsQuery(id: string | null) {
  return useQuery({
    queryKey: customerKeys.analytics(id ?? "none"),
    queryFn: () => customersApi.getCustomerAnalytics(id as string),
    enabled: id !== null,
  });
}

export function useCustomerContactsQuery(id: string | null) {
  return useQuery({
    queryKey: customerKeys.contacts(id ?? "none"),
    queryFn: () => customersApi.listCustomerContacts(id as string),
    enabled: id !== null,
  });
}

export function useCustomerAddressesQuery(id: string | null) {
  return useQuery({
    queryKey: customerKeys.addresses(id ?? "none"),
    queryFn: () => customersApi.listCustomerAddresses(id as string),
    enabled: id !== null,
  });
}

export function useCustomerTagsQuery(id: string | null) {
  return useQuery({
    queryKey: customerKeys.tags(id ?? "none"),
    queryFn: () => customersApi.listCustomerTags(id as string),
    enabled: id !== null,
  });
}

export function useCustomerNotesQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: customerKeys.notes(id ?? "none", page),
    queryFn: () => customersApi.listCustomerNotes(id as string, page),
    enabled: id !== null,
  });
}

export function useCustomerCommunicationsQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: customerKeys.communications(id ?? "none", page),
    queryFn: () => customersApi.listCustomerCommunications(id as string, page),
    enabled: id !== null,
  });
}

export function useCustomerReportQuery(branchId: string) {
  return useQuery({
    queryKey: customerKeys.report(branchId),
    queryFn: () => customersApi.getCustomerReport(branchId || undefined),
  });
}
