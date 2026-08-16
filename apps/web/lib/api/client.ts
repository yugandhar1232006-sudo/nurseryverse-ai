import createClient, { type Middleware } from "openapi-fetch";

import { API_BASE_URL, CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from "@/lib/api/config";
import { apiErrorFromNetworkFailure, apiErrorFromResponseBody, ApiError, isApiError } from "@/lib/api/error";
import type { paths } from "@/lib/api/generated/schema";
import { sessionStore } from "@/store/session-store";

/**
 * Every generated operation ID this client exposes is real -- it comes
 * straight from apps/api's live OpenAPI schema (see
 * lib/api/generated/schema.d.ts's header and package.json's
 * `generate:api-types` script). There is no hand-maintained type here
 * that can drift from the backend.
 */
export const apiClient = createClient<paths>({
  baseUrl: API_BASE_URL,
  credentials: "include", // harmless in bearer mode; required for cookie-mode refresh/CSRF cookies
  // openapi-fetch's own default (`fetch = globalThis.fetch`) is evaluated
  // once, here, at module-load time -- it captures whichever `fetch`
  // function happens to be the global at that instant and closes over it
  // forever. In production that's harmless (nothing repatches
  // `globalThis.fetch` after boot), but it's a real bug under Vitest:
  // MSW's `server.listen()` (test/setup.ts) patches `globalThis.fetch`
  // in a `beforeAll` hook, which runs *after* this module has already
  // been imported and already captured the pre-patch, real network
  // `fetch`. Every request would then silently bypass MSW and hit a
  // real (nonexistent, in-sandbox) backend. Passing a thin pass-through
  // instead makes every call do a fresh `globalThis.fetch` lookup at
  // request time, so it always sees whatever is currently installed --
  // MSW's interceptor in tests, the real fetch in the browser.
  fetch: (input) => globalThis.fetch(input),
});

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Attaches the in-memory access token and (cookie-mode only) the
 * double-submit CSRF header to every outgoing request. Does not attempt
 * retry-on-401 here -- see `refreshAccessToken`/`withAuthRetry` below for
 * why that has to live at the call-wrapper level instead of in fetch
 * middleware.
 */
const authRequestMiddleware: Middleware = {
  async onRequest({ request }) {
    const { accessToken } = sessionStore.getState();
    if (accessToken) {
      request.headers.set("Authorization", `Bearer ${accessToken}`);
    }
    const csrf = readCookie(CSRF_COOKIE_NAME);
    if (csrf) {
      request.headers.set(CSRF_HEADER_NAME, csrf);
    }
    return request;
  },
};

apiClient.use(authRequestMiddleware);

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Rotates the refresh token via POST /api/v1/auth/refresh. Deliberately
 * uses a bare `fetch`, not `apiClient`, so this call never re-enters
 * `authRequestMiddleware`/`withAuthRetry` and can't recurse. Concurrent
 * callers share one in-flight refresh via `refreshInFlight` so a burst of
 * simultaneous 401s doesn't rotate the token multiple times (each
 * rotation invalidates the previous one -- see auth.py's replay-family
 * revocation).
 */
async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const { refreshToken } = sessionStore.getState();
    const csrf = readCookie(CSRF_COOKIE_NAME);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(csrf ? { [CSRF_HEADER_NAME]: csrf } : {}),
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) return false;

      const body = (await res.json()) as {
        access_token: string;
        refresh_token: string;
        expires_in: number;
      };
      sessionStore.getState().setSession({
        accessToken: body.access_token,
        refreshToken: body.refresh_token,
        expiresIn: body.expires_in,
      });
      return true;
    } catch {
      return false;
    }
  })();

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

/**
 * Wraps a single openapi-fetch call with the app's standard auth-retry
 * behavior: on a 401, attempt exactly one silent refresh and re-issue the
 * *same* call once (the caller passes a thunk so the request is rebuilt
 * from scratch rather than replaying a possibly-already-consumed
 * Request/body -- openapi-fetch's own middleware can mutate headers
 * in-place safely, per `authRequestMiddleware` above, but retrying a
 * request with a body from inside response middleware is not safe in
 * the general case, hence doing it here instead). A second 401 (refresh
 * failed, or the retried call 401s again) clears the session and
 * surfaces the error -- route guards/`useSession` react to `status`
 * flipping to "unauthenticated" and redirect to sign-in.
 */
async function withAuthRetry<T>(call: () => Promise<FetchResult<T>>): Promise<FetchResult<T>> {
  const first = await call();
  if (first.response.status !== 401) return first;

  const refreshed = await refreshAccessToken();
  if (!refreshed) {
    sessionStore.getState().clearSession();
    return first;
  }

  const second = await call();
  if (second.response.status === 401) {
    sessionStore.getState().clearSession();
  }
  return second;
}

/**
 * Every feature module (lib/api/auth.ts, lib/api/plants.ts, etc.) should
 * call through this rather than `apiClient` directly: it adds the
 * refresh-and-retry behavior and normalizes every non-2xx response into
 * a thrown `ApiError`, so calling code (React Query hooks) only ever
 * deals with `T` on success or a caught `ApiError` on failure -- never a
 * raw `{data, error}` union or a bare fetch Response.
 */
export async function unwrap<T>(call: () => Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await withAuthRetry(call);
  } catch (cause) {
    // `call()` rejected before any response existed -- offline, DNS
    // failure, connection refused (backend process down), CORS
    // preflight failure, etc. Neither `withAuthRetry` nor `openapi-fetch`
    // itself can produce a `{data, error, response}` result for this
    // (there is no Response), so it surfaces as a thrown error instead.
    // Normalized here into the same ApiError shape as every other
    // failure path so calling code has exactly one error type to handle
    // -- this is what backs the "Network failure"/"Server unavailable"
    // UI states.
    if (isApiError(cause)) throw cause; // already normalized somewhere upstream
    throw apiErrorFromNetworkFailure(cause);
  }

  if (!result.response.ok) {
    throw apiErrorFromResponseBody(result.response.status, result.error);
  }
  if (result.data === undefined) {
    // 204 No Content and similar -- not an error, just nothing to return.
    return undefined as T;
  }
  return result.data;
}

/**
 * Same response normalization as `unwrap()`, but deliberately *without*
 * the 401-retry behavior. `POST /auth/refresh` itself is the only call
 * this should be used for: retrying a failed token refresh by attempting
 * *another* token refresh is nonsensical (there's nothing left to
 * refresh with once the refresh token itself has been rejected), and
 * routing it through `withAuthRetry` would fire a second, redundant
 * `refreshAccessToken()` call on top of whatever call site is already
 * doing the refreshing -- doubling load and presenting an already-
 * revoked token to the backend's replay-family-revocation logic twice
 * instead of once. `lib/api/auth.ts`'s exported `refresh()` uses this.
 */
export async function unwrapOnce<T>(call: () => Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await call();
  } catch (cause) {
    if (isApiError(cause)) throw cause;
    throw apiErrorFromNetworkFailure(cause);
  }

  if (!result.response.ok) {
    throw apiErrorFromResponseBody(result.response.status, result.error);
  }
  if (result.data === undefined) {
    return undefined as T;
  }
  return result.data;
}

export { ApiError };
