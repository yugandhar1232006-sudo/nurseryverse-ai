import { QueryClient } from "@tanstack/react-query";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";

import { bootSession } from "@/lib/auth/session-boot";
import { authKeys } from "@/lib/auth/queries";
import { useSessionStore } from "@/store/session-store";
import { server } from "@/test/msw/server";
import { makeMe } from "@/test/fixtures/auth";

const BASE = "http://localhost:8000";

describe("bootSession", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient();
  });

  it("restores a session when a valid refresh token exists (e.g. cookie-mode reload, or an in-memory bearer token)", async () => {
    useSessionStore.setState({ refreshToken: "refresh-token-1" });

    await bootSession(queryClient);

    const state = useSessionStore.getState();
    expect(state.status).toBe("authenticated");
    expect(state.user?.email).toBe("jane@example.com");
    expect(state.accessToken).toBe("access-token-2");
    // The Me query cache is primed directly so a component mounting
    // `useMeQuery()` right after boot doesn't trigger a redundant fetch.
    expect(queryClient.getQueryData(authKeys.me())).toEqual(makeMe());
  });

  it("clears session state when there is no valid refresh token (first visit, or a bearer-mode hard reload)", async () => {
    useSessionStore.setState({ refreshToken: null });

    await bootSession(queryClient);

    const state = useSessionStore.getState();
    expect(state.status).toBe("unauthenticated");
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
  });

  it("clears session state when the refresh token is present but rejected by the backend (expired/revoked)", async () => {
    useSessionStore.setState({ refreshToken: "a-revoked-token" });

    await bootSession(queryClient);

    const state = useSessionStore.getState();
    expect(state.status).toBe("unauthenticated");
    expect(state.user).toBeNull();
  });

  it("clears session state on a network failure during restoration (offline, DNS failure, backend down)", async () => {
    server.use(http.post(`${BASE}/api/v1/auth/refresh`, () => HttpResponse.error()));
    useSessionStore.setState({ refreshToken: "refresh-token-1" });

    await bootSession(queryClient);

    expect(useSessionStore.getState().status).toBe("unauthenticated");
  });

  it("clears session state when refresh succeeds but the follow-up /auth/me call fails", async () => {
    server.use(http.get(`${BASE}/api/v1/auth/me`, () => HttpResponse.json({ error: { code: "server_error", message: "boom" } }, { status: 500 })));
    useSessionStore.setState({ refreshToken: "refresh-token-1" });

    await bootSession(queryClient);

    const state = useSessionStore.getState();
    expect(state.status).toBe("unauthenticated");
    expect(state.user).toBeNull();
  });
});
