/**
 * The one place that knows the real backend's origin. Every other module
 * imports API_BASE_URL from here rather than reading the env var directly,
 * so there is exactly one thing to change to point the whole app at a
 * different backend (staging, a teammate's local port, etc.).
 */
export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ?? "http://localhost:8000";

/** Cookie/header names, mirrored from apps/api/app/api/routes/auth.py -- must stay in sync. */
export const CSRF_COOKIE_NAME = "nv_csrf_token";
export const CSRF_HEADER_NAME = "x-csrf-token";
