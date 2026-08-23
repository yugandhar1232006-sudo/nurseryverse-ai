import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

export type SupplierResponse = components["schemas"]["SupplierResponse"];

export async function listSuppliers(): Promise<SupplierResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/suppliers"));
}
