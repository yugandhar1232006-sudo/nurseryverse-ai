import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for the 7C Application Shell -- same "no mocking, real
 * `apps/api`, real Postgres" approach as e2e/auth.spec.ts, and the same
 * disclosed constraint: this sandbox has no `docker`/Postgres (confirmed
 * via a live `/readyz` check and a bare TCP probe of :8000/:3000, both
 * unreachable), so this suite is written and reviewed for correctness
 * against the real, already-implemented shell components, but has not
 * been execution-verified end-to-end here. See
 * docs/frontend/07-application-shell.md's Testing section.
 *
 * Test account scope: `POST /auth/signup` (Module 2) creates a bare user
 * account only -- there is no signup-time org creation, and no UI for
 * `POST /orgs` yet (that's Phase 7E). A freshly signed-up e2e user
 * therefore has `org_id: null` and `permissions: []`, same as any real
 * new NurseryVerse account before onboarding. This is not a limitation of
 * this test suite to route around -- it is the real, correctly-handled
 * "no org yet" state every shell component (`OrgContext`, `BranchSelector`,
 * every permission-gated nav item and page) is specifically built to
 * degrade to, and this suite verifies exactly that degradation rather
 * than faking an org into existence to get a "nicer" test.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(): string {
  return `e2e-shell-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpAndLogIn(page: Page, request: APIRequestContext): Promise<string> {
  const email = uniqueEmail();
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Shell E2E User" },
  });
  if (!res.ok()) {
    throw new Error(`Signup fixture failed (${res.status()}): ${await res.text()}`);
  }

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/");

  return email;
}

/**
 * The notification bell/Alerts tab are gated by `notifications:read`
 * (see components/layout/top-nav.tsx) -- a bare signup has no role and
 * therefore no bell at all. The notification-center tests need a user
 * who genuinely holds that permission, so they create an organization
 * first (which makes the signing-up user its Owner, granting
 * `notifications:read` per docs/ux/07-role-permission-matrix.md).
 */
async function signUpLogInAndCreateOrg(page: Page, request: APIRequestContext): Promise<string> {
  const email = await signUpAndLogIn(page, request);

  await page.goto("/settings");
  await page.getByLabel("Organization name").fill(`${email.split("@")[0]} Nursery`);
  await page.getByLabel("Contact email").fill(`contact-${Date.now()}@example.com`);
  await page.getByRole("button", { name: "Create organization" }).click();
  await expect(page.getByRole("tab", { name: "Branches" })).toBeVisible();

  return email;
}

test.describe("Application Shell (real backend)", () => {
  test("login lands on the real Dashboard route inside the full shell", async ({ page, request }) => {
    await signUpAndLogIn(page, request);

    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();
    // A brand-new, org-less account: only the two ungated destinations
    // (Dashboard, Settings) are real for this user -- every permission-
    // gated item is correctly absent, not disabled.
    await expect(page.getByRole("link", { name: "Settings" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Plants" })).toHaveCount(0);
  });

  test("sidebar navigation updates the URL and marks the active route", async ({ page, request }) => {
    await signUpAndLogIn(page, request);

    await page.getByRole("link", { name: "Settings" }).click();
    await expect(page).toHaveURL("/settings");
    await expect(page.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
  });

  test("breadcrumbs render the real route trail on a non-root page and are absent on the Dashboard", async ({
    page,
    request,
  }) => {
    await signUpAndLogIn(page, request);
    await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toHaveCount(0);

    await page.getByRole("link", { name: "Settings" }).click();
    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(breadcrumb).toBeVisible();
    await expect(breadcrumb.getByText("Settings")).toBeVisible();
  });

  test("navigating directly by URL to a permission-gated page shows Permission denied, not a blank screen or a crash", async ({
    page,
    request,
  }) => {
    await signUpAndLogIn(page, request);

    await page.goto("/plants");
    await expect(page.getByText("You don't have access to this page")).toBeVisible();
  });

  test("organization context and branch selector correctly show nothing for an org-less account (not a broken picker)", async ({
    page,
    request,
  }) => {
    await signUpAndLogIn(page, request);

    await expect(page.getByRole("combobox", { name: "Select branch" })).toHaveCount(0);
  });

  test("the notification center opens from the header bell and shows a real empty state for a fresh org Owner", async ({
    page,
    request,
  }) => {
    // A bare signup has no role and therefore no bell (notifications:read
    // is gated) -- create an org to become an Owner who legitimately has
    // the permission, then the empty state is the real one.
    await signUpLogInAndCreateOrg(page, request);

    await page.getByRole("button", { name: /Notifications/ }).click();
    await expect(page.getByText("No notifications yet")).toBeVisible();
  });

  test("global search opens via the header button and via Ctrl+K, and respects zero search permissions", async ({
    page,
    request,
  }) => {
    await signUpAndLogIn(page, request);

    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByText("Nothing to search yet")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByText("Nothing to search yet")).toBeHidden();

    await page.keyboard.press("Control+k");
    await expect(page.getByPlaceholder(/Search plants/)).toBeVisible();
  });

  test("signing out from the user menu clears the session and protected routes redirect to /login again", async ({
    page,
    request,
  }) => {
    await signUpAndLogIn(page, request);

    await page.getByRole("button", { name: /Account menu/ }).click();
    await page.getByRole("menuitem", { name: /Sign out/ }).click();
    await expect(page).toHaveURL(/\/login/);

    await page.goto("/settings");
    await expect(page).toHaveURL(/\/login\?next=%2Fsettings/);
  });

  test.describe("mobile viewport", () => {
    test.use({ viewport: { width: 390, height: 844 } });

    test.beforeEach(async ({ page }) => {
      // Hide the TanStack Query DevTools overlay that intercepts pointer
      // events on mobile viewports.  addInitScript runs before any page
      // scripts, so the rule is in effect from the very first navigation.
      await page.addInitScript(() => {
        const style = document.createElement("style");
        style.textContent = ".tsqd-parent-container { display: none !important; }";
        document.addEventListener("DOMContentLoaded", () => document.head.appendChild(style));
      });
    });

    test("shows the bottom tab bar instead of the desktop sidebar, and the More sheet reaches the rest of nav", async ({
      page,
      request,
    }) => {
      await signUpAndLogIn(page, request);

      await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible();

      await page.getByRole("button", { name: "Open navigation menu" }).click();
      await expect(page.getByRole("navigation", { name: "More navigation" })).toBeVisible();
      await page.getByRole("navigation", { name: "More navigation" }).getByRole("link", { name: "Settings" }).click();
      await expect(page).toHaveURL("/settings");
    });

    test("the Alerts tab opens the same notification panel as the desktop bell", async ({ page, request }) => {
      await signUpLogInAndCreateOrg(page, request);

      // Scope to the mobile tab bar: on a phone viewport the desktop
      // header bell is also present in the DOM (CSS-hidden), so the bare
      // `getByRole("button", { name: "Notifications" })` matches both and
      // trips strict mode.
      await page.getByRole("navigation", { name: "Primary" }).getByRole("button", { name: "Notifications" }).click();
      await expect(page.getByText("No notifications yet")).toBeVisible();
    });
  });
});
