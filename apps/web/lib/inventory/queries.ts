"use client";

import { useQuery } from "@tanstack/react-query";

import * as inventoryApi from "@/lib/api/inventory";
import { useSessionStore } from "@/store/session-store";

/** Query key factory for 7I's Inventory reads, mirroring lib/plants/queries.ts's pattern. */
export const inventoryKeys = {
  all: ["inventory"] as const,
  units: () => [...inventoryKeys.all, "units"] as const,
  locations: (branchId: string, includeInactive: boolean) =>
    [...inventoryKeys.all, "locations", branchId, includeInactive] as const,
  list: (params: inventoryApi.ListInventoryParams) => [...inventoryKeys.all, "list", params] as const,
  detail: (id: string) => [...inventoryKeys.all, "detail", id] as const,
  lineMovements: (id: string, page: number) => [...inventoryKeys.all, "line-movements", id, page] as const,
  lineReservations: (id: string) => [...inventoryKeys.all, "line-reservations", id] as const,
  summary: (branchId: string) => [...inventoryKeys.all, "summary", branchId] as const,
  lowStock: (branchId: string) => [...inventoryKeys.all, "low-stock", branchId] as const,
  valuation: (branchId: string) => [...inventoryKeys.all, "valuation", branchId] as const,
  wasteReport: (params: inventoryApi.ReportParams) => [...inventoryKeys.all, "waste-report", params] as const,
  transferReport: (params: inventoryApi.ReportParams) => [...inventoryKeys.all, "transfer-report", params] as const,
  movementHistory: (params: inventoryApi.MovementHistoryParams) => [...inventoryKeys.all, "movement-history", params] as const,
  reservationReport: (params: inventoryApi.ReservationReportParams) => [...inventoryKeys.all, "reservation-report", params] as const,
};

/** Global, system-seeded reference data (migration 0002) -- same long staleTime as 7F's `usePlantCategoriesQuery`. */
export function useUnitsQuery() {
  return useQuery({
    queryKey: inventoryKeys.units(),
    queryFn: inventoryApi.listUnits,
    staleTime: 5 * 60 * 1000,
  });
}

/** `branch_id` is required server-side (`GET /inventory-locations`) -- `enabled: false` until a branch is actually selected. */
export function useInventoryLocationsQuery(branchId: string | null, includeInactive = false) {
  return useQuery({
    queryKey: inventoryKeys.locations(branchId ?? "none", includeInactive),
    queryFn: () => inventoryApi.listInventoryLocations(branchId as string, includeInactive),
    enabled: branchId !== null && branchId !== "",
  });
}

export function useInventoryListQuery(params: inventoryApi.ListInventoryParams) {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: inventoryKeys.list(params),
    queryFn: () => inventoryApi.listInventory(params),
    enabled: orgId !== null,
    staleTime: 15 * 1000,
  });
}

export function useInventoryDetailQuery(id: string | null) {
  return useQuery({
    queryKey: inventoryKeys.detail(id ?? "none"),
    queryFn: () => inventoryApi.getInventoryLine(id as string),
    enabled: id !== null,
    staleTime: 15 * 1000,
  });
}

export function useLineMovementsQuery(id: string | null, page: number) {
  return useQuery({
    queryKey: inventoryKeys.lineMovements(id ?? "none", page),
    queryFn: () => inventoryApi.getLineMovements(id as string, page),
    enabled: id !== null,
  });
}

export function useLineReservationsQuery(id: string | null) {
  return useQuery({
    queryKey: inventoryKeys.lineReservations(id ?? "none"),
    queryFn: () => inventoryApi.getLineReservations(id as string),
    enabled: id !== null,
  });
}

export function useInventorySummaryQuery(branchId: string) {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: inventoryKeys.summary(branchId),
    queryFn: () => inventoryApi.getInventorySummary(branchId || undefined),
    enabled: orgId !== null,
    staleTime: 15 * 1000,
  });
}

export function useLowStockReportQuery(branchId: string) {
  return useQuery({
    queryKey: inventoryKeys.lowStock(branchId),
    queryFn: () => inventoryApi.getLowStockReport(branchId || undefined),
  });
}

export function useStockValuationQuery(branchId: string) {
  return useQuery({
    queryKey: inventoryKeys.valuation(branchId),
    queryFn: () => inventoryApi.getStockValuation(branchId || undefined),
  });
}

export function useWasteReportQuery(params: inventoryApi.ReportParams) {
  return useQuery({
    queryKey: inventoryKeys.wasteReport(params),
    queryFn: () => inventoryApi.getWasteReport(params),
  });
}

export function useTransferReportQuery(params: inventoryApi.ReportParams) {
  return useQuery({
    queryKey: inventoryKeys.transferReport(params),
    queryFn: () => inventoryApi.getTransferReport(params),
  });
}

export function useMovementHistoryReportQuery(params: inventoryApi.MovementHistoryParams) {
  return useQuery({
    queryKey: inventoryKeys.movementHistory(params),
    queryFn: () => inventoryApi.getMovementHistory(params),
  });
}

export function useReservationReportQuery(params: inventoryApi.ReservationReportParams) {
  return useQuery({
    queryKey: inventoryKeys.reservationReport(params),
    queryFn: () => inventoryApi.getReservationReport(params),
  });
}
