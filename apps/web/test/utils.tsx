import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";

/**
 * Test-only QueryClient: retries disabled (unlike the app's real
 * providers/query-provider.tsx, which retries transient failures up to
 * twice) so a test asserting on an error state doesn't have to wait out
 * real retry backoff, and `gcTime: Infinity` isn't needed since each test
 * gets its own fresh client via `renderWithProviders` rather than sharing
 * the browser-singleton one the app uses.
 */
function makeTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface RenderWithProvidersOptions extends Omit<RenderOptions, "wrapper"> {
  queryClient?: QueryClient;
}

/**
 * Every component test that touches `useMeQuery`/mutations/etc. needs a
 * `QueryClientProvider` ancestor -- this is the one place that wiring is
 * defined so test files don't each hand-roll a wrapper. Does *not*
 * include `AuthProvider`/`ThemeProvider`/`TooltipProvider` from the real
 * `app/layout.tsx` -- most tests render a single page/component in
 * isolation and opt into exactly the providers they need (e.g. login
 * tests don't need `AuthProvider`'s boot-session side effect firing
 * unexpectedly mid-test).
 */
export function renderWithProviders(ui: React.ReactElement, options: RenderWithProvidersOptions = {}) {
  const { queryClient = makeTestQueryClient(), ...rest } = options;

  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...rest }) };
}

export { makeTestQueryClient };
export * from "@testing-library/react";
