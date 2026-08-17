import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for the 7D Dashboards module -- same "no mocking,
 * real apps/api, real Postgres" approach and the same disclosed
 * constraint as e2e/auth.spec.ts and e2e/shell.spec.ts: this sandbox has
 * no docker/Postgres, so this suite is written and reviewed for
 * correctness against the real, already-implemented dashboard
 * components and the real Module 12 reporting routes, but has not been
 * execution-verified end-to-end here. See docs/frontend/08-dashboards.md's
 * Testing section.
 *
 * Test account scope: a freshly signed-up user has no org
 * (`POST /auth/signup` doesn't create one) and therefore no
 * `reports:read` permission -- this suite verifies the honest
 * `NoReportingAccess` degradation for that real state, matching
 * e2e/shell.spec.ts's own precedent for why this isn't routed around
 * with a fake org. Full dashboard-content assertions (KPI figures,
 * branch scoping) would additionally require a seeded org+branch+role
 * fixture this sandbox cannot provision either; those paths are covered
 * by the Vitest/RTL suite (components/dashboards/__tests__/dashboard-page.test.tsx)
 * against real component code with MSW-mocked network responses instead.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(): string {
  return `e2e-dash-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpAndLogIn(page: Page, request: APIRequestContext): Promise<string> {
  const email = uniqueEmail();
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Dashboard E2E User" },
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

test.describe("Dashboards (real backend)", () => {
  test("an org-less account lands on / and sees the honest no-reporting-access state, not fabricated widgets", async ({
    page,
    request,
  }) => {
    await signUpAndLogIn(page, request);

    // A brand-new signup has `org_id: null` -- no role, so no `reports:read`
    // (see components/dashboards/no-reporting-access.tsx: `NoReportingAccess`
    // deliberately branches on `orgId === null` and points the user at the
    // real fix, Settings -> create an organization, instead of the generic
    // "Reporting is not part of your role" copy that only applies once they
    // belong to an org).
    await expect(page.getByText(/not part of an organization yet/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Set up your organization" })).toBeVisible();
    // No dashboard tabs render for a user with no reports:read permission --
    // there is nothing behind them to show.
    await expect(page.getByRole("tab", { name: "Executive" })).toHaveCount(0);
  });

  test("the dashboard route requires authentication like every other protected page", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });
});
