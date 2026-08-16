import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 8's Inventory & Stock Management REST API
 * (`/inventory-locations/*`, `/inventory/*`, `/stock-reservations/*`,
 * `/units`). Mirrors `inventory.py`'s own three-path-root layout rather
 * than inventing a single `/inventory` namespace client-side.
 *
 * Permission model (see `inventory.py`'s module docstring): `inventory:read`
 * gates every GET, `inventory:write` gates the normal operational flows
 * (create, receive, transfer, reserve, release, fulfill, sell),
 * `inventory:adjust` gates the quantity-correcting/write-off actions
 * (Adjust, Damage, Dispose, Archive, and fulfilling a reservation -- see
 * `fulfill_reservation`'s route, which is `inventory:adjust` not `:write`
 * since it converts a hold into a real departure of stock).
 *
 * `UnitResponse`/`listUnits()` is the real defect fix from this phase --
 * see `UnitRepository`'s docstring in the backend for the full story.
 */

export type InventoryLocationType = components["schemas"]["InventoryLocationType"];
export type InventoryLocationResponse = components["schemas"]["InventoryLocationResponse"];
export type CreateInventoryLocationRequest = components["schemas"]["CreateInventoryLocationRequest"];

export type InventoryResponse = components["schemas"]["InventoryResponse"];
export type PageInventoryResponse = components["schemas"]["Page_InventoryResponse_"];
export type CreateInventoryLineRequest = components["schemas"]["CreateInventoryLineRequest"];
export type ReceiveStockRequest = components["schemas"]["ReceiveStockRequest"];
export type TransferStockRequest = components["schemas"]["TransferStockRequest"];
export type ReserveStockRequest = components["schemas"]["ReserveStockRequest"];
export type AdjustStockRequest = components["schemas"]["AdjustStockRequest"];
export type InventoryAdjustmentReason = components["schemas"]["InventoryAdjustmentReason"];
export type MarkDamagedRequest = components["schemas"]["MarkDamagedRequest"];
export type DisposeStockRequest = components["schemas"]["DisposeStockRequest"];
export type SellStockRequest = components["schemas"]["SellStockRequest"];
export type ArchiveInventoryRequest = components["schemas"]["ArchiveInventoryRequest"];

export type StockMovementType = components["schemas"]["StockMovementType"];
export type StockMovementResponse = components["schemas"]["StockMovementResponse"];
export type PageStockMovementResponse = components["schemas"]["Page_StockMovementResponse_"];

export type StockReservationStatus = components["schemas"]["StockReservationStatus"];
export type StockReservationResponse = components["schemas"]["StockReservationResponse"];
export type PageStockReservationResponse = components["schemas"]["Page_StockReservationResponse_"];
export type FulfillReservationRequest = components["schemas"]["FulfillReservationRequest"];

export type InventorySummaryResponse = components["schemas"]["InventorySummaryResponse"];
export type StockValuationResponse = components["schemas"]["StockValuationResponse"];
export type WasteReportResponse = components["schemas"]["WasteReportResponse"];
export type TransferReportResponse = components["schemas"]["TransferReportResponse"];

export type UnitResponse = components["schemas"]["UnitResponse"];

// ------------------------------------------------------------------
// Units (global reference data)
// ------------------------------------------------------------------

export async function listUnits(): Promise<UnitResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/units"));
}

// ------------------------------------------------------------------
// Inventory Locations
// ------------------------------------------------------------------

export async function listInventoryLocations(branchId: string, includeInactive = false): Promise<InventoryLocationResponse[]> {
  return unwrap(() =>
    apiClient.GET("/api/v1/inventory-locations", {
      params: { query: { branch_id: branchId, include_inactive: includeInactive } },
    }),
  );
}

export async function createInventoryLocation(body: CreateInventoryLocationRequest): Promise<InventoryLocationResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory-locations", { body }));
}

export async function deactivateInventoryLocation(id: string): Promise<InventoryLocationResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory-locations/{id}/deactivate", { params: { path: { id } } }));
}

// ------------------------------------------------------------------
// Inventory: CRUD + Search
// ------------------------------------------------------------------

export interface ListInventoryParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
  category_id?: string;
  species_id?: string;
  location_id?: string;
  search?: string;
  low_stock_only?: boolean;
  include_archived?: boolean;
  sort_by?: string;
  sort_dir?: string;
}

export async function listInventory(params: ListInventoryParams = {}): Promise<PageInventoryResponse> {
  return unwrap(() => apiClient.GET("/api/v1/inventory", { params: { query: params } }));
}

export async function createInventoryLine(body: CreateInventoryLineRequest): Promise<InventoryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory", { body }));
}

