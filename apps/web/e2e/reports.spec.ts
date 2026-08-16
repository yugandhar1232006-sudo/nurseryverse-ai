import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for 7N's Report Catalog/Generate/Status/History/
 * Download + Scheduled Reports CRUD -- same "no mocking, real apps/api,
 * real Postgres" approach and the same disclosed constraint as every
 * prior phase's spec in this project: written and reviewed for
 * correctness against the real, already-implemented 7N components and
 * the real Module 12 `reports.py` routes, but not execution-verified
 * end-to-end here (no Chromium/Postgres in this sandbox). See
 * docs/frontend/18-reports-analytics.md's Testing section.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpLogInAndCreateOrg(page: Page, request: APIRequestContext, prefix: string): Promise<void> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Reports E2E User" },
  });
  if (!res.ok()) {
    throw new Error(`Signup fixture failed (${res.status()}): ${await res.text()}`);
  }

  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/");

  await page.goto("/settings");
  await page.getByLabel("Organization name").fill(`${prefix} Nursery`);
  await page.getByLabel("Contact email").fill(`contact-${Date.now()}@example.com`);
  await page.getByRole("button", { name: "Create organization" }).click();
  await expect(page.getByRole("tab", { name: "Branches" })).toBeVisible();
}

test.describe("Reports & Analytics (real backend, 7N)", () => {
  test("generates a real report and sees it move from pending to complete in history, with a real download link", async ({
    page,
    request,
  }) => {
    await signUpLogInAndCreateOrg(page, request, "reports-generate");

    await page.goto("/reports");
    await expect(page.getByText("Report Catalog")).toBeVisible();

    await page.getByRole("button", { name: "Generate report" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("combobox", { name: "Report type" }).click();
    await page.getByRole("option").first().click();
    await dialog.getByRole("button", { name: "Generate" }).click();

    // The real 202-Accepted async flow -- history polls on its own until
    // the real backend's BackgroundTasks generation settles.
    await expect(page.getByText("Complete")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("link", { name: /Download/ })).toHaveAttribute("href", /\/download$/);
  });

  test("creates a real scheduled report and can pause it", async ({ page, request }) => {
    await signUpLogInAndCreateOrg(page, request, "reports-scheduled");

    await page.goto("/reports");
    await page.getByRole("tab", { name: "Scheduled" }).click();
    await page.getByRole("button", { name: "New schedule" }).click();

    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Name").fill("E2E weekly sales summary");
    await dialog.getByRole("combobox", { name: "Report type" }).click();
    await page.getByRole("option").first().click();
    const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString().slice(0, 16);
    await dialog.getByLabel("First run").fill(tomorrow);
    await dialog.getByRole("button", { name: "Create schedule" }).click();

    await expect(page.getByText("E2E weekly sales summary")).toBeVisible();
    await expect(page.getByText("Active")).toBeVisible();

    await page.getByRole("button", { name: "Pause" }).click();
    await expect(page.getByText("Paused")).toBeVisible();
  });
});
