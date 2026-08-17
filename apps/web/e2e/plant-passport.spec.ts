import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for 7K's Plant Passport module -- same "no mocking,
 * real apps/api, real Postgres" approach as e2e/plant-lifecycle.spec.ts,
 * and the same disclosed constraint: this sandbox has no docker/Postgres,
 * so this suite is written and reviewed for correctness against the
 * real, already-implemented 7K components and the real Module 9
 * passport.py routes, but has not been execution-verified end-to-end
 * here. See docs/frontend/15-plant-passport.md's Testing section.
 *
 * Two tests, deliberately covering both halves of this module in one
 * real user journey: generating a passport from the internal,
 * authenticated Plant Profile (the only way `public_url`/`public_token`
 * come into existence), then opening that exact real `public_url` in a
 * brand-new, fully signed-out browser context -- proving the public
 * route genuinely requires no session, not just that it renders when a
 * session happens to still be present in the same tab.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpLogInAndRegisterPlant(page: Page, request: APIRequestContext, prefix: string): Promise<void> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Passport E2E User" },
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

  await page.getByRole("tab", { name: "Branches" }).click();
  await page.getByRole("button", { name: "New branch" }).click();
  const branchDialog = page.getByRole("dialog");
  await branchDialog.getByLabel("Branch name").fill("E2E Passport Branch");
  await branchDialog.getByLabel("Address line 1").fill("500 Test Way");
  await branchDialog.getByLabel("City").fill("Portland");
  await branchDialog.getByLabel(/Country/).fill("US");
  await branchDialog.getByLabel(/Timezone/).fill("America/Los_Angeles");
  await branchDialog.getByRole("button", { name: "Create branch" }).click();
  await expect(page.getByRole("row", { name: /E2E Passport Branch/ })).toBeVisible();

  await page.goto("/plants/species");
  await page.getByRole("button", { name: "Add species" }).click();
  const speciesDialog = page.getByRole("dialog");
  await speciesDialog.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option").first().click();
  await speciesDialog.getByLabel("Common name").fill("E2E Passport Fig");
  await speciesDialog.getByLabel("Botanical name").fill("Ficus lyrata");
  await speciesDialog.getByRole("button", { name: "Add species" }).click();
  await expect(page.getByText("E2E Passport Fig")).toBeVisible();

  await page.goto("/plants");
  await page.getByRole("button", { name: "Register plant" }).click();
  const registerDialog = page.getByRole("dialog");
  await registerDialog.getByRole("combobox", { name: "Branch" }).click();
  await page.getByRole("option", { name: "E2E Passport Branch" }).click();
  await registerDialog.getByRole("combobox", { name: "Species" }).click();
  await page.getByRole("option", { name: "E2E Passport Fig" }).click();
  await registerDialog.getByLabel("Label (optional)").fill("E2E Passport Plant");
  await registerDialog.getByRole("button", { name: "Register plant" }).click();
  await expect(page.getByText("E2E Passport Plant")).toBeVisible();
  await page.getByText("E2E Passport Plant").click();
  await expect(page).toHaveURL(/\/plants\/[0-9a-f-]+/);
}

test.describe("Plant Passport (real backend)", () => {
  test("generates a real passport from the Plant Profile's Passport tab", async ({ page, request }) => {
    await signUpLogInAndRegisterPlant(page, request, "passport-generate");

    await page.getByRole("tab", { name: "Passport" }).click();
    await expect(page.getByText("No passport generated yet")).toBeVisible();

    await page.getByRole("button", { name: "Generate passport" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Generate passport" }).click();

    await expect(page.getByText("Version 1")).toBeVisible();
    await expect(page.getByText("Latest")).toBeVisible();
    await expect(page.getByRole("button", { name: "Copy public link" })).toBeVisible();
  });

  test("a freshly generated passport's real public link opens with no session at all, in a brand-new browser context", async ({
    page,
    request,
    browser,
  }) => {
    await signUpLogInAndRegisterPlant(page, request, "passport-public");

    await page.getByRole("tab", { name: "Passport" }).click();
    await page.getByRole("button", { name: "Generate passport" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Generate passport" }).click();
    await expect(page.getByText("Version 1")).toBeVisible();

    const publicUrl = await page.getByRole("link", { name: "View public page" }).getAttribute("href");
    expect(publicUrl).toBeTruthy();

    // A brand-new, fully signed-out browser context -- no cookies, no
    // localStorage, no in-memory session state carried over from `page`
    // above -- proving the public route genuinely needs no session.
    const publicContext = await browser.newContext();
    const publicPage = await publicContext.newPage();
    await publicPage.goto(publicUrl as string);

    await expect(publicPage.getByText("E2E Passport Plant")).toBeVisible();
    await expect(publicPage.getByText(/NVA-PP-/)).toBeVisible();
    await expect(publicPage.getByText("Ficus lyrata")).toBeVisible();

    await publicContext.close();
  });
});
