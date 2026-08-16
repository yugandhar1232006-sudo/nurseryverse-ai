import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Search-scoped, read-only wrappers around real per-entity list endpoints
 * that already support a `search=` query filter (confirmed directly from
 * the generated schema, not assumed):
 *  - `GET /plants?search=` (matches common label / QR token / batch number)
 *  - `GET /species?search=` (matches common/botanical name)
 *  - `GET /customers?search=`
 *  - `GET /inventory?search=`
 *
 * There is no unified `/search` endpoint anywhere in the backend -- the
 * 7C kickoff's "Support the real backend search capabilities where
 * available. Do not create fake search results" is satisfied here by
 * fanning a single query out across these four real endpoints
 * client-side (see `lib/search/use-global-search.ts`) rather than
 * inventing a backend capability that doesn't exist.
 *
 * Invoices are excluded for the same reason `nav-config.ts` excludes them
 * from the sidebar: no backend route exists for that resource at all
 * (confirmed by direct file-listing inspection of
 * apps/api/app/api/routes/) despite a seeded permission code.
 *
 * These are intentionally kept separate from any future
 * lib/api/plants.ts / species.ts / customers.ts / inventory.ts full CRUD
 * modules (7F/7I/7J) -- this file only ever needs a `page_size=5,
 * search=q` read, not the full surface those modules will eventually
 * own, and duplicating that tiny slice here avoids building out unrelated
 * CRUD ahead of its phase.
 */

export type SearchedSpecies = Pick<components["schemas"]["SpeciesResponse"], "id" | "common_name" | "botanical_name">;
export type SearchedPlant = Pick<components["schemas"]["PlantResponse"], "id" | "common_label" | "batch_number" | "zone">;
export type SearchedCustomer = Pick<components["schemas"]["CustomerResponse"], "id" | "name" | "email">;
export type SearchedInventoryLine = Pick<components["schemas"]["InventoryResponse"], "id" | "name" | "available_quantity">;

const RESULT_LIMIT = 5;

export async function searchPlants(query: string): Promise<SearchedPlant[]> {
  const page = await unwrap(() =>
    apiClient.GET("/api/v1/plants", { params: { query: { search: query, page_size: RESULT_LIMIT } } }),
  );
  return page.items;
}

export async function searchSpecies(query: string): Promise<SearchedSpecies[]> {
  const page = await unwrap(() =>
    apiClient.GET("/api/v1/species", { params: { query: { search: query, page_size: RESULT_LIMIT } } }),
  );
  return page.items;
}

export async function searchCustomers(query: string): Promise<SearchedCustomer[]> {
  const page = await unwrap(() =>
    apiClient.GET("/api/v1/customers", { params: { query: { search: query, page_size: RESULT_LIMIT } } }),
  );
  return page.items;
}

export async function searchInventory(query: string): Promise<SearchedInventoryLine[]> {
  const page = await unwrap(() =>
    apiClient.GET("/api/v1/inventory", { params: { query: { search: query, page_size: RESULT_LIMIT } } }),
  );
  return page.items;
}
