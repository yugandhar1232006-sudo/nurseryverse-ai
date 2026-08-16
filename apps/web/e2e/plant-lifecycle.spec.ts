import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for the 7G Plant Lifecycle module -- same "no
 * mocking, real apps/api, real Postgres" approach as
 * e2e/plant-catalog.spec.ts, and the same disclosed constraint: this
 * sandbox has no docker/Postgres, so this suite is written and reviewed
 * for correctness against the real, already-implemented 7G components
 * and the real Module 6 routes, but has not been execution-verified
 * end-to-end here. See docs/frontend/11-plant-lifecycle.md's Testing
 * section.
 *
 * A fresh Owner signup has no seed data, so every test provisions its
 * own real branch (via Settings) and real species (via /plants/species)
 * before it can register a plant -- there is no fixture this sandbox can
 * substitute instead. Record-tab CRUD (growth/health/watering/
 * fertilizer/environmental/disease reports) against real component code
 * is additionally covered by the Vitest/RTL suite
 * (components/plants/__tests__/plant-lifecycle.test.tsx) with
 * MSW-mocked network responses.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpLogInAndSetUpNursery(page: Page, request: APIRequestContext, prefix: string): Promise<void> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Lifecycle E2E User" },
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
  await branchDialog.getByLabel("Branch name").fill("E2E Main Branch");
  await branchDialog.getByLabel("Address line 1").fill("100 Test Way");
  await branchDialog.getByLabel("City").fill("Portland");
  await branchDialog.getByLabel(/Country/).fill("US");
  await branchDialog.getByLabel(/Timezone/).fill("America/Los_Angeles");
  await branchDialog.getByRole("button", { name: "Create branch" }).click();
  await expect(page.getByText("E2E Main Branch")).toBeVisible();

  await page.goto("/plants/species");
  await page.getByRole("button", { name: "Add species" }).click();
  const speciesDialog = page.getByRole("dialog");
  await speciesDialog.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option").first().click();
  await speciesDialog.getByLabel("Common name").fill("E2E Fiddle Leaf Fig");
  await speciesDialog.getByLabel("Botanical name").fill("Ficus lyrata");
  await speciesDialog.getByRole("button", { name: "Add species" }).click();
  await expect(page.getByText("E2E Fiddle Leaf Fig")).toBeVisible();
}

test.describe("Plant Lifecycle (real backend)", () => {
  test("a real Owner registers a plant, sees it in the real list, and opens its Plant Profile", async ({ page, request }) => {
    await signUpLogInAndSetUpNursery(page, request, "lifecycle-register");

    await page.goto("/plants");
    await page.getByRole("button", { name: "Register plant" }).click();

    const dialog = page.getByRole("dialog");
    await dialog.getByRole("combobox", { name: "Branch" }).click();
    await page.getByRole("option", { name: "E2E Main Branch" }).click();
    await dialog.getByRole("combobox", { name: "Species" }).click();
    await page.getByRole("option", { name: "E2E Fiddle Leaf Fig" }).click();
    await dialog.getByLabel("Label (optional)").fill("E2E Plant #1");
    await dialog.getByRole("button", { name: "Register plant" }).click();

    await expect(page.getByText("E2E Plant #1")).toBeVisible();
    await page.getByText("E2E Plant #1").click();

    await expect(page).toHaveURL(/\/plants\/[0-9a-f-]+/);
    await expect(page.getByRole("heading", { name: "E2E Plant #1" })).toBeVisible();
  });

  test("records a real growth measurement from the Plant Profile's Growth tab", async ({ page, request }) => {
    await signUpLogInAndSetUpNursery(page, request, "lifecycle-growth");

    await page.goto("/plants");
    await page.getByRole("button", { name: "Register plant" }).click();
    const registerDialog = page.getByRole("dialog");
    await registerDialog.getByRole("combobox", { name: "Branch" }).click();
    await page.getByRole("option", { name: "E2E Main Branch" }).click();
    await registerDialog.getByRole("combobox", { name: "Species" }).click();
    await page.getByRole("option", { name: "E2E Fiddle Leaf Fig" }).click();
    await registerDialog.getByLabel("Label (optional)").fill("E2E Plant #2");
    await registerDialog.getByRole("button", { name: "Register plant" }).click();
    await page.getByText("E2E Plant #2").click();

    await page.getByRole("tab", { name: "Growth" }).click();
    await page.getByRole("button", { name: "Record measurement" }).click();
    const growthDialog = page.getByRole("dialog");
    await growthDialog.getByLabel("Height (cm)").fill("42");
    await growthDialog.getByRole("button", { name: "Save measurement" }).click();

    await expect(page.getByText("Height: 42 cm")).toBeVisible();
  });

  test("the Plants route requires authentication like every other protected page", async ({ page }) => {
    await page.goto("/plants");
    await expect(page).toHaveURL(/\/login/);
  });
});
