import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { NotificationPreferencesPanel } from "@/components/settings/notification-preferences-panel";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeOrgSettings } from "@/test/fixtures/organization";
import { makePreference } from "@/test/fixtures/notifications";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7M / PG-58 -- the category x channel notification preferences matrix
 * that replaces `app/(app)/settings/page.tsx`'s `ComingSoon` placeholder.
 * Mirrors `organization.test.tsx`'s `signIn`/`server.use(...)` pattern.
 */
describe("NotificationPreferencesPanel (7M)", () => {
  it("shows a permission-denied fallback without notifications:manage_preferences", async () => {
    signIn(["plants:read"]);
    server.use(http.get(`${BASE}/api/v1/orgs/:id/settings`, () => HttpResponse.json(makeOrgSettings())));
    renderWithProviders(<NotificationPreferencesPanel />);

    expect(await screen.findByText(/doesn.t include notifications:manage_preferences/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save preferences" })).not.toBeInTheDocument();
  });

  it("loads real saved preference rows and reflects them in the grid, hiding the SMS column when the org has SMS off", async () => {
    signIn(["notifications:manage_preferences"]);
    server.use(
      http.get(`${BASE}/api/v1/orgs/:id/settings`, () => HttpResponse.json(makeOrgSettings({ sms_enabled: false }))),
      http.get(`${BASE}/api/v1/notifications/preferences`, () =>
        HttpResponse.json([
          makePreference({ category: "low_stock", channel: "email", enabled: false }),
          makePreference({ category: "low_stock", channel: "in_app", enabled: true }),
        ]),
      ),
    );
    renderWithProviders(<NotificationPreferencesPanel />);

    await screen.findByText("Channels by category");
    expect(screen.queryByRole("columnheader", { name: "SMS" })).not.toBeInTheDocument();

    const row = screen.getByText("Low stock").closest("tr") as HTMLElement;
    const emailCheckbox = within(row).getByRole("checkbox", { name: "Low stock via Email" });
    expect(emailCheckbox).not.toBeChecked();
    const inAppCheckbox = within(row).getByRole("checkbox", { name: "Low stock via In-app" });
    expect(inAppCheckbox).toBeChecked();
  });

  it("shows the SMS column when the org has SMS enabled, and saves a real full grid including unchecked cells", async () => {
    const user = userEvent.setup();
    signIn(["notifications:manage_preferences"]);
    let savedBody: Array<{ category: string; channel: string; enabled: boolean }> | null = null;
    server.use(
      http.get(`${BASE}/api/v1/orgs/:id/settings`, () => HttpResponse.json(makeOrgSettings({ sms_enabled: true }))),
      http.get(`${BASE}/api/v1/notifications/preferences`, () => HttpResponse.json([])),
      http.put(`${BASE}/api/v1/notifications/preferences`, async ({ request }) => {
        savedBody = (await request.json()) as typeof savedBody;
        return HttpResponse.json(savedBody);
      }),
    );
    renderWithProviders(<NotificationPreferencesPanel />);

    await screen.findByText("Channels by category");
    expect(screen.getByRole("columnheader", { name: "SMS" })).toBeInTheDocument();

    const row = screen.getByText("Disease confirmed").closest("tr") as HTMLElement;
    // No saved row yet -- real backend default is in_app/email ON, sms/push
    // OFF (PreferenceService._DEFAULT_ENABLED), which the grid mirrors.
    expect(within(row).getByRole("checkbox", { name: "Disease confirmed via In-app" })).toBeChecked();
    expect(within(row).getByRole("checkbox", { name: "Disease confirmed via SMS" })).not.toBeChecked();

    // Uncheck email for this one category to prove an explicit "off" is sent, not omitted.
    await user.click(within(row).getByRole("checkbox", { name: "Disease confirmed via Email" }));
    await user.click(screen.getByRole("button", { name: "Save preferences" }));

    await waitFor(() => expect(savedBody).not.toBeNull());
    const diseaseEmailRow = savedBody!.find((r) => r.category === "disease_confirmed" && r.channel === "email");
    expect(diseaseEmailRow?.enabled).toBe(false);
    // All 22 categories x 4 visible channels (SMS shown) are sent explicitly.
    expect(savedBody!.length).toBe(22 * 4);
  });
});
