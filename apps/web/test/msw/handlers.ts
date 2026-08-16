import { http, HttpResponse } from "msw";

import { makeErrorEnvelope, makeMe, makeSession, makeTokenPair } from "@/test/fixtures/auth";

const BASE = "http://localhost:8000";

export const VALID_EMAIL = "jane@example.com";
export const VALID_PASSWORD = "correct-password-123";

/**
 * Default, "happy path" handlers for a single known-good user. Individual
 * tests override specific handlers with `server.use(...)` to exercise
 * error states (invalid credentials, locked account, network failure,
 * expired token, etc.) -- see test/msw/server.ts's per-test reset.
 *
 * These intercept at the network layer (MSW), not by mocking
 * `lib/api/auth.ts` or `apiClient` -- the real `unwrap`/`withAuthRetry`/
 * `ApiError` parsing logic in lib/api/client.ts genuinely runs against
 * these responses, per the Phase 7B kickoff's "do not mock the entire
 * authentication system."
 */
export const handlers = [
  http.post(`${BASE}/api/v1/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (body.email === VALID_EMAIL && body.password === VALID_PASSWORD) {
      return HttpResponse.json(makeTokenPair());
    }
    return HttpResponse.json(
      makeErrorEnvelope({ code: "authentication_error", message: "Incorrect email or password." }),
      { status: 401 },
    );
  }),

  http.post(`${BASE}/api/v1/auth/refresh`, async ({ request }) => {
    const body = (await request.json()) as { refresh_token: string | null };
    if (body.refresh_token === "refresh-token-1" || body.refresh_token === "refresh-token-2") {
      return HttpResponse.json(makeTokenPair({ access_token: "access-token-2", refresh_token: "refresh-token-2" }));
    }
    return HttpResponse.json(
      makeErrorEnvelope({ code: "authentication_error", message: "Invalid or expired refresh token." }),
      { status: 401 },
    );
  }),

  http.post(`${BASE}/api/v1/auth/logout`, () => HttpResponse.json({ message: "Logged out." })),
  http.post(`${BASE}/api/v1/auth/logout-all`, () => HttpResponse.json({ message: "Logged out of all devices." })),

  http.get(`${BASE}/api/v1/auth/me`, ({ request }) => {
    const auth = request.headers.get("authorization");
    if (!auth || !auth.startsWith("Bearer ")) {
      return HttpResponse.json(
        makeErrorEnvelope({ code: "authentication_error", message: "Not authenticated." }),
        { status: 401 },
      );
    }
    return HttpResponse.json(makeMe());
  }),

  http.get(`${BASE}/api/v1/auth/sessions`, () => HttpResponse.json([makeSession()])),
  http.delete(`${BASE}/api/v1/auth/sessions/:sessionId`, () => HttpResponse.json({ message: "Session revoked." })),

  http.post(`${BASE}/api/v1/auth/password/change`, () => HttpResponse.json({ message: "Password changed." })),
  http.post(`${BASE}/api/v1/auth/password/reset/request`, () =>
    HttpResponse.json({ message: "If that email is registered, a reset link has been sent." }),
  ),
  http.post(`${BASE}/api/v1/auth/password/reset/confirm`, () => HttpResponse.json({ message: "Password reset." })),

  http.post(`${BASE}/api/v1/auth/verify-email/request`, () =>
    HttpResponse.json({ message: "Verification email sent." }),
  ),
  http.post(`${BASE}/api/v1/auth/verify-email/confirm`, () => HttpResponse.json({ message: "Email verified." })),
];
