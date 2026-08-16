import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

/**
 * Real-backend E2E for 7M's Notification Preferences module (PG-58) --
 * same "no mocking, real apps/api, real Postgres" approach and the same
 * disclosed constraint as every prior phase's spec in this project:
 * written and reviewed for correctness against the real, already-
 * implemented `NotificationPreferencesPanel` and the real Module 11
 * `GET/PUT /notifications/preferences` routes, but not execution-verified
 * end-to-end here (no Chromium/Postgres in this sandbox). See
 * docs/frontend/17-notifications.md's Testing section.
 */

const PASSWORD = "Correct-horse-battery-1";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function uniqueEmail(prefix: string): string {
  return `e2e-${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`;
}

async function signUpLogInAndCreateOrg(page: Page, request: APIRequestContext, prefix: string): Promise<void> {
  const email = uniqueEmail(prefix);
  const res = await request.post(`${API_BASE_URL}/api/v1/auth/signup`, {
    data: { email, password: PASSWORD, full_name: "Notifications E2E User" },
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

test.describe("Notification Preferences (real backend, PG-58)", () => {
  test("saves a real preference change and it survives a reload", async ({ page, request }) => {
    await signUpLogInAndCreateOrg(page, request, "notif-prefs");

    await page.getByRole("tab", { name: "Notifications" }).click();
    await expect(page.getByText("Channels by category")).toBeVisible();

    const row = page.getByText("Low stock").locator("xpath=ancestor::tr");
    const emailCheckbox = row.getByRole("checkbox", { name: "Low stock via Email" });
    // Backend default for a never-configured (category, channel) pair is
    // ON for email (PreferenceService._DEFAULT_ENABLED) -- uncheck it and
    // save, proving a real explicit "off" row persists.
    await expect(emailCheckbox).toBeChecked();
    await emailCheckbox.uncheck();
    await page.getByRole("button", { name: "Save preferences" }).click();
    await expect(page.getByText("Notification preferences saved")).toBeVisible();

    await page.reload();
    await page.getByRole("tab", { name: "Notifications" }).click();
    const rowAfterReload = page.getByText("Low stock").locator("xpath=ancestor::tr");
    await expect(rowAfterReload.getByRole("checkbox", { name: "Low stock via Email" })).not.toBeChecked();
  });
});
