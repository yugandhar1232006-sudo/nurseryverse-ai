/**
 * Normalized error thrown by the API client for every non-2xx response
 * from the real backend. Every route in the system returns the single
 * envelope defined in apps/api/app/core/responses.py and registered in
 * apps/api/app/core/error_handlers.py:
 *
 *   { "error": { "code": string, "message": string, "context": object },
 *     "request_id": string | null }
 *
 * For 422s specifically, `context.errors` holds FastAPI/Pydantic's own
 * RequestValidationError.errors() array: { loc: (string|number)[], msg,
 * type }[]. ApiError.fieldErrors flattens that into `field -> messages[]`
 * (dropping the leading "body"/"query"/"path" segment of `loc`) so RHF's
 * `setError` can consume it directly without every call site re-parsing
 * `loc` itself.
 */
export interface RawFastApiValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly context: Record<string, unknown>;
  readonly requestId: string | null;
  /** Present only for 422 validation errors; keyed by field path (e.g. "email"). */
  readonly fieldErrors?: Record<string, string[]>;

  constructor(params: {
    status: number;
    code: string;
    message: string;
    context?: Record<string, unknown>;
    requestId?: string | null;
    fieldErrors?: Record<string, string[]>;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.status = params.status;
    this.code = params.code;
    this.context = params.context ?? {};
    this.requestId = params.requestId ?? null;
    this.fieldErrors = params.fieldErrors;
  }
}

function flattenFieldErrors(rawErrors: RawFastApiValidationError[]): Record<string, string[]> {
  const out: Record<string, string[]> = {};
  for (const err of rawErrors) {
    // Drop the leading location segment ("body" | "query" | "path" | "header").
    const field = err.loc.slice(1).join(".") || err.loc.join(".");
    (out[field] ??= []).push(err.msg);
  }
  return out;
}

/**
 * Builds an ApiError from a parsed JSON response body per the envelope
 * above. Falls back gracefully if the body doesn't match (e.g. an
 * upstream proxy/edge error that never reached the FastAPI handlers).
 */
export function apiErrorFromResponseBody(status: number, body: unknown): ApiError {
  if (body && typeof body === "object" && "error" in body) {
    const envelope = body as { error?: { code?: string; message?: string; context?: Record<string, unknown> }; request_id?: string | null };
    const code = envelope.error?.code ?? "unknown_error";
    const message = envelope.error?.message ?? messageForStatus(status);
    const context = envelope.error?.context ?? {};
    const rawErrors = context.errors as RawFastApiValidationError[] | undefined;
    return new ApiError({
      status,
      code,
      message,
      context,
      requestId: envelope.request_id ?? null,
      fieldErrors: Array.isArray(rawErrors) ? flattenFieldErrors(rawErrors) : undefined,
    });
  }
  return new ApiError({ status, code: "unknown_error", message: messageForStatus(status) });
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

/**
 * Status `0` is this module's own convention for "no response at all" --
 * not a real HTTP status, used when `fetch` itself rejects (offline, DNS
 * failure, connection refused because the backend process is down,
 * CORS preflight failure, etc.). Every other status in this table is a
 * real response the backend sent.
 */
export const NETWORK_ERROR_STATUS = 0;

/** User-facing fallback copy per HTTP status, used when the backend didn't supply a message. */
export const DEFAULT_ERROR_MESSAGES: Record<number, string> = {
  [NETWORK_ERROR_STATUS]: "Unable to reach the server. Check your connection and try again.",
  400: "That request wasn't valid. Please check the form and try again.",
  401: "Your session has expired. Please sign in again.",
  403: "You don't have permission to do that.",
  404: "We couldn't find what you were looking for.",
  409: "That conflicts with existing data. Please refresh and try again.",
  422: "Some fields need to be corrected.",
  429: "You're doing that too often. Please wait a moment and try again.",
  500: "Something went wrong on our end. Please try again.",
  503: "The service is temporarily unavailable. Please try again shortly.",
};

export function messageForStatus(status: number): string {
  return DEFAULT_ERROR_MESSAGES[status] ?? "An unexpected error occurred.";
}

/**
 * Wraps a thrown network-level failure (fetch rejecting before any
 * response was received) into the same `ApiError` shape every other
 * error path produces, so calling code never has to special-case "was
 * this a backend error or did the request not even complete." See
 * lib/api/client.ts's `unwrap()`, which is the only place this should
 * be called from.
 */
export function apiErrorFromNetworkFailure(cause: unknown): ApiError {
  return new ApiError({
    status: NETWORK_ERROR_STATUS,
    code: "network_error",
    message: messageForStatus(NETWORK_ERROR_STATUS),
    context: { cause: cause instanceof Error ? cause.message : String(cause) },
  });
}
