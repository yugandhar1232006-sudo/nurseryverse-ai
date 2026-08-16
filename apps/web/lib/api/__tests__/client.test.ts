import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { apiClient, unwrap } from "@/lib/api/client";
import { ApiError, isApiError } from "@/lib/api/error";
import { useSessionStore } from "@/store/session-store";
import { server } from "@/test/msw/server";
import { makeMe } from "@/test/fixtures/auth";

const BASE = "http://localhost:8000";
const getMe = () => unwrap(() => apiClient.GET("/api/v1/auth/me", {}));

describe("unwrap / withAuthRetry (401 refresh-and-retry)", () => {
  it("silently refreshes and retries once on a 401, returning the retried call's result", async () => {
    let calls = 0;
    server.use(
      http.get(`${BASE}/api/v1/auth/me`, ({ request }) => {
        calls += 1;
        if (calls === 1) {
          return HttpResponse.json(
            { error: { code: "authentication_error", message: "Expired." } },
            { status: 401 },
          );
        }
        // Retried call: the client must be sending the *rotated* token.
        expect(request.headers.get("authorization")).toBe("Bearer access-token-2");
        return HttpResponse.json(makeMe());
      }),
    );
    useSessionStore.setState({ accessToken: "expired-token", refreshToken: "refresh-token-1" });

    const me = await getMe();

    expect(me.email).toBe("jane@example.com");
    expect(calls).toBe(2);
    expect(useSessionStore.getState().accessToken).toBe("access-token-2");
  });

  it("dedupes concurrent 401s into a single /auth/refresh call", async () => {
    let meCalls = 0;
    let refreshCalls = 0;
    server.use(
      http.get(`${BASE}/api/v1/auth/me`, ({ request }) => {
        meCalls += 1;
        if (request.headers.get("authorization") === "Bearer access-token-2") {
          return HttpResponse.json(makeMe());
        }
        return HttpResponse.json(
          { error: { code: "authentication_error", message: "Expired." } },
          { status: 401 },
        );
      }),
      http.post(`${BASE}/api/v1/auth/refresh`, () => {
        refreshCalls += 1;
        return HttpResponse.json({
          access_token: "access-token-2",
          refresh_token: "refresh-token-2",
          token_type: "bearer",
          expires_in: 900,
        });
      }),
    );
    useSessionStore.setState({ accessToken: "expired-token", refreshToken: "refresh-token-1" });

    const results = await Promise.all([getMe(), getMe(), getMe()]);

    expect(results.every((r) => r.email === "jane@example.com")).toBe(true);
    expect(refreshCalls).toBe(1);
    expect(meCalls).toBe(6); // 3 initial 401s + 3 retries
  });

  it("clears the session and surfaces an ApiError when refresh itself fails", async () => {
    server.use(
      http.get(`${BASE}/api/v1/auth/me`, () =>
        HttpResponse.json({ error: { code: "authentication_error", message: "Expired." } }, { status: 401 }),
      ),
    );
    useSessionStore.setState({
      accessToken: "expired-token",
      refreshToken: "a-revoked-token", // not recognized by the default refresh handler
      user: makeMe(),
      status: "authenticated",
    });

    await expect(getMe()).rejects.toBeInstanceOf(ApiError);

    const state = useSessionStore.getState();
    expect(state.status).toBe("unauthenticated");
    expect(state.accessToken).toBeNull();
  });

  it("clears the session when the retried call 401s again even after a successful refresh", async () => {
    server.use(http.get(`${BASE}/api/v1/auth/me`, () =>
      HttpResponse.json({ error: { code: "authentication_error", message: "Still expired." } }, { status: 401 }),
    ));
    useSessionStore.setState({ accessToken: "expired-token", refreshToken: "refresh-token-1" });

    await expect(getMe()).rejects.toBeInstanceOf(ApiError);
    expect(useSessionStore.getState().status).toBe("unauthenticated");
  });

  it("normalizes a thrown network failure into an ApiError with status 0, without touching the session", async () => {
    server.use(http.get(`${BASE}/api/v1/auth/me`, () => HttpResponse.error()));
    useSessionStore.setState({ accessToken: "some-token", refreshToken: "refresh-token-1" });

    let caught: unknown;
    try {
      await getMe();
    } catch (error) {
      caught = error;
    }

    expect(isApiError(caught)).toBe(true);
    expect((caught as ApiError).status).toBe(0);
    expect((caught as ApiError).code).toBe("network_error");
  });

  it("parses the real backend 422 envelope into flattened fieldErrors", async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/login`, () =>
        HttpResponse.json(
          {
            error: {
              code: "validation_error",
              message: "Validation failed.",
              context: {
                errors: [{ loc: ["body", "email"], msg: "field required", type: "missing" }],
              },
            },
            request_id: "req-123",
          },
          { status: 422 },
        ),
      ),
    );

    let caught: unknown;
    try {
      await unwrap(() =>
        apiClient.POST("/api/v1/auth/login", { body: { email: "", password: "" } }),
      );
    } catch (error) {
      caught = error;
    }

    expect(isApiError(caught)).toBe(true);
    const apiError = caught as ApiError;
    expect(apiError.status).toBe(422);
    expect(apiError.requestId).toBe("req-123");
    expect(apiError.fieldErrors).toEqual({ email: ["field required"] });
  });
});
