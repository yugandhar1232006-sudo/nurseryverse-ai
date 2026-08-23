"use client";

import { useQuery } from "@tanstack/react-query";

import * as suppliersApi from "@/lib/api/suppliers";
import { useSessionStore } from "@/store/session-store";

export const supplierKeys = {
  all: ["suppliers"] as const,
  list: () => [...supplierKeys.all, "list"] as const,
};

export function useSuppliersQuery() {
  const orgId = useSessionStore((state) => state.user?.org_id ?? null);

  return useQuery({
    queryKey: supplierKeys.list(),
    queryFn: suppliersApi.listSuppliers,
    enabled: orgId !== null,
    staleTime: 60 * 1000,
  });
}
