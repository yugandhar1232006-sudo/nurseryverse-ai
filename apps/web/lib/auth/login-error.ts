import { isApiError } from "@/lib/api/error";

export type LoginErrorKind =
  | "invalid_credentials"
  | "account_locked"
  | "rate_limited"
  | "network"
  | "server"
  | "unknown";

/**
 * The backend (apps/api/app/services/auth_service.py's `login()`) raises
 * the *same* `AuthenticationError` (401, `error_code: "authentication_error"`)
 * for wrong password, unknown email, a deactivated account, and a locked
 * account -- deliberately: returning a different error *code* for
 * "locked" vs. "wrong password" would let an attacker distinguish
 * "this account exists and is locked" from "this account doesn't exist,"
 * a user-enumeration signal the backend is explicit about avoiding
 * elsewhere too (see `request_password_reset`'s identical-response
 * behavior). The lockout message text ("Account is temporarily locked...")
 * is the only signal available to show a different UI state for it, so
 * that's what this checks -- confirmed unique among every other auth
 * error message in the service, not a fragile guess. If the backend ever
 * changes that copy, this needs updating alongside it (documented in
 * docs/frontend/06-authentication.md's Known Limitations).
 */
export function classifyLoginError(error: unknown): { kind: LoginErrorKind; message: string } {
  if (isApiError(error)) {
    if (error.status === 0) {
      return { kind: "network", message: error.message };
    }
    if (error.status === 429) {
      return { kind: "rate_limited", message: error.message };
    }
    if (error.status === 401) {
      if (/locked/i.test(error.message)) {
        return { kind: "account_locked", message: error.message };
      }
      return { kind: "invalid_credentials", message: error.message };
    }
    if (error.status >= 500) {
      return { kind: "server", message: error.message };
    }
    return { kind: "unknown", message: error.message };
  }
  return { kind: "unknown", message: "Something went wrong. Please try again." };
}