export async function getInventoryLine(id: string): Promise<InventoryResponse> {
  return unwrap(() => apiClient.GET("/api/v1/inventory/{id}", { params: { path: { id } } }));
}

export async function getLineMovements(id: string, page = 1, pageSize = 20): Promise<PageStockMovementResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/inventory/{id}/movements", { params: { path: { id }, query: { page, page_size: pageSize } } }),
  );
}

export async function getLineReservations(id: string): Promise<StockReservationResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/inventory/{id}/reservations", { params: { path: { id } } }));
}

// ------------------------------------------------------------------
// Inventory: mutating actions
// ------------------------------------------------------------------

export async function receiveStock(id: string, body: ReceiveStockRequest): Promise<InventoryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory/{id}/receive", { params: { path: { id } }, body }));
}

/** A cross-branch transfer needs `inventory:write` on both the source AND destination branch -- a 403 means the caller lacks it on one side. */
export async function transferStock(id: string, body: TransferStockRequest): Promise<InventoryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory/{id}/transfer", { params: { path: { id } }, body }));
}

export async function reserveStock(id: string, body: ReserveStockRequest): Promise<StockReservationResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory/{id}/reserve", { params: { path: { id } }, body }));
}

export async function adjustStock(id: string, body: AdjustStockRequest): Promise<InventoryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory/{id}/adjust", { params: { path: { id } }, body }));
}

export async function markDamaged(id: string, body: MarkDamagedRequest): Promise<InventoryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory/{id}/damage", { params: { path: { id } }, body }));
}

export async function disposeStock(id: string, body: DisposeStockRequest): Promise<InventoryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory/{id}/dispose", { params: { path: { id } }, body }));
}

export async function sellStock(id: string, body: SellStockRequest): Promise<InventoryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory/{id}/sell", { params: { path: { id } }, body }));
}

export async function archiveInventoryLine(id: string, body: ArchiveInventoryRequest): Promise<InventoryResponse> {
  return unwrap(() => apiClient.POST("/api/v1/inventory/{id}/archive", { params: { path: { id } }, body }));
}

// ------------------------------------------------------------------
// Stock Reservations: release / fulfill
// ------------------------------------------------------------------

export async function releaseReservation(id: string): Promise<StockReservationResponse> {
  return unwrap(() => apiClient.POST("/api/v1/stock-reservations/{id}/release", { params: { path: { id } } }));
}

export async function fulfillReservation(id: string, body: FulfillReservationRequest): Promise<StockReservationResponse> {
  return unwrap(() => apiClient.POST("/api/v1/stock-reservations/{id}/fulfill", { params: { path: { id } }, body }));
}

// ------------------------------------------------------------------
// Reporting
// ------------------------------------------------------------------

export interface ReportParams {
  branch_id?: string;
  date_from?: string;
  date_to?: string;
}

export async function getInventorySummary(branchId?: string): Promise<InventorySummaryResponse> {
  return unwrap(() => apiClient.GET("/api/v1/inventory/summary", { params: { query: { branch_id: branchId } } }));
}

export async function getLowStockReport(branchId?: string): Promise<InventoryResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/inventory/low-stock", { params: { query: { branch_id: branchId } } }));
}

export async function getStockValuation(branchId?: string): Promise<StockValuationResponse> {
  return unwrap(() => apiClient.GET("/api/v1/inventory/valuation", { params: { query: { branch_id: branchId } } }));
}

export async function getWasteReport(params: ReportParams = {}): Promise<WasteReportResponse> {
  return unwrap(() => apiClient.GET("/api/v1/inventory/waste-report", { params: { query: params } }));
}

export async function getTransferReport(params: ReportParams = {}): Promise<TransferReportResponse> {
  return unwrap(() => apiClient.GET("/api/v1/inventory/transfer-report", { params: { query: params } }));
}

export interface MovementHistoryParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
  movement_type?: StockMovementType;
  date_from?: string;
  date_to?: string;
}

/** Org-wide movement ledger (distinct from `getLineMovements`, which is scoped to one inventory line). */
export async function getMovementHistory(params: MovementHistoryParams = {}): Promise<PageStockMovementResponse> {
  return unwrap(() => apiClient.GET("/api/v1/inventory/movements", { params: { query: params } }));
}

export interface ReservationReportParams {
  page?: number;
  page_size?: number;
  branch_id?: string;
}

/** Org-wide active-reservations report (distinct from `getLineReservations`, which is scoped to one inventory line). */
export async function getReservationReport(params: ReservationReportParams = {}): Promise<PageStockReservationResponse> {
  return unwrap(() => apiClient.GET("/api/v1/inventory/reservations", { params: { query: params } }));
}
