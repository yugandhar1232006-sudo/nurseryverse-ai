import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for the 7F Plant Catalog (Species/Variety) module --
 * same "no mocking, real apps/api, real Postgres" approach as
 * e2e/organization.spec.ts, and the same disclosed constraint: this
 * sandbox has no docker/Postgres, so this suite is written and reviewed
 * for correctness against the real, already-implemented 7F components
 * and the real Module 5 routes, but has not been execution-verified
 * end-to-end here. See docs/frontend/10-plant-catalog.md's Testing
 * section.
 *
 * `species:write` requires a real org (Owner/Org Admin by default per
 * docs/ux/07-role-permission-matrix.md), so every test here signs up
 * fresh and creates a real org first via the same `POST /orgs` onboarding
 * flow 7E's own E2E suite exercises -- there is no seed fixture this
 * sandbox can provision instead.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpLogInAndCreateOrg(page: Page, request: APIRequestContext, prefix: string): Promise<void> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Catalog E2E User" },
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
  await expect(page.getByRole("tab", { name: "Organization" })).toBeVisible();
}

test.describe("Plant Catalog (real backend)", () => {
  test("a real Owner adds a species with a category and care attributes, then sees it in the real list", async ({ page, request }) => {
    await signUpLogInAndCreateOrg(page, request, "catalog-species");

    await page.goto("/plants/species");
    await expect(page.getByText("Species catalog")).toBeVisible();
    await page.getByRole("button", { name: "Add species" }).click();

    const dialog = page.getByRole("dialog");
    await dialog.getByRole("combobox", { name: "Category" }).click();
    // Real, system-seeded plant-category taxonomy (migration 0002) --
    // whichever categories exist server-side populate this list; select
    // whatever the first real option is rather than a hardcoded name.
    await page.getByRole("option").first().click();
    await dialog.getByLabel("Common name").fill("E2E Fiddle Leaf Fig");
    await dialog.getByLabel("Botanical name").fill("Ficus lyrata");
    await dialog.getByRole("button", { name: "Add species" }).click();

    await expect(page.getByText("E2E Fiddle Leaf Fig")).toBeVisible();
  });

  test("adds a variety under a species from the real species detail view", async ({ page, request }) => {
    await signUpLogInAndCreateOrg(page, request, "catalog-variety");

    await page.goto("/plants/species");
    await page.getByRole("button", { name: "Add species" }).click();
    const speciesDialog = page.getByRole("dialog");
    await speciesDialog.getByRole("combobox", { name: "Category" }).click();
    await page.getByRole("option").first().click();
    await speciesDialog.getByLabel("Common name").fill("E2E Snake Plant");
    await speciesDialog.getByLabel("Botanical name").fill("Dracaena trifasciata");
    await speciesDialog.getByRole("button", { name: "Add species" }).click();
    await expect(page.getByText("E2E Snake Plant")).toBeVisible();

    await page.getByText("E2E Snake Plant").click();
    const detailDialog = page.getByRole("dialog");
    await detailDialog.getByRole("button", { name: "Add variety" }).click();
    const varietyDialog = page.getByRole("dialog", { name: "Add variety" });
    await varietyDialog.getByLabel("Variety name").fill("Bambino");
    await varietyDialog.getByRole("button", { name: "Add variety" }).click();

    await expect(detailDialog.getByText("Bambino")).toBeVisible();
  });

  test("the Species Catalog route requires authentication like every other protected page", async ({ page }) => {
    await page.goto("/plants/species");
    await expect(page).toHaveURL(/\/login/);
  });
});
