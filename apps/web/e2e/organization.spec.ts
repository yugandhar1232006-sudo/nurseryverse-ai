import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for the 7E Organization Management module -- same "no
 * mocking, real apps/api, real Postgres" approach as e2e/auth.spec.ts,
 * e2e/shell.spec.ts, and e2e/dashboards.spec.ts, and the same disclosed
 * constraint: this sandbox has no docker/Postgres, so this suite is
 * written and reviewed for correctness against the real, already-
 * implemented 7E components and the real Module 4/13 routes, but has not
 * been execution-verified end-to-end here. See
 * docs/frontend/09-organization-management.md's Testing section.
 *
 * The onboarding create-org path is the one 7E flow a fresh signup can
 * genuinely drive against a real backend with zero seed data -- every
 * other 7E screen (Branches CRUD, Employees invite/transfer/deactivate)
 * requires an existing org+Owner role, which is exactly what this first
 * test creates for real, then the rest of the suite builds on. Branch/
 * Employee CRUD against real component code is additionally covered by
 * the Vitest/RTL suite (components/organization/__tests__/organization.test.tsx)
 * with MSW-mocked network responses.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpAndLogIn(page: Page, request: APIRequestContext, prefix: string): Promise<string> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Org E2E User" },
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

test.describe("Organization Management (real backend)", () => {
  test("a fresh signup with no org sees the real onboarding form on Settings, and creating an org unlocks the tabbed settings UI as its real Owner", async ({
    page,
    request,
  }) => {
    await signUpAndLogIn(page, request, "org-create");

    await page.goto("/settings");
    await expect(page.getByText("Set up your organization")).toBeVisible();
    await expect(page.getByRole("tab", { name: "Organization" })).toHaveCount(0);

    await page.getByLabel("Organization name").fill("E2E Test Nursery");
    await page.getByLabel("Contact email").fill(`contact-${Date.now()}@example.com`);
    await page.getByRole("button", { name: "Create organization" }).click();

    // POST /orgs makes the caller the real Owner atomically -- the
    // tabbed settings UI (gated on a real org_id, not a mock) should now
    // render, including the Employees tab, which only Owner/Org Admin/
    // Branch Manager ever see.
    await expect(page.getByRole("tab", { name: "Organization" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "Employees" })).toBeVisible();
    await expect(page.getByText("E2E Test Nursery")).toBeVisible();
  });

  test("the new Owner can create a real branch and see it listed", async ({ page, request }) => {
    await signUpAndLogIn(page, request, "org-branch");
    await page.goto("/settings");

    await page.getByLabel("Organization name").fill("Branch E2E Nursery");
    await page.getByLabel("Contact email").fill(`contact-${Date.now()}@example.com`);
    await page.getByRole("button", { name: "Create organization" }).click();
    await expect(page.getByRole("tab", { name: "Branches" })).toBeVisible();

    await page.getByRole("tab", { name: "Branches" }).click();
    await page.getByRole("button", { name: "New branch" }).click();

    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Branch name").fill("E2E Main Branch");
    await dialog.getByLabel("Address line 1").fill("100 Test Way");
    await dialog.getByLabel("City").fill("Portland");
    await dialog.getByLabel(/Country/).fill("US");
    await dialog.getByLabel(/Timezone/).fill("America/Los_Angeles");
    await dialog.getByRole("button", { name: "Create branch" }).click();

    await expect(page.getByRole("row", { name: /E2E Main Branch/ })).toBeVisible();
  });

  test("the Settings route requires authentication like every other protected page", async ({ page }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/\/login/);
  });
});
