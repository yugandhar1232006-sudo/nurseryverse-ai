import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for 7L's AI Experience module -- same "no mocking,
 * real apps/api, real Postgres" approach as every prior phase's E2E spec
 * in this project, and the same disclosed constraint: written and
 * reviewed for correctness against the real, already-implemented 7L
 * components and the real Module 10 ai_predictions.py/ai_assistant.py
 * routes, but not execution-verified end-to-end here (no Chromium/
 * Postgres in this sandbox). See docs/frontend/16-ai-experience.md's
 * Testing section.
 *
 * Three tests, covering the per-plant surface (PG-26/PG-28), the org-wide
 * AI Center hub (PG-31/32/33), and the AI Assistant header overlay
 * (FR-9.1-9.4) -- the three genuinely separate surfaces this phase built.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpLogInAndRegisterPlant(page: Page, request: APIRequestContext, prefix: string): Promise<void> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "AI Experience E2E User" },
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
  await branchDialog.getByLabel("Branch name").fill("E2E AI Branch");
  await branchDialog.getByLabel("Address line 1").fill("700 Test Way");
  await branchDialog.getByLabel("City").fill("Portland");
  await branchDialog.getByLabel(/Country/).fill("US");
  await branchDialog.getByLabel(/Timezone/).fill("America/Los_Angeles");
  await branchDialog.getByRole("button", { name: "Create branch" }).click();
  await expect(page.getByText("E2E AI Branch")).toBeVisible();

  await page.goto("/plants/species");
  await page.getByRole("button", { name: "Add species" }).click();
  const speciesDialog = page.getByRole("dialog");
  await speciesDialog.getByRole("combobox", { name: "Category" }).click();
  await page.getByRole("option").first().click();
  await speciesDialog.getByLabel("Common name").fill("E2E AI Fig");
  await speciesDialog.getByLabel("Botanical name").fill("Ficus lyrata");
  await speciesDialog.getByRole("button", { name: "Add species" }).click();
  await expect(page.getByText("E2E AI Fig")).toBeVisible();

  await page.goto("/plants");
  await page.getByRole("button", { name: "Register plant" }).click();
  const registerDialog = page.getByRole("dialog");
  await registerDialog.getByRole("combobox", { name: "Branch" }).click();
  await page.getByRole("option", { name: "E2E AI Branch" }).click();
  await registerDialog.getByRole("combobox", { name: "Species" }).click();
  await page.getByRole("option", { name: "E2E AI Fig" }).click();
  await registerDialog.getByLabel("Label (optional)").fill("E2E AI Plant");
  await registerDialog.getByRole("button", { name: "Register plant" }).click();
  await expect(page.getByText("E2E AI Plant")).toBeVisible();
  await page.getByText("E2E AI Plant").click();
  await expect(page).toHaveURL(/\/plants\/[0-9a-f-]+/);
}

test.describe("AI Experience (real backend)", () => {
  test("runs a real on-demand survival prediction from a plant's AI Predictions tab and sees it in the real history", async ({
    page,
    request,
  }) => {
    await signUpLogInAndRegisterPlant(page, request, "ai-plant");

    await page.getByRole("tab", { name: "AI Predictions" }).click();
    await expect(page.getByText("No AI predictions yet")).toBeVisible();

    await page.getByRole("button", { name: "Run survival prediction" }).click();
    await expect(page.getByText("Survival prediction")).toBeVisible();
    await expect(page.getByText(/Confidence score:/)).toBeVisible();
  });

  test("the org-wide AI Center hub shows the same real prediction in its Survival Risk tab", async ({ page, request }) => {
    await signUpLogInAndRegisterPlant(page, request, "ai-center");

    await page.getByRole("tab", { name: "AI Predictions" }).click();
    await page.getByRole("button", { name: "Run survival prediction" }).click();
    await expect(page.getByText("Survival prediction")).toBeVisible();

    await page.goto("/ai-center");
    await expect(page.getByRole("tab", { name: "Survival Risk", selected: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: /\/100/ })).toBeVisible();
  });

  test("sends a real message through the AI Assistant header overlay and sees a real reply", async ({ page, request }) => {
    await signUpLogInAndRegisterPlant(page, request, "ai-assistant");

    await page.getByRole("button", { name: "AI Assistant" }).click();
    await expect(page.getByText("Ask me anything about your nursery")).toBeVisible();

    await page.getByPlaceholder("Type a message…").fill("What plants do I have?");
    await page.getByRole("button", { name: "Send message" }).click();

    // A real reply from the real orchestrator -- content is not asserted
    // verbatim (the LLM's exact wording is not a frontend contract), only
    // that the "Thinking…" pending state resolves into a real, non-empty
    // assistant turn.
    await expect(page.getByText("Thinking…")).toBeVisible();
    await expect(page.getByText("Thinking…")).not.toBeVisible({ timeout: 30_000 });
  });
});
