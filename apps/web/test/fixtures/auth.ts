import type { MeResponse, SessionResponse, TokenPairResponse } from "@/lib/api/auth";

/**
 * Shared fixtures for auth tests -- kept in one place so a schema change
 * (e.g. a new `MeResponse` field) only needs updating here, not in every
 * test file that builds one of these DTOs by hand.
 */
export function makeTokenPair(overrides: Partial<TokenPairResponse> = {}): TokenPairResponse {
  return {
    access_token: "access-token-1",
    refresh_token: "refresh-token-1",
    token_type: "bearer",
    expires_in: 900,
    ...overrides,
  };
}

export function makeMe(overrides: Partial<MeResponse> = {}): MeResponse {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    email: "jane@example.com",
    full_name: "Jane Grower",
    is_email_verified: true,
    org_id: "22222222-2222-2222-2222-222222222222",
    role: "owner",
    permissions: ["plants:read", "plants:write"],
    ...overrides,
  };
}

export function makeSession(overrides: Partial<SessionResponse> = {}): SessionResponse {
  return {
    id: "33333333-3333-3333-3333-333333333333",
    device_name: "Chrome on macOS",
    ip_address: "127.0.0.1",
    issued_at: "2026-08-01T00:00:00Z",
    last_used_at: "2026-08-10T00:00:00Z",
    expires_at: "2026-09-01T00:00:00Z",
    // The real backend route never actually populates this (see
    // docs/frontend/06-authentication.md's Known Limitations) -- `false`
    // is what it always comes back as in practice, not just a schema
    // default.
    is_current: false,
    ...overrides,
  };
}

/** The real backend error envelope shape (apps/api/app/core/responses.py). */
export function makeErrorEnvelope(params: {
  code: string;
  message: string;
  context?: Record<string, unknown>;
  requestId?: string | null;
}) {
  return {
    error: { code: params.code, message: params.message, context: params.context ?? {} },
    request_id: params.requestId ?? "req-test-1",
  };
}
