import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for the 7J Sales & CRM module -- same "no mocking,
 * real apps/api, real Postgres" approach as e2e/inventory.spec.ts, and
 * the same disclosed constraint: this sandbox has no docker/Postgres, so
 * this suite is written and reviewed for correctness against the real,
 * already-implemented 7J components and the real Module 9 routes, but has
 * not been execution-verified end-to-end here. See
 * docs/frontend/14-sales-crm.md's Testing section.
 *
 * A fresh Owner signup has no seed data, so this walks the full real
 * dependency chain a Sale requires: branch -> customer -> inventory line
 * (with real on-hand stock received) -> sales order -> confirm (reserves
 * stock via Module 8's real InventoryService) -> checkout (generates the
 * real Sale + Invoice) -> record a payment -> request, approve, and
 * complete a return (the last step restocks inventory and is
 * `sales:void`-gated, which the Owner role satisfies).
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpLogInAndCreateBranch(page: Page, request: APIRequestContext, prefix: string): Promise<void> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Sales E2E User" },
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
  await branchDialog.getByLabel("Branch name").fill("E2E Sales Branch");
  await branchDialog.getByLabel("Address line 1").fill("400 Test Way");
  await branchDialog.getByLabel("City").fill("Portland");
  await branchDialog.getByLabel(/Country/).fill("US");
  await branchDialog.getByLabel(/Timezone/).fill("America/Los_Angeles");
  await branchDialog.getByRole("button", { name: "Create branch" }).click();
  await expect(page.getByRole("row", { name: /E2E Sales Branch/ })).toBeVisible();
}

