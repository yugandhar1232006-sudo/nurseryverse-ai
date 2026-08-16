import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_MARKER_COOKIE } from "@/lib/auth/session-marker";

/**
 * Next.js 16 renamed the `middleware.ts` file convention to `proxy.ts`
 * (same mechanism, new name/export -- see
 * https://nextjs.org/docs/app/api-reference/file-conventions/proxy).
 * This project targets Next.js 16 from the start, so it uses the
 * current convention rather than the deprecated one.
 *
 * Defense-in-depth only, never the actual security boundary (that's the
 * backend's AuthorizationService/PermissionService -- see
 * docs/frontend/05-permission-aware-ui.md). The real, authoritative
 * client-side gate is app/(app)/layout.tsx, which reads the actual
 * in-memory session state this proxy cannot see.
 *
 * Why this can't do more: Next.js's edge proxy runs on the server,
 * before any client JS, and only has access to the incoming request's
 * cookies/headers. In the backend's default bearer-token mode (see
 * store/session-store.ts's docstring), authentication involves *no*
 * cookie at all -- tokens live only in browser JS memory. So this proxy
 * has no reliable way to distinguish "definitely signed out" from
 * "signed in via bearer tokens the server can't see." Redirecting based
 * on the absence of the real `nv_refresh_token` cookie (which only
 * exists in cookie-mode deployments) would incorrectly block every
 * authenticated bearer-mode user -- unacceptable given bearer mode is
 * the backend's actual current default.
 *
 * The fix used here: `lib/auth/session-marker.ts`'s non-sensitive
 * `nv_has_session` cookie, set/cleared by client-side auth state changes
 * regardless of which backend mode is active. It carries no secret and
 * is never sent to or read by the backend -- purely a same-origin hint
 * for this proxy.
 *
 * `PROTECTED_PREFIXES` is a deliberate allowlist, not "protect
 * everything except an allowlist of public paths." Under-protecting a
 * route here is low-stakes (the client-side guard and the backend both
 * still enforce it); over-protecting is not -- accidentally gating a
 * route that must stay public (the Plant Passport, 7K) would be a real
 * defect. Extend this list as each phase adds protected routes.
 */
const PROTECTED_PREFIXES = ["/account"];

const AUTH_ONLY_PAGES = ["/login"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSessionMarker = request.cookies.has(SESSION_MARKER_COOKIE);

  const isProtected = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  if (isProtected && !hasSessionMarker) {
    const loginUrl = new URL("/login", request.url);
    // Preserved so the login form can redirect back to where the user
    // was headed instead of dumping them on a generic landing page.
    loginUrl.searchParams.set("next", pathname + request.nextUrl.search);
    return NextResponse.redirect(loginUrl);
  }

  const isAuthOnlyPage = AUTH_ONLY_PAGES.some((page) => pathname === page);
  if (isAuthOnlyPage && hasSessionMarker) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Skip static assets, images, and Next internals -- matching those
     * needlessly runs this on every asset request for no benefit.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|webp|woff2?)$).*)",
  ],
};
