import { apiClient, unwrap, unwrapOnce } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin, typed wrappers around the real `/api/v1/auth/*` routes
 * (apps/api/app/api/routes/auth.py) -- this is the *only* authentication
 * implementation in the frontend. There is no separate mock/local auth
 * path; every function here calls the live backend through `unwrap()`
 * (lib/api/client.ts), which already adds the auth header, the
 * 401-refresh-and-retry behavior, and normalizes errors to `ApiError`.
 *
 * These functions return the raw backend DTOs -- session-state side
 * effects (writing into `useSessionStore`) belong to the callers in
 * `lib/auth/` (session-boot, login mutation, etc.), not here, so this
 * module stays a pure API binding that's trivial to unit test with a
 * mocked `apiClient`.
 */

export type TokenPairResponse = components["schemas"]["TokenPairResponse"];
export type MeResponse = components["schemas"]["MeResponse"];
// openapi-typescript disambiguates the two backend `SessionResponse`
// schemas (Module 2 Auth's device-session model vs. Module 13 Admin's
// unrelated one) by module path -- this is the auth one.
export type SessionResponse = components["schemas"]["app__schemas__auth__SessionResponse"];
export type MessageResponse = components["schemas"]["MessageResponse"];

export interface LoginInput {
  email: string;
  password: string;
  device_name?: string | null;
}

/**
 * Uses `unwrapOnce`, not `unwrap`: login is an *unauthenticated* endpoint,
 * so a 401 from it means "wrong credentials" (or a locked/inactive
 * account -- see lib/auth/login-error.ts), never "this access token
 * expired, try refreshing." Routing it through `unwrap`'s normal
 * refresh-and-retry behavior would silently fire a pointless
 * `/auth/refresh` call on every failed login attempt (using whatever
 * stale/absent refresh token happens to be sitting in memory) and, on
 * that refresh's inevitable failure, call `clearSession()` as a side
 * effect of a login page action that was never authenticated to begin
 * with. The user-visible error message is identical either way (the
 * original login response's 401 body is what's ultimately thrown), so
 * this was only ever a wasted round-trip plus a confusing side effect,
 * not a user-facing bug -- but there's no reason to keep it.
 */
export async function login(input: LoginInput): Promise<TokenPairResponse> {
  return unwrapOnce(() => apiClient.POST("/api/v1/auth/login", { body: input }));
}

export interface SignupInput {
  email: string;
  password: string;
  full_name: string;
  device_name?: string | null;
}

/** Same reasoning as `login` above -- signup is unauthenticated too. */
export async function signup(input: SignupInput): Promise<TokenPairResponse> {
  return unwrapOnce(() => apiClient.POST("/api/v1/auth/signup", { body: input }));
}

/**
 * Uses `unwrapOnce` (not `unwrap`) deliberately: retrying a failed
 * refresh by triggering *another* refresh is nonsensical and would
 * double up with `lib/api/client.ts`'s own internal
 * `refreshAccessToken()` (used by the 401 interceptor) if this ever
 * 401s. This exported version is for explicit call sites -- session-boot
 * restoration -- that want a typed result without going through the
 * interceptor's bare-fetch path.
 */
export async function refresh(refreshToken: string | null): Promise<TokenPairResponse> {
  return unwrapOnce(() => apiClient.POST("/api/v1/auth/refresh", { body: { refresh_token: refreshToken } }));
}

export async function logout(refreshToken: string | null): Promise<MessageResponse> {
  return unwrap(() => apiClient.POST("/api/v1/auth/logout", { body: { refresh_token: refreshToken } }));
}

export async function logoutAll(): Promise<MessageResponse> {
  return unwrap(() => apiClient.POST("/api/v1/auth/logout-all", {}));
}

export async function getMe(): Promise<MeResponse> {
  return unwrap(() => apiClient.GET("/api/v1/auth/me", {}));
}

export async function listSessions(): Promise<SessionResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/auth/sessions", {}));
}

export async function revokeSession(sessionId: string): Promise<MessageResponse> {
  return unwrap(() =>
    apiClient.DELETE("/api/v1/auth/sessions/{session_id}", { params: { path: { session_id: sessionId } } }),
  );
}

export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

export async function changePassword(input: ChangePasswordInput): Promise<MessageResponse> {
  return unwrap(() => apiClient.POST("/api/v1/auth/password/change", { body: input }));
}

export async function requestPasswordReset(email: string): Promise<MessageResponse> {
  return unwrap(() => apiClient.POST("/api/v1/auth/password/reset/request", { body: { email } }));
}

export async function confirmPasswordReset(token: string, newPassword: string): Promise<MessageResponse> {
  return unwrap(() =>
    apiClient.POST("/api/v1/auth/password/reset/confirm", { body: { token, new_password: newPassword } }),
  );
}

export async function requestEmailVerification(): Promise<MessageResponse> {
  return unwrap(() => apiClient.POST("/api/v1/auth/verify-email/request", {}));
}

export async function confirmEmailVerification(token: string): Promise<MessageResponse> {
  return unwrap(() => apiClient.POST("/api/v1/auth/verify-email/confirm", { body: { token } }));
}
