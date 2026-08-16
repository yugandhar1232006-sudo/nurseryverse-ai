"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as inventoryApi from "@/lib/api/inventory";
import { inventoryKeys } from "@/lib/inventory/queries";
import { toast } from "@/lib/toast";

function invalidateLine(queryClient: ReturnType<typeof useQueryClient>, id: string) {
  void queryClient.invalidateQueries({ queryKey: inventoryKeys.detail(id) });
  void queryClient.invalidateQueries({ queryKey: [...inventoryKeys.all, "list"] });
}

export function useCreateInventoryLocationMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: inventoryApi.createInventoryLocation,
    onSuccess: (location) => {
      void queryClient.invalidateQueries({ queryKey: [...inventoryKeys.all, "locations", location.branch_id] });
      toast.success("Location created");
    },
  });
}

export function useDeactivateInventoryLocationMutation(branchId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => inventoryApi.deactivateInventoryLocation(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...inventoryKeys.all, "locations", branchId] });
      toast.success("Location deactivated");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useCreateInventoryLineMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: inventoryApi.createInventoryLine,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...inventoryKeys.all, "list"] });
      toast.success("Inventory line created");
    },
  });
}

export function useReceiveStockMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: inventoryApi.ReceiveStockRequest) => inventoryApi.receiveStock(id, body),
    onSuccess: () => {
      invalidateLine(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineMovements(id, 1) });
      toast.success("Stock received");
    },
    onError: (error) => toast.apiError(error),
  });
}

/** A 403 here means the caller lacks `inventory:write` on the destination branch for a cross-branch transfer -- surfaced as a toast, dialog stays open. */
export function useTransferStockMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: inventoryApi.TransferStockRequest) => inventoryApi.transferStock(id, body),
    onSuccess: () => {
      invalidateLine(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineMovements(id, 1) });
      toast.success("Stock transferred");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useReserveStockMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: inventoryApi.ReserveStockRequest) => inventoryApi.reserveStock(id, body),
    onSuccess: () => {
      invalidateLine(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineReservations(id) });
      toast.success("Stock reserved");
    },
    onError: (error) => toast.apiError(error),
  });
}

/** Insufficient-stock (e.g. adjusting below zero) comes back as a real 409, per `_apply_change()`'s docstring -- not validated client-side. */
export function useAdjustStockMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: inventoryApi.AdjustStockRequest) => inventoryApi.adjustStock(id, body),
    onSuccess: () => {
      invalidateLine(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineMovements(id, 1) });
      toast.success("Stock adjusted");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useMarkDamagedMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: inventoryApi.MarkDamagedRequest) => inventoryApi.markDamaged(id, body),
    onSuccess: () => {
      invalidateLine(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineMovements(id, 1) });
      toast.success("Stock marked as damaged");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useDisposeStockMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: inventoryApi.DisposeStockRequest) => inventoryApi.disposeStock(id, body),
    onSuccess: () => {
      invalidateLine(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineMovements(id, 1) });
      toast.success("Stock disposed");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useSellStockMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: inventoryApi.SellStockRequest) => inventoryApi.sellStock(id, body),
    onSuccess: () => {
      invalidateLine(queryClient, id);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineMovements(id, 1) });
      toast.success("Stock sold");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useArchiveInventoryLineMutation(id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: inventoryApi.ArchiveInventoryRequest) => inventoryApi.archiveInventoryLine(id, body),
    onSuccess: () => {
      invalidateLine(queryClient, id);
      toast.success("Inventory line archived");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useReleaseReservationMutation(lineId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (reservationId: string) => inventoryApi.releaseReservation(reservationId),
    onSuccess: () => {
      invalidateLine(queryClient, lineId);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineReservations(lineId) });
      toast.success("Reservation released");
    },
    onError: (error) => toast.apiError(error),
  });
}

export function useFulfillReservationMutation(lineId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ reservationId, body }: { reservationId: string; body: inventoryApi.FulfillReservationRequest }) =>
      inventoryApi.fulfillReservation(reservationId, body),
    onSuccess: () => {
      invalidateLine(queryClient, lineId);
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineReservations(lineId) });
      void queryClient.invalidateQueries({ queryKey: inventoryKeys.lineMovements(lineId, 1) });
      toast.success("Reservation fulfilled");
    },
    onError: (error) => toast.apiError(error),
  });
}
