import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for the 7H Plant Digital Twin module -- same "no
 * mocking, real apps/api, real Postgres" approach as
 * e2e/plant-lifecycle.spec.ts, and the same disclosed constraint: this
 * sandbox has no docker/Postgres, so this suite is written and reviewed
 * for correctness against the real, already-implemented 7H components
 * and the real Module 7 read-only routes, but has not been
 * execution-verified end-to-end here. See docs/frontend/12-digital-twin.md's
 * Testing section.
 *
 * A fresh Owner signup has no seed data, so every test provisions its own
 * real branch, real species, and a real registered plant before a twin
 * exists to inspect -- a twin is only ever created by the backend's own
 * event projector reacting to a real `plant.registered` event, so there is
 * no way to seed one directly. Panel-level rendering (Versions compare,
 * Events payload disclosure, a real inconsistency result) is additionally
 * covered by the Vitest/RTL suite
 * (components/digital-twin/__tests__/digital-twin.test.tsx) with
 * MSW-mocked network responses.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpLogInAndRegisterAPlant(page: Page, request: APIRequestContext, prefix: string, plantLabel: string): Promise<void> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Digital Twin E2E User" },
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
  await branchDialog.getByLabel("Branch name").fill("E2E Twin Branch");
  await branchDialog.getByLabel("Address line 1").fill("200 Test Way");
  await branchDialog.getByLabel("City").fill("Portland");
  await branchDialog.getByLabel(/Country/).fill("US");
  await branchDialog.getByLabel(/Timezone/).fill("America/Los_Angeles");
  await branchDialog.getByRole("button", { name: "Create branch" }).click();
  await expect(page.getByText("E2E Twin Branch")).toBeVisible();

  await page.goto("/plants/species");
  await page.getByRole("button", { name: "Add species" }).click();
  const speciesDialog = page.getByRole("dialog");
  await speciesDialog.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option").first().click();
  await speciesDialog.getByLabel("Common name").fill("E2E Twin Fig");
  await speciesDialog.getByLabel("Botanical name").fill("Ficus lyrata");
  await speciesDialog.getByRole("button", { name: "Add species" }).click();
  await expect(page.getByText("E2E Twin Fig")).toBeVisible();

  await page.goto("/plants");
  await page.getByRole("button", { name: "Register plant" }).click();
  const registerDialog = page.getByRole("dialog");
  await registerDialog.getByRole("combobox", { name: "Branch" }).click();
  await page.getByRole("option", { name: "E2E Twin Branch" }).click();
  await registerDialog.getByRole("combobox", { name: "Species" }).click();
  await page.getByRole("option", { name: "E2E Twin Fig" }).click();
  await registerDialog.getByLabel("Label (optional)").fill(plantLabel);
  await registerDialog.getByRole("button", { name: "Register plant" }).click();
  await page.getByText(plantLabel).click();
  await expect(page).toHaveURL(/\/plants\/[0-9a-f-]+/);
}

test.describe("Plant Digital Twin (real backend)", () => {
  test("a freshly registered plant already has a real, valid twin with a non-error current state", async ({ page, request }) => {
    await signUpLogInAndRegisterAPlant(page, request, "twin-overview", "E2E Twin Plant #1");

    await page.getByRole("tab", { name: "Digital Twin" }).click();

    await expect(page.getByText("in_production")).toBeVisible();
    await expect(page.getByText("Owned by nursery")).toBeVisible();
  });

  test("recording a real growth measurement produces a real new twin version visible in the Timeline", async ({ page, request }) => {
    await signUpLogInAndRegisterAPlant(page, request, "twin-timeline", "E2E Twin Plant #2");

    await page.getByRole("tab", { name: "Growth" }).click();
    await page.getByRole("button", { name: "Record measurement" }).click();
    const growthDialog = page.getByRole("dialog");
    await growthDialog.getByLabel("Height (cm)").fill("30");
    await growthDialog.getByRole("button", { name: "Save measurement" }).click();
    await expect(page.getByText("Height: 30 cm")).toBeVisible();

    await page.getByRole("tab", { name: "Digital Twin" }).click();
    const twinTabs = page.getByRole("tablist", { name: "Digital Twin views" });
    await twinTabs.getByRole("tab", { name: "Timeline" }).click();

    await expect(page.getByText("plant.growth_recorded")).toBeVisible();
  });

  test("runs a real replay-consistency check from the Digital Twin overview", async ({ page, request }) => {
    await signUpLogInAndRegisterAPlant(page, request, "twin-verify", "E2E Twin Plant #3");

    await page.getByRole("tab", { name: "Digital Twin" }).click();
    await page.getByRole("button", { name: "Verify now" }).click();

    await expect(page.getByText(/Consistent as of version/)).toBeVisible();
  });
});
