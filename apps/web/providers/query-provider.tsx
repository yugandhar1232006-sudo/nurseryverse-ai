"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

import { isApiError } from "@/lib/api/error";

/**
 * All server state (anything that came from the real backend) lives in
 * TanStack Query. Client/UI-only state lives in Zustand (see
 * store/session-store.ts, store/ui-store.ts, store/notification-store.ts).
 * This split is deliberate per the Phase 4 state-management architecture
 * doc -- do not put server data into Zustand or UI state into React Query.
 */
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30 * 1000,
        gcTime: 5 * 60 * 1000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          // Never retry auth/permission/validation/not-found errors -- retrying
          // won't change a 401/403/404/422 outcome and just delays user feedback.
          if (isApiError(error) && [400, 401, 403, 404, 409, 422].includes(error.status)) {
            return false;
          }
          return failureCount < 2;
        },
      },
      mutations: {
        retry: false,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

function getQueryClient() {
  if (typeof window === "undefined") {
    // Server: always make a new query client.
    return makeQueryClient();
  }
  // Browser: reuse the client across renders so cache survives re-renders.
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === "development" && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
