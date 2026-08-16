import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import SettingsPage from "@/app/(app)/settings/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeBranch, makeOrganization } from "@/test/fixtures/shell";
import { makeAdminUser, makeAdminUserPage, makeRole } from "@/test/fixtures/organization";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

function signIn(overrides: Partial<Parameters<typeof makeMe>[0]> = {}) {
  useSessionStore.setState({ status: "authenticated", user: makeMe(overrides), accessToken: "access-token-1" });
}

/**
 * 7E Organization Management -- the onboarding create-org path, Branches
 * CRUD, and the Employees list/invite flow, all against real MSW-mocked
 * `apiClient` network responses (see test/msw/organization-handlers.ts).
 * Mirrors the 7D dashboard-page.test.tsx's real-network-layer approach.
 */
describe("SettingsPage (7E)", () => {
  it("shows the real onboarding form (not the tabbed settings UI) for a user with no org yet", async () => {
    signIn({ org_id: null, permissions: [] });
    renderWithProviders(<SettingsPage />);

    expect(await screen.findByText("Set up your organization")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Organization" })).not.toBeInTheDocument();
  });

  it("creates the organization, then re-fetches /auth/me and swaps to the real tabbed settings UI once org_id is granted", async () => {
    const user = userEvent.setup();
    signIn({ org_id: null, permissions: [] });
    // Once the org is created, the real backend would return org_id set with
    // Owner permissions on the next /auth/me -- simulate that server-side
    // state transition the same way the real backend would report it.
    server.use(
      http.get(`${BASE}/api/v1/auth/me`, () =>
        HttpResponse.json(makeMe({ org_id: "22222222-2222-2222-2222-222222222222", permissions: ["org:read", "branch:read"] })),
      ),
    );
    renderWithProviders(<SettingsPage />);

    await screen.findByText("Set up your organization");
    await user.type(screen.getByLabelText("Organization name"), "Green Thumb Nursery");
    await user.type(screen.getByLabelText("Contact email"), "owner@greenthumb.test");
    await user.click(screen.getByRole("button", { name: "Create organization" }));

    await waitFor(() => expect(screen.getByRole("tab", { name: "Organization" })).toBeInTheDocument());
  });

  it("gates the Employees tab behind employees:read, showing a real permission-denied state for roles that lack it", async () => {
    signIn({ permissions: ["org:read", "branch:read"] });
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    await user.click(await screen.findByRole("tab", { name: "Employees" }));
    expect(await screen.findByText("Your role doesn't include employee management access.")).toBeInTheDocument();
  });

  it("lists real branches and archives one through the AlertDialog confirmation", async () => {
    const user = userEvent.setup();
    signIn({ permissions: ["org:read", "branch:read", "branch:write", "branch:delete"] });
    const branch = makeBranch({ name: "Riverside Branch" });
    server.use(http.get(`${BASE}/api/v1/branches`, () => HttpResponse.json([branch])));
    let archived = false;
    server.use(
      http.delete(`${BASE}/api/v1/branches/:id`, () => {
        archived = true;
        return HttpResponse.json({ ...branch, status: "archived" });
      }),
    );
    renderWithProviders(<SettingsPage />);

    await user.click(await screen.findByRole("tab", { name: "Branches" }));
    expect(await screen.findByText("Riverside Branch")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Archive" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Archive" }));

    await waitFor(() => expect(archived).toBe(true));
  });

  it("lists real employees (name/email/status from GET /admin/users) and invites a new one", async () => {
    const user = userEvent.setup();
    signIn({ permissions: ["org:read", "branch:read", "employees:read", "employees:write"] });
    server.use(
      http.get(`${BASE}/api/v1/admin/users`, () => HttpResponse.json(makeAdminUserPage([makeAdminUser({ full_name: "Sam Rivera", email: "sam@greenthumb.test" })]))),
      http.get(`${BASE}/api/v1/admin/roles`, () => HttpResponse.json([makeRole({ code: "sales_staff", name: "Sales Staff" })])),
    );
    let invitedEmail: string | null = null;
    server.use(
      http.post(`${BASE}/api/v1/employees/invite`, async ({ request }) => {
        const body = (await request.json()) as { email: string };
        invitedEmail = body.email;
        return HttpResponse.json({ employee_id: "e-99", email: body.email, status: "invited" });
      }),
    );
    renderWithProviders(<SettingsPage />);

    await user.click(await screen.findByRole("tab", { name: "Employees" }));
    expect(await screen.findByText("Sam Rivera")).toBeInTheDocument();
    expect(screen.getByText("sam@greenthumb.test")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Invite employee" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Email"), "new.hire@greenthumb.test");
    await user.click(within(dialog).getByRole("combobox", { name: "Role" }));
    await user.click(await screen.findByRole("option", { name: "Sales Staff" }));
    await user.click(within(dialog).getByRole("button", { name: "Send invitation" }));

    await waitFor(() => expect(invitedEmail).toBe("new.hire@greenthumb.test"));
  });

  it("shows a real error state with retry when the branches list fails to load", async () => {
    const user = userEvent.setup();
    signIn({ permissions: ["org:read", "branch:read"] });
    server.use(http.get(`${BASE}/api/v1/branches`, () => HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 })));
    renderWithProviders(<SettingsPage />);

    await user.click(await screen.findByRole("tab", { name: "Branches" }));
    expect(await screen.findByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders the real organization profile fields for org:read (every role holds it)", async () => {
    signIn({ permissions: [] });
    server.use(http.get(`${BASE}/api/v1/orgs/:id`, () => HttpResponse.json(makeOrganization({ name: "Green Thumb Nursery" }))));
    renderWithProviders(<SettingsPage />);

    expect(await screen.findByText("Green Thumb Nursery")).toBeInTheDocument();
  });
});
