import * as React from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import {
  useChangePasswordMutation,
  useLoginMutation,
  useLogoutAllMutation,
  useLogoutMutation,
} from "@/lib/auth/mutations";
import { useSessionStore } from "@/store/session-store";
import { server } from "@/test/msw/server";
import { makeTestQueryClient } from "@/test/utils";
import { VALID_EMAIL, VALID_PASSWORD } from "@/test/msw/handlers";

const BASE = "http://localhost:8000";

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = makeTestQueryClient();
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useLoginMutation", () => {
  it("logs in, stores the token pair, fetches /auth/me, and flips the session to authenticated", async () => {
    const { result } = renderHook(() => useLoginMutation(), { wrapper });

    result.current.mutate({ email: VALID_EMAIL, password: VALID_PASSWORD });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const state = useSessionStore.getState();
    expect(state.status).toBe("authenticated");
    expect(state.accessToken).toBe("access-token-1");
    expect(state.user?.email).toBe(VALID_EMAIL);
  });

  it("surfaces invalid-credentials as a rejected mutation without touching session state", async () => {
    const { result } = renderHook(() => useLoginMutation(), { wrapper });

    result.current.mutate({ email: VALID_EMAIL, password: "wrong-password" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(useSessionStore.getState().status).toBe("resolving");
  });
});

describe("useLogoutMutation", () => {
  it("clears local session state on success", async () => {
    useSessionStore.setState({ status: "authenticated", accessToken: "t", refreshToken: "r" });
    const { result } = renderHook(() => useLogoutMutation(), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(useSessionStore.getState().status).toBe("unauthenticated");
  });

  it("still clears local session state when the backend logout call fails (network down) -- logging out is always honored locally", async () => {
    server.use(http.post(`${BASE}/api/v1/auth/logout`, () => HttpResponse.error()));
    useSessionStore.setState({ status: "authenticated", accessToken: "t", refreshToken: "r" });
    const { result } = renderHook(() => useLogoutMutation(), { wrapper });

    result.current.mutate();

    // TanStack Query's `UseMutationResult` has no `isSettled` field --
    // `isError` is the right terminal-state check here since the backend
    // call itself rejects (network down).
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(useSessionStore.getState().status).toBe("unauthenticated");
  });
});

describe("useLogoutAllMutation", () => {
  it("clears local session state on success", async () => {
    useSessionStore.setState({ status: "authenticated", accessToken: "t", refreshToken: "r" });
    const { result } = renderHook(() => useLogoutAllMutation(), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(useSessionStore.getState().status).toBe("unauthenticated");
  });
});

describe("useChangePasswordMutation", () => {
  it("proactively clears the session on success (the backend revokes every session, including this one)", async () => {
    useSessionStore.setState({ status: "authenticated", accessToken: "t", refreshToken: "r" });
    const { result } = renderHook(() => useChangePasswordMutation(), { wrapper });

    result.current.mutate({ current_password: "old-pw", new_password: "New-password-123" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(useSessionStore.getState().status).toBe("unauthenticated");
  });
});
