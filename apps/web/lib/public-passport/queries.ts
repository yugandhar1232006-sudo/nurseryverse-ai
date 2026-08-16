"use client";

import { useQuery } from "@tanstack/react-query";

import * as publicPassportApi from "@/lib/api/public-passport";

/**
 * Query key factory for the public, unauthenticated Passport page.
 * Deliberately not merged into `lib/passport/queries.ts` -- see that
 * file's own docstring on why the internal and public API modules are
 * kept apart.
 */
export const publicPassportKeys = {
  all: ["public-passport"] as const,
  passport: (token: string) => [...publicPassportKeys.all, "passport", token] as const,
  scan: (token: string) => [...publicPassportKeys.all, "scan", token] as const,
};

/** The factual, point-in-time certificate -- no live data, no scan event recorded. */
export function usePublicPassportQuery(token: string) {
  return useQuery({ queryKey: publicPassportKeys.passport(token), queryFn: () => publicPassportApi.getPublicPassport(token) });
}

/**
 * The live "what does this plant need right now" view. `staleTime:
 * Infinity` and `refetchOnWindowFocus: false`/`refetchOnMount: false`
 * (via `gcTime`-independent one-shot semantics below) matter more here
 * than on any other query in this codebase: `QRService.scan()` records a
 * real `QRScanEvent` as a side effect of the backend call itself (see
 * `lib/api/public-passport.ts`'s docstring), so silently refetching this
 * on a window-focus or remount would inflate real scan-count analytics
 * with phantom scans the visitor never actually made.
 */
export function useQrScanQuery(token: string) {
  return useQuery({
    queryKey: publicPassportKeys.scan(token),
    queryFn: () => publicPassportApi.scanPassportQr(token),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
  });
}
