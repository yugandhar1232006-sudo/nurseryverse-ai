import { expect, test, type APIRequestContext } from "@playwright/test";

/**
 * Real-backend authentication E2E, per the Phase 7B kickoff's explicit
 * instruction not to mock the authentication system for these tests.
 * Every request in this file goes to the actual FastAPI backend
 * (`NEXT_PUBLIC_API_BASE_URL`, default http://localhost:8000) through an
 * actual running Next.js app (`PLAYWRIGHT_BASE_URL`, see
 * playwright.config.ts) -- there is no MSW, no route stubbing, nothing
 * intercepted.
 *
 * WHY THIS FILE CANNOT RUN IN THIS SANDBOX (disclosed, not silently
 * skipped): this development environment has no `docker`/Postgres, so
 * there is no live backend to talk to -- confirmed via `/readyz` (503)
 * and a live login attempt (500, DNS resolution failure reaching the DB
 * host), identical to the constraint already documented for the backend's
 * own Module 14 work. This suite is written and reviewed for correctness
 * against the real, already-implemented `apps/api` routes (verified by
 * reading apps/api/app/services/auth_service.py and
 * apps/api/app/core/config.py directly -- see the lockout test's comment
 * for the exact threshold this asserts against), but has not been
 * execution-verified end-to-end here. See
 * docs/frontend/06-authentication.md's Testing section.
 *
 * Test isolation: rather than depend on a pre-seeded fixture account
 * (fragile -- couples this suite to whatever seed data happens to exist
 * in a given environment), `beforeAll` below signs up a fresh, uniquely
 * emailed user directly against the real `/api/v1/auth/signup` endpoint.
 * There's no UI for signup yet (out of 7B's scope -- login/reset/verify/
 * account only, per the kickoff), so this is done via Playwright's
 * `request` fixture rather than the browser.
 */

const PASSWORD = "Correct-horse-battery-1";
const WRONG_PASSWORD = "Wrong-password-1";

function uniqueEmail(): string {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpUser(request: APIRequestContext, apiBaseUrl: string, email: string) {
  const res = await request.post(`${apiBaseUrl}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "E2E Test User" },
  });
  if (!res.ok()) {
    throw new Error(`Signup fixture failed (${res.status()}): ${await res.text()}`);
  }
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

test.describe("Authentication (real backend)", () => {
  test("successful login reaches the app and shows the signed-in header", async ({ page, request }) => {
    const email = uniqueEmail();
    await signUpUser(request, API_BASE_URL, email);

    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL("/");
    // As of 7C's AppShell, the persistent header no longer carries a
    // static "NurseryVerse AI" wordmark (org context is real API data,
    // not a hardcoded string) -- assert against shell chrome that's
    // always present instead: the primary nav landmark and the user
    // menu trigger (Sign out lives inside that menu now, not inline).
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    await expect(page.getByRole("button", { name: /Account menu/ })).toBeVisible();
  });

  test("wrong password shows an invalid-credentials error and does not sign in", async ({ page, request }) => {
    const email = uniqueEmail();
    await signUpUser(request, API_BASE_URL, email);

    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(WRONG_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page.getByText("Sign-in failed")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("visiting a protected route while signed out redirects to /login and preserves the destination", async ({
    page,
  }) => {
    await page.goto("/account");
    await expect(page).toHaveURL(/\/login\?next=%2Faccount/);
  });

  test("logging in from a protected-route redirect returns to the original destination", async ({
    page,
    request,
  }) => {
    const email = uniqueEmail();
    await signUpUser(request, API_BASE_URL, email);

    await page.goto("/account");
    await expect(page).toHaveURL(/\/login\?next=%2Faccount/);

    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL("/account");
    // Exact match: without it, `getByText("Your account")` also matches the
    // verify-email banner ("Please verify your email address to secure your
    // account…") and the card description, tripping strict mode.
    await expect(page.getByText("Your account", { exact: true })).toBeVisible();
  });

  test("signing out clears the session and protected routes require signing in again", async ({ page, request }) => {
    const email = uniqueEmail();
    await signUpUser(request, API_BASE_URL, email);

    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL("/");

    // Sign out lives inside the user menu dropdown (7C's UserMenu), not
    // as an inline header button as it was in 7B's minimal AppHeader.
    await page.getByRole("button", { name: /Account menu/ }).click();
    await page.getByRole("menuitem", { name: /Sign out/ }).click();
    await expect(page).toHaveURL(/\/login/);

    await page.goto("/account");
    await expect(page).toHaveURL(/\/login\?next=%2Faccount/);
  });

  test("account locks out after repeated failed attempts (AUTH_MAX_FAILED_LOGIN_ATTEMPTS=5)", async ({
    page,
    request,
  }) => {
    // Mirrors apps/api/app/core/config.py's AUTH_MAX_FAILED_LOGIN_ATTEMPTS
    // and apps/api/app/services/auth_service.py's `_register_failed_attempt`:
    // the *5th* wrong attempt is the one that sets `locked_until`, but it
    // still returns the generic wrong-password error itself (the lock
    // isn't checked until the *next* login attempt, which is what
    // actually surfaces the "temporarily locked" message). So this
    // submits 5 wrong attempts, then a 6th to observe the lockout state.
    const email = uniqueEmail();
    await signUpUser(request, API_BASE_URL, email);

    await page.goto("/login");
    for (let attempt = 0; attempt < 5; attempt += 1) {
      await page.getByLabel("Email").fill(email);
      await page.getByLabel("Password").fill(WRONG_PASSWORD);
      await page.getByRole("button", { name: "Sign in" }).click();
      await expect(page.getByText("Sign-in failed")).toBeVisible();
    }

    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(WRONG_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();

    // Real backend copy: "Account is temporarily locked due to repeated
    // failed login attempts. Try again later or reset your password."
    // Both the alert title and description match /temporarily locked/i, so
    // scope to the exact title to keep the locator strict-mode-clean.
    await expect(page.getByText("Account temporarily locked")).toBeVisible();

    // Confirms the lockout is real (server-enforced), not just a
    // client-side message: even the *correct* password is rejected while
    // locked.
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByText("Account temporarily locked")).toBeVisible();
  });

  test("the password-reset-request page always shows the same success message (anti-enumeration)", async ({
    page,
  }) => {
    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill("definitely-not-a-real-account@example.com");
    await page.getByRole("button", { name: "Send reset link" }).click();

    await expect(page.getByText("Reset link sent")).toBeVisible();
  });

  test("visiting /reset-password without a token shows an invalid-link state, not a crash", async ({ page }) => {
    await page.goto("/reset-password");
    await expect(page.getByText("Invalid reset link")).toBeVisible();
  });

  test("visiting /verify-email with a bogus token shows a failure state, not a crash", async ({ page }) => {
    await page.goto("/verify-email?token=not-a-real-token");
    await expect(page.getByText("Verification failed")).toBeVisible();
  });
});