async function createCustomer(page: Page, name: string): Promise<void> {
  await page.goto("/customers");
  await page.getByRole("button", { name: "Add customer" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name").fill(name);
  await dialog.getByRole("combobox", { name: "Branch" }).click();
  await page.getByRole("option", { name: "E2E Sales Branch" }).click();
  await dialog.getByRole("button", { name: "Add customer" }).click();
  await expect(page.getByText(name)).toBeVisible();
}

async function createAndStockInventoryLine(page: Page, name: string, receiveQuantity: string): Promise<void> {
  await page.goto("/inventory");
  await page.getByRole("button", { name: "Create line" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name").fill(name);
  await dialog.getByRole("combobox", { name: "Branch" }).click();
  await page.getByRole("option", { name: "E2E Sales Branch" }).click();
  await dialog.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option").first().click();
  await dialog.getByRole("combobox", { name: "Unit" }).click();
  await page.getByRole("option").first().click();
  await dialog.getByRole("button", { name: "Create line" }).click();
  await expect(page.getByText(name)).toBeVisible();

  await page.getByText(name).click();
  await page.getByRole("button", { name: "Receive" }).click();
  const receiveDialog = page.getByRole("dialog");
  await receiveDialog.getByLabel("Quantity").fill(receiveQuantity);
  await receiveDialog.getByRole("button", { name: "Receive stock" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(page.getByText(`On hand: ${receiveQuantity}`, { exact: true })).toBeVisible();
}

test.describe("Sales & CRM (real backend)", () => {
  test("creates a customer through the real form and it appears in the real Customers list", async ({ page, request }) => {
    await signUpLogInAndCreateBranch(page, request, "crm-create");
    await createCustomer(page, "E2E Casey Nguyen");

    await expect(page.getByText("E2E Casey Nguyen")).toBeVisible();
  });

  test("walks the full real order->confirm->checkout->sale->invoice->payment lifecycle", async ({ page, request }) => {
    await signUpLogInAndCreateBranch(page, request, "sales-lifecycle");
    await createCustomer(page, "E2E Jordan Rivera");
    await createAndStockInventoryLine(page, "E2E 4in nursery pots", "100");

    await page.goto("/sales");
    await page.getByRole("tab", { name: "Orders" }).click();
    await page.getByRole("button", { name: "New order" }).click();
    let dialog = page.getByRole("dialog");
    await dialog.getByRole("combobox", { name: "Branch" }).click();
    await page.getByRole("option", { name: "E2E Sales Branch" }).click();
    await dialog.getByRole("combobox", { name: "Customer" }).click();
    await page.getByRole("option", { name: "E2E Jordan Rivera" }).click();
    await dialog.getByRole("button", { name: "Add line" }).click();
    await dialog.getByRole("combobox", { name: "Inventory line" }).click();
    await page.getByRole("option", { name: "E2E 4in nursery pots" }).click();
    await dialog.getByPlaceholder("Unit price").fill("25.00");
    await dialog.getByRole("button", { name: "Create sales order" }).click();
    await expect(dialog).toBeHidden();

    await page.getByRole("row", { name: /draft/ }).click();
    await expect(page.getByRole("heading", { name: "Sales Order" })).toBeVisible();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByRole("button", { name: "Confirm" })).toBeHidden({ timeout: 30_000 });

    await page.getByRole("button", { name: "Checkout" }).click();
    await expect(page).toHaveURL(/\/sales\/[0-9a-f-]+$/);
    await expect(page.getByText("completed", { exact: false })).toBeVisible();

    // Checkout redirected to the completed Sale, which -- per
    // `SaleResponse` carrying no `invoice_id` -- doesn't itself show the
    // Invoice; go back to the Sales Order detail page, which does.
    await page.goto("/sales");
    await page.getByRole("tab", { name: "Orders" }).click();
    await page.getByRole("row", { name: /E2E Sales Branch/ }).click();
    await expect(page.getByRole("heading", { name: "Sales Order" })).toBeVisible();
    await page.reload();
    await expect(page.getByText(/Invoice INV-/)).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Record payment" }).click();
    dialog = page.getByRole("dialog");
    await dialog.getByLabel("Amount").fill("10");
    await dialog.getByRole("button", { name: "Record payment" }).click();
    await expect(page.getByText("Paid:", { exact: false })).toBeVisible();
  });

  test("requests, approves, and completes a real return against a completed sale", async ({ page, request }) => {
    await signUpLogInAndCreateBranch(page, request, "return-lifecycle");
    await createCustomer(page, "E2E Return Customer");
    await createAndStockInventoryLine(page, "E2E Soil bags", "50");

    await page.goto("/sales");
    await page.getByRole("tab", { name: "Orders" }).click();
    await page.getByRole("button", { name: "New order" }).click();
    const orderDialog = page.getByRole("dialog");
    await orderDialog.getByRole("combobox", { name: "Branch" }).click();
    await page.getByRole("option", { name: "E2E Sales Branch" }).click();
    await orderDialog.getByRole("combobox", { name: "Customer" }).click();
    await page.getByRole("option", { name: "E2E Return Customer" }).click();
    await orderDialog.getByRole("button", { name: "Add line" }).click();
    await orderDialog.getByRole("combobox", { name: "Inventory line" }).click();
    await page.getByRole("option", { name: "E2E Soil bags" }).click();
    await orderDialog.getByPlaceholder("Unit price").fill("25.00");
    await orderDialog.getByRole("button", { name: "Create sales order" }).click();
    await expect(orderDialog).toBeHidden();

    await page.getByRole("row", { name: /draft/ }).click();
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByRole("button", { name: "Confirm" })).toBeHidden({ timeout: 30_000 });
    await page.getByRole("button", { name: "Checkout" }).click();
    await expect(page).toHaveURL(/\/sales\/[0-9a-f-]+$/);

    await page.getByRole("button", { name: "Request return" }).click();
    const returnDialog = page.getByRole("dialog");
    await returnDialog.getByLabel(/Include line/).click();
    await returnDialog.getByRole("button", { name: "Request return" }).click();

    await page.goto("/sales");
    await page.getByRole("tab", { name: "Returns" }).click();
    await page.getByRole("row", { name: /E2E Sales Branch/ }).click();
    await expect(page).toHaveURL(/\/sales\/returns\/[0-9a-f-]+$/);

    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("approved", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Complete return" }).click();
    await expect(page.getByText("completed", { exact: true })).toBeVisible();
  });
});
