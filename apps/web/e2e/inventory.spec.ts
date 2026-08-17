import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for the 7I Inventory module -- same "no mocking, real
 * apps/api, real Postgres" approach as e2e/plant-lifecycle.spec.ts and
 * e2e/digital-twin.spec.ts, and the same disclosed constraint: this
 * sandbox has no docker/Postgres, so this suite is written and reviewed
 * for correctness against the real, already-implemented 7I components and
 * the real Module 8 routes (including the `GET /units` route added this
 * phase), but has not been execution-verified end-to-end here. See
 * docs/frontend/13-inventory.md's Testing section.
 *
 * A fresh Owner signup has no seed data, so every test provisions its own
 * real branch before an inventory line can exist -- `CreateInventoryLineRequest`
 * requires a real `branch_id`, `category_id` (from the system-seeded
 * `GET /plant-categories`), and `unit_id` (from the system-seeded
 * `GET /units`), so no inventory line can be created without a branch
 * first. Dialog-level rendering (Locations panel, Reports panel, a real
 * 409 from an over-adjustment) is additionally covered by the Vitest/RTL
 * suite (components/inventory/__tests__/inventory.test.tsx) with
 * MSW-mocked network responses.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpLogInAndCreateBranch(page: Page, request: APIRequestContext, prefix: string): Promise<void> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Inventory E2E User" },
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
  await branchDialog.getByLabel("Branch name").fill("E2E Inventory Branch");
  await branchDialog.getByLabel("Address line 1").fill("300 Test Way");
  await branchDialog.getByLabel("City").fill("Portland");
  await branchDialog.getByLabel(/Country/).fill("US");
  await branchDialog.getByLabel(/Timezone/).fill("America/Los_Angeles");
  await branchDialog.getByRole("button", { name: "Create branch" }).click();
  await expect(page.getByRole("row", { name: /E2E Inventory Branch/ })).toBeVisible();
}

async function createInventoryLine(page: Page, name: string): Promise<void> {
  await page.goto("/inventory");
  await page.getByRole("button", { name: "Create line" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name").fill(name);
  await dialog.getByRole("combobox", { name: "Branch" }).click();
  await page.getByRole("option", { name: "E2E Inventory Branch" }).click();
  await dialog.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option").first().click();
  await dialog.getByRole("combobox", { name: "Unit" }).click();
  await page.getByRole("option").first().click();
  await dialog.getByRole("button", { name: "Create line" }).click();
  await expect(page.getByText(name)).toBeVisible();
}

test.describe("Inventory (real backend)", () => {
  test("creates a real inventory line through the real form and it appears in the real Stock list", async ({ page, request }) => {
    await signUpLogInAndCreateBranch(page, request, "inv-create");
    await createInventoryLine(page, "E2E 4in nursery pots");

    await expect(page.getByText("E2E 4in nursery pots")).toBeVisible();
    // A brand-new line starts with on-hand 0 and the default 10-unit
    // low-stock threshold, so it renders as Low stock (not In stock).
    await expect(page.locator("table").getByRole("cell").filter({ hasText: "Low stock" })).toBeVisible();
  });

  test("receives real stock against a real inventory line and the on-hand quantity updates", async ({ page, request }) => {
    await signUpLogInAndCreateBranch(page, request, "inv-receive");
    await createInventoryLine(page, "E2E Soil bags");

    await page.getByText("E2E Soil bags").click();
    await expect(page).toHaveURL(/\/inventory\/[0-9a-f-]+/);

    await page.getByRole("button", { name: "Receive" }).click();
    const receiveDialog = page.getByRole("dialog");
    await receiveDialog.getByLabel("Quantity").fill("50");
    await receiveDialog.getByRole("button", { name: "Receive stock" }).click();

    await expect(page.getByText("On hand: 50", { exact: true })).toBeVisible();
  });

  test("adjusts real stock with a reason and the movement appears in the real ledger", async ({ page, request }) => {
    await signUpLogInAndCreateBranch(page, request, "inv-adjust");
    await createInventoryLine(page, "E2E Fertilizer");

    await page.getByText("E2E Fertilizer").click();
    await page.getByRole("button", { name: "Receive" }).click();
    let dialog = page.getByRole("dialog");
    await dialog.getByLabel("Quantity").fill("20");
    await dialog.getByRole("button", { name: "Receive stock" }).click();

    await page.getByRole("button", { name: "Adjust" }).click();
    dialog = page.getByRole("dialog");
    await dialog.getByLabel("Change").fill("-5");
    await dialog.getByRole("combobox", { name: "Reason" }).click();
    await page.getByRole("option", { name: "Count correction" }).click();
    await dialog.getByRole("button", { name: "Adjust stock" }).click();

    await page.getByRole("tab", { name: "Movements" }).click();
    await expect(page.getByText("Adjusted", { exact: true })).toBeVisible();
  });

  test("creates a real inventory location for a branch and it appears in the real Locations panel", async ({ page, request }) => {
    await signUpLogInAndCreateBranch(page, request, "inv-location");

    await page.goto("/inventory");
    await page.getByRole("tab", { name: "Locations" }).click();
    await page.getByRole("button", { name: "New location" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Name").fill("E2E Greenhouse 1");
    await dialog.getByRole("combobox", { name: "Type" }).click();
    await page.getByRole("option", { name: "Greenhouse" }).click();
    await dialog.getByRole("button", { name: "Create location" }).click();

    await expect(page.getByText("E2E Greenhouse 1")).toBeVisible();
  });
});
