import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import AdminPage from "@/app/(app)/admin/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import {
  makeAIModelStatus,
  makeAuditLogPage,
  makeAuthorizationDenialPage,
  makeDataRetentionSummary,
  makeFeatureFlag,
  makeHealthReport,
  makeKnowledgeBaseStatus,
  makeNotificationTemplate,
  makeRolePermissionEntry,
  makeSystemConfig,
} from "@/test/fixtures/admin";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7O -- Administration, all six real tabs of the `/admin` route in one
 * file (same "one page, several real workflows, one describe block"
 * approach as `reports.test.tsx`). Covers both halves of the
 * `platform_admin`-only story: the tabs every real Owner/Org Admin/
 * Branch Manager account can use (Users, Roles & Permissions, Feature
 * Flags, Audit) *and* the honest permission-denied fallback for the
 * tabs/sub-tabs only `admin:read` unlocks (System, Platform Security
 * Events) -- never asserting those render real data for a normal
 * account, since that would be testing a fake capability.
 */
describe("Administration (7O)", () => {
  it("shows a permission-denied page without employees:read or admin:read", async () => {
    signIn(["plants:read"]);
    renderWithProviders(<AdminPage />);

    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
  });

  it("lists real users and changes a user's role through the dialog", async () => {
    const user = userEvent.setup();
    signIn(["employees:read", "employees:write"]);
    let submittedBody: { new_role_code?: string } | null = null;
    server.use(
      http.post(`${BASE}/api/v1/admin/users/:userId/role`, async ({ request }) => {
        submittedBody = (await request.json()) as typeof submittedBody;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithProviders(<AdminPage />);

    expect(await screen.findByText("Sam Rivera")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Actions for Sam Rivera" }));
    await user.click(await screen.findByRole("menuitem", { name: "Change role" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("combobox", { name: "Role" }));
    await user.click(await screen.findByRole("option", { name: "Branch Manager" }));
    await user.click(within(dialog).getByRole("button", { name: "Change role" }));

    await waitFor(() => expect(submittedBody).not.toBeNull());
    expect(submittedBody).toMatchObject({ new_role_code: "branch_manager" });
  });

  it("hides the row-actions menu for a read-only account (no employees:write)", async () => {
    signIn(["employees:read"]);
    renderWithProviders(<AdminPage />);

    await screen.findByText("Sam Rivera");
    expect(screen.queryByRole("button", { name: "Actions for Sam Rivera" })).not.toBeInTheDocument();
  });

  it("shows a role's real permissions on selection", async () => {
    const user = userEvent.setup();
    signIn(["employees:read"]);
    server.use(
      http.get(`${BASE}/api/v1/admin/roles/:roleId/permissions`, () =>
        HttpResponse.json([makeRolePermissionEntry({ permission_code: "plants:read", scope: "branch" })]),
      ),
    );
    renderWithProviders(<AdminPage />);

    await user.click(await screen.findByRole("tab", { name: "Roles & Permissions" }));
    await user.click(await screen.findByText("Branch Manager"));

    expect(await screen.findByText("plants:read")).toBeInTheDocument();
  });

  it("toggles a real org-scoped feature flag", async () => {
    const user = userEvent.setup();
    signIn(["employees:read", "feature_flags:manage"]);
    let toggledTo: boolean | null = null;
    server.use(
      http.get(`${BASE}/api/v1/admin/feature-flags`, () => HttpResponse.json([makeFeatureFlag({ key: "ai_disease_scan_v2", is_enabled: true })])),
      http.put(`${BASE}/api/v1/admin/feature-flags/:key/organization`, async ({ request }) => {
        const body = (await request.json()) as { is_enabled: boolean };
        toggledTo = body.is_enabled;
        return HttpResponse.json(makeFeatureFlag({ is_enabled: body.is_enabled }));
      }),
    );
    renderWithProviders(<AdminPage />);

    await user.click(await screen.findByRole("tab", { name: "Feature Flags" }));
    await user.click(await screen.findByRole("switch", { name: "Toggle ai_disease_scan_v2" }));

    await waitFor(() => expect(toggledTo).toBe(false));
  });

  it("lists the real audit log and shows a permission-denied fallback for Platform Security Events", async () => {
    const user = userEvent.setup();
    signIn(["employees:read", "audit:read"]);
    server.use(http.get(`${BASE}/api/v1/admin/audit-logs`, () => HttpResponse.json(makeAuditLogPage())));
    renderWithProviders(<AdminPage />);

    await user.click(await screen.findByRole("tab", { name: "Audit & Security" }));
    expect(await screen.findByText("user.role_changed")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Platform Security Events" }));
    expect(await screen.findByText("Platform-wide security events require a platform administrator account.")).toBeInTheDocument();
  });

  it("shows real authorization denials for an Owner account", async () => {
    const user = userEvent.setup();
    signIn(["employees:read", "audit:read"]);
    server.use(http.get(`${BASE}/api/v1/admin/authorization-denials`, () => HttpResponse.json(makeAuthorizationDenialPage())));
    renderWithProviders(<AdminPage />);

    await user.click(await screen.findByRole("tab", { name: "Audit & Security" }));
    await user.click(screen.getByRole("tab", { name: "Authorization Denials" }));

    expect(await screen.findByText("admin:read")).toBeInTheDocument();
  });

  it("shows an honest permission-denied fallback for the System tab on a normal tenant account", async () => {
    const user = userEvent.setup();
    signIn(["employees:read"]);
    renderWithProviders(<AdminPage />);

    await user.click(await screen.findByRole("tab", { name: "System" }));

    expect(
      await screen.findByText(
        "System Health, System Configuration, AI Administration, and Data Retention require a platform administrator account. Your role doesn't include admin:read.",
      ),
    ).toBeInTheDocument();
  });

  it("renders real System data for a platform_admin-equivalent account", async () => {
    const user = userEvent.setup();
    signIn(["employees:read", "admin:read"]);
    server.use(
      http.get(`${BASE}/api/v1/admin/health`, () => HttpResponse.json(makeHealthReport({ api: "ok", database_reachable: true }))),
      http.get(`${BASE}/api/v1/admin/system-config`, () => HttpResponse.json([makeSystemConfig({ key: "max_upload_size_mb" })])),
      http.get(`${BASE}/api/v1/admin/ai/models`, () => HttpResponse.json([makeAIModelStatus({ capability: "disease_detection" })])),
      http.get(`${BASE}/api/v1/admin/ai/knowledge-base`, () => HttpResponse.json([makeKnowledgeBaseStatus()])),
      http.get(`${BASE}/api/v1/admin/data-retention`, () => HttpResponse.json(makeDataRetentionSummary())),
    );
    renderWithProviders(<AdminPage />);

    await user.click(await screen.findByRole("tab", { name: "System" }));

    expect(await screen.findByText("Database reachable")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Configuration" }));
    expect(await screen.findByText("max_upload_size_mb")).toBeInTheDocument();
  });

  it("shows an honest permission-denied fallback for Notifications without notifications:manage_preferences", async () => {
    const user = userEvent.setup();
    signIn(["employees:read"]);
    renderWithProviders(<AdminPage />);

    await user.click(await screen.findByRole("tab", { name: "Notifications" }));

    expect(
      await screen.findByText("Template authoring, system alerts, and the delivery-retry sweep require notification management access."),
    ).toBeInTheDocument();
  });

  it("creates a real notification template and retries due notifications", async () => {
    const user = userEvent.setup();
    signIn(["employees:read", "notifications:manage_preferences"]);
    let createdBody: { category?: string; channel?: string; body_template?: string } | null = null;
    let retried = false;
    server.use(
      http.get(`${BASE}/api/v1/notifications/templates`, () => HttpResponse.json([])),
      http.post(`${BASE}/api/v1/notifications/templates`, async ({ request }) => {
        createdBody = (await request.json()) as typeof createdBody;
        return HttpResponse.json(makeNotificationTemplate(), { status: 201 });
      }),
      http.post(`${BASE}/api/v1/notifications/retry-due`, () => {
        retried = true;
        return HttpResponse.json({ retried_count: 1, results: [] });
      }),
    );
    renderWithProviders(<AdminPage />);

    await user.click(await screen.findByRole("tab", { name: "Notifications" }));
    await user.click(await screen.findByRole("combobox", { name: "Category" }));
    await user.click(await screen.findByRole("option", { name: "Watering overdue" }));
    await user.type(screen.getByLabelText("Body template"), "{{ plant_name }} needs water.");
    await user.click(screen.getByRole("button", { name: "Create template" }));

    await waitFor(() => expect(createdBody).not.toBeNull());
    expect(createdBody).toMatchObject({ category: "watering_overdue", channel: "in_app" });

    await user.click(screen.getByRole("tab", { name: "Broadcast & Retry" }));
    await user.click(await screen.findByRole("button", { name: "Retry due notifications now" }));
    await waitFor(() => expect(retried).toBe(true));
    expect(await screen.findByText("Retried 1 due notification(s).")).toBeInTheDocument();
  });
});
