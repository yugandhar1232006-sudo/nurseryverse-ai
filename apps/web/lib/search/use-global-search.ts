"use client";

import * as React from "react";
import { useQueries } from "@tanstack/react-query";

import { usePermissions } from "@/lib/auth/use-permissions";
import * as searchApi from "@/lib/search/api";

export type SearchResultKind = "plant" | "species" | "customer" | "inventory";

export interface SearchResult {
  kind: SearchResultKind;
  id: string;
  title: string;
  subtitle?: string;
  /** The real, already-existing route this result's parent list lives at -- see lib/search/api.ts's docstring on why results don't link to a per-id detail page that doesn't exist yet. */
  href: string;
}

const MIN_QUERY_LENGTH = 2;
const DEBOUNCE_MS = 250;

/** Debounces a fast-changing value -- used here to avoid firing four real API calls on every keystroke. */
function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = React.useState(value);
  React.useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * Fans a single query string out across the real per-entity search-capable
 * endpoints (`lib/search/api.ts`), gated one-to-one by the same permission
 * codes `nav-config.ts` uses for each destination -- a user who can't see
 * "Customers" in the sidebar never fires (or sees results from) a
 * customer search either, matching "hidden, not disabled" for search the
 * same way it applies to navigation.
 *
 * `useQueries` (not four separate `useQuery` calls) so all four searches
 * run in parallel and this hook can report one combined
 * loading/error/results state to the panel, while each entity's own
 * query key still caches/dedupes independently.
 */
export function useGlobalSearch(rawQuery: string) {
  const { can } = usePermissions();
  const query = useDebouncedValue(rawQuery.trim(), DEBOUNCE_MS);
  const isQueryValid = query.length >= MIN_QUERY_LENGTH;

  const canSearchPlants = can("plants:read");
  const canSearchSpecies = can("species:read");
  const canSearchCustomers = can("customers:read");
  const canSearchInventory = can("inventory:read");

  const results = useQueries({
    queries: [
      {
        queryKey: ["global-search", "plants", query],
        queryFn: () => searchApi.searchPlants(query),
        enabled: isQueryValid && canSearchPlants,
        staleTime: 30_000,
      },
      {
        queryKey: ["global-search", "species", query],
        queryFn: () => searchApi.searchSpecies(query),
        enabled: isQueryValid && canSearchSpecies,
        staleTime: 30_000,
      },
      {
        queryKey: ["global-search", "customers", query],
        queryFn: () => searchApi.searchCustomers(query),
        enabled: isQueryValid && canSearchCustomers,
        staleTime: 30_000,
      },
      {
        queryKey: ["global-search", "inventory", query],
        queryFn: () => searchApi.searchInventory(query),
        enabled: isQueryValid && canSearchInventory,
        staleTime: 30_000,
      },
    ],
  });

  const [plantsResult, speciesResult, customersResult, inventoryResult] = results;

  const items: SearchResult[] = React.useMemo(() => {
    if (!isQueryValid) return [];
    const out: SearchResult[] = [];

    (plantsResult.data ?? []).forEach((p) =>
      out.push({
        kind: "plant",
        id: p.id,
        title: p.common_label ?? `Batch ${p.batch_number ?? p.id.slice(0, 8)}`,
        subtitle: p.zone ? `Zone ${p.zone}` : undefined,
        href: "/plants",
      }),
    );
    (speciesResult.data ?? []).forEach((s) =>
      out.push({
        kind: "species",
        id: s.id,
        title: s.common_name,
        subtitle: s.botanical_name,
        href: "/plants/species",
      }),
    );
    (customersResult.data ?? []).forEach((c) =>
      out.push({
        kind: "customer",
        id: c.id,
        title: c.name,
        subtitle: c.email ?? undefined,
        href: "/customers",
      }),
    );
    (inventoryResult.data ?? []).forEach((i) =>
      out.push({
        kind: "inventory",
        id: i.id,
        title: i.name,
        subtitle: `${i.available_quantity} available`,
        href: "/inventory",
      }),
    );

    return out;
  }, [isQueryValid, plantsResult.data, speciesResult.data, customersResult.data, inventoryResult.data]);

  const enabledQueries = results.filter((r) => r.fetchStatus !== "idle" || r.isFetched);
  const isLoading = isQueryValid && results.some((r) => r.isLoading);
  const isError = isQueryValid && enabledQueries.length > 0 && enabledQueries.every((r) => r.isError);
  const firstError = results.find((r) => r.isError)?.error;

  return {
    query,
    isQueryValid,
    items,
    isLoading,
    isError,
    error: firstError,
    hasAnySearchPermission: canSearchPlants || canSearchSpecies || canSearchCustomers || canSearchInventory,
  };
}
