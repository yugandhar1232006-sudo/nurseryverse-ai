"use client";

import { useQuery } from "@tanstack/react-query";

import * as salesApi from "@/lib/api/sales";
import { useSessionStore } from "@/store/session-store";

/** Query key factory for 7J's Sales reads, mirroring lib/inventory/queries.ts's pattern. */
export const salesKeys = {
  all: ["sales-module"] as const,
  quotationList: (params: salesApi.ListQuotationsParams) => [...salesKeys.all, "quotation-list", params] as const,
  quotationDetail: (id: string) => [...salesKeys.all, "quotation-detail", id] as const,
  quotationItems: (id: string) => [...salesKeys.all, "quotation-items", id] as const,
  orderList: (params: salesApi.ListSalesOrdersParams) => [...salesKeys.all, "order-list", params] as const,
  orderDetail: (id: string) => [...salesKeys.all, "order-detail", id] as const,
  orderItems: (id: string) => [...salesKeys.all, "order-items", id] as const,
  saleList: (params: salesApi.ListSalesParams) => [...salesKeys.all, "sale-list", params] as const,
  saleDetail: (id: string) => [...salesKeys.all, "sale-detail", id] as const,
  saleItems: (id: string) => [...salesKeys.all, "sale-items", id] as const,
  invoiceDetail: (id: string) => [...salesKeys.all, "invoice-detail", id] as const,
  invoiceItems: (id: string) => [...salesKeys.all, "invoice-items", id] as const,
  invoicePayments: (id: string) => [...salesKeys.all, "invoice-payments", id] as const,
  returnList: (params: salesApi.ListReturnsParams) => [...salesKeys.all, "return-list", params] as const,
  returnDetail: (id: string) => [...salesKeys.all, "return-detail", id] as const,
  returnItems: (id: string) => [...salesKeys.all, "return-items", id] as const,
  refundList: (params: salesApi.ListRefundsParams) => [...salesKeys.all, "refund-list", params] as const,
  refundDetail: (id: string) => [...salesKeys.all, "refund-detail", id] as const,
  salesReport: (params: salesApi.SalesReportParams) => [...salesKeys.all, "sales-report", params] as const,
  revenueReport: (params: salesApi.SalesReportParams) => [...salesKeys.all, "revenue-report", params] as const,
};

function useOrgScoped() {
  return useSessionStore((state) => state.user?.org_id ?? null) !== null;
}

// ------------------------------------------------------------------
// Quotations
// ------------------------------------------------------------------

export function useQuotationListQuery(params: salesApi.ListQuotationsParams) {
  const enabled = useOrgScoped();
  return useQuery({ queryKey: salesKeys.quotationList(params), queryFn: () => salesApi.listQuotations(params), enabled, staleTime: 15 * 1000 });
}

export function useQuotationDetailQuery(id: string | null) {
  return useQuery({
    queryKey: salesKeys.quotationDetail(id ?? "none"),
    queryFn: () => salesApi.getQuotation(id as string),
    enabled: id !== null,
    staleTime: 15 * 1000,
  });
}

export function useQuotationItemsQuery(id: string | null) {
  return useQuery({ queryKey: salesKeys.quotationItems(id ?? "none"), queryFn: () => salesApi.getQuotationItems(id as string), enabled: id !== null });
}

// ------------------------------------------------------------------
// Sales Orders
// ------------------------------------------------------------------

export function useSalesOrderListQuery(params: salesApi.ListSalesOrdersParams) {
  const enabled = useOrgScoped();
  return useQuery({ queryKey: salesKeys.orderList(params), queryFn: () => salesApi.listSalesOrders(params), enabled, staleTime: 15 * 1000 });
}

export function useSalesOrderDetailQuery(id: string | null) {
  return useQuery({
    queryKey: salesKeys.orderDetail(id ?? "none"),
    queryFn: () => salesApi.getSalesOrder(id as string),
    enabled: id !== null,
    staleTime: 15 * 1000,
  });
}

export function useSalesOrderItemsQuery(id: string | null) {
  return useQuery({ queryKey: salesKeys.orderItems(id ?? "none"), queryFn: () => salesApi.getSalesOrderItems(id as string), enabled: id !== null });
}

// ------------------------------------------------------------------
// Sales (completed) + Reports
// ------------------------------------------------------------------

export function useSaleListQuery(params: salesApi.ListSalesParams) {
  const enabled = useOrgScoped();
  return useQuery({ queryKey: salesKeys.saleList(params), queryFn: () => salesApi.listSales(params), enabled, staleTime: 15 * 1000 });
}

export function useSaleDetailQuery(id: string | null) {
  return useQuery({ queryKey: salesKeys.saleDetail(id ?? "none"), queryFn: () => salesApi.getSale(id as string), enabled: id !== null, staleTime: 15 * 1000 });
}

export function useSaleItemsQuery(id: string | null) {
  return useQuery({ queryKey: salesKeys.saleItems(id ?? "none"), queryFn: () => salesApi.getSaleItems(id as string), enabled: id !== null });
}

export function useSalesReportQuery(params: salesApi.SalesReportParams) {
  return useQuery({ queryKey: salesKeys.salesReport(params), queryFn: () => salesApi.getSalesReport(params) });
}

export function useRevenueReportQuery(params: salesApi.SalesReportParams) {
  return useQuery({ queryKey: salesKeys.revenueReport(params), queryFn: () => salesApi.getRevenueReport(params) });
}

// ------------------------------------------------------------------
// Invoices + Payments
// ------------------------------------------------------------------

export function useInvoiceDetailQuery(id: string | null) {
  return useQuery({
    queryKey: salesKeys.invoiceDetail(id ?? "none"),
    queryFn: () => salesApi.getInvoice(id as string),
    enabled: id !== null,
    staleTime: 5 * 1000,
  });
}

export function useInvoiceItemsQuery(id: string | null) {
  return useQuery({ queryKey: salesKeys.invoiceItems(id ?? "none"), queryFn: () => salesApi.getInvoiceItems(id as string), enabled: id !== null });
}

export function useInvoicePaymentsQuery(id: string | null) {
  return useQuery({
    queryKey: salesKeys.invoicePayments(id ?? "none"),
    queryFn: () => salesApi.listInvoicePayments(id as string),
    enabled: id !== null,
  });
}

// ------------------------------------------------------------------
// Returns + Refunds
// ------------------------------------------------------------------

export function useReturnListQuery(params: salesApi.ListReturnsParams) {
  const enabled = useOrgScoped();
  return useQuery({ queryKey: salesKeys.returnList(params), queryFn: () => salesApi.listReturns(params), enabled, staleTime: 15 * 1000 });
}

export function useReturnDetailQuery(id: string | null) {
  return useQuery({ queryKey: salesKeys.returnDetail(id ?? "none"), queryFn: () => salesApi.getReturn(id as string), enabled: id !== null, staleTime: 15 * 1000 });
}

export function useReturnItemsQuery(id: string | null) {
  return useQuery({ queryKey: salesKeys.returnItems(id ?? "none"), queryFn: () => salesApi.getReturnItems(id as string), enabled: id !== null });
}

export function useRefundListQuery(params: salesApi.ListRefundsParams) {
  const enabled = useOrgScoped();
  return useQuery({ queryKey: salesKeys.refundList(params), queryFn: () => salesApi.listRefunds(params), enabled, staleTime: 15 * 1000 });
}
