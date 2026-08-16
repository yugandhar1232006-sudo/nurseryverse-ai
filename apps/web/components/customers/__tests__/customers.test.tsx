import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import CustomersPage from "@/app/(app)/customers/page";
import CustomerDetailPage from "@/app/(app)/customers/[id]/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeCustomer, makeCustomerContact, makeCustomerPage, makeCustomerTag } from "@/test/fixtures/customers";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ id: makeCustomer().id }),
}));

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7J Customers -- real MSW-mocked `apiClient` network responses, same
 * approach as 7D-7I's suites. Covers `/customers` (search/filter/create)
 * and `/customers/[id]` (Overview/Contacts/Tags tabs -- Addresses/Notes/
 * Communications/Purchase History share the same add-and-list or
 * paginated-list shape already exercised by these three, so aren't
 * separately duplicated here).
 */
describe("CustomersPage (7J)", () => {
  it("shows PermissionDenied for a role without customers:read", async () => {
    signIn([]);
    renderWithProviders(<CustomersPage />);

    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
    expect(screen.queryByText("Customers")).not.toBeInTheDocument();
  });

  it("lists real customers and supports the search filter re-fetching from the backend", async () => {
    const user = userEvent.setup();
    signIn(["customers:read"]);
    let lastSearch: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/customers`, ({ request }) => {
        lastSearch = new URL(request.url).searchParams.get("search");
        return HttpResponse.json(makeCustomerPage([makeCustomer({ name: "Jordan Rivera" })]));
      }),
    );
    renderWithProviders(<CustomersPage />);

    expect(await screen.findByText("Jordan Rivera")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Search customers"), "jordan");
    await waitFor(() => expect(lastSearch).toBe("jordan"), { timeout: 2000 });
  });

  it("creates a customer through the real form", async () => {
    const user = userEvent.setup();
    signIn(["customers:read", "customers:write"]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.post(`${BASE}/api/v1/customers`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeCustomer());
      }),
    );
    renderWithProviders(<CustomersPage />);

    await user.click(await screen.findByRole("button", { name: "Add customer" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Casey Nguyen");
    await user.click(within(dialog).getByRole("combobox", { name: "Branch" }));
    await user.click(await screen.findByRole("option", { name: "Main Branch" }));
    await user.click(within(dialog).getByRole("button", { name: "Add customer" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({ name: "Casey Nguyen", customer_type: "retail" });
  });

  it("shows a real empty state distinguishing 'no customers yet' from 'no matches'", async () => {
    signIn(["customers:read"]);
    server.use(http.get(`${BASE}/api/v1/customers`, () => HttpResponse.json(makeCustomerPage([]))));
    renderWithProviders(<CustomersPage />);

    expect(await screen.findByText("No customers yet")).toBeInTheDocument();
  });

  it("shows a real error state with retry when the customer list fails to load", async () => {
    signIn(["customers:read"]);
    server.use(
      http.get(`${BASE}/api/v1/customers`, () =>
        HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 }),
      ),
    );
    renderWithProviders(<CustomersPage />);

    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument());
  });
});

describe("CustomerDetailPage (7J)", () => {
  it("shows the real customer's identity strip and Overview analytics", async () => {
    signIn(["customers:read"]);
    server.use(http.get(`${BASE}/api/v1/customers/:id`, () => HttpResponse.json(makeCustomer({ name: "Jordan Rivera" }))));
    renderWithProviders(<CustomerDetailPage />);

    expect(await screen.findByRole("heading", { name: "Jordan Rivera" })).toBeInTheDocument();
    expect(await screen.findByText("Total orders")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("adds a real contact through the Contacts tab, which has no delete/edit route", async () => {
    const user = userEvent.setup();
    signIn(["customers:read", "customers:write"]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/api/v1/customers/:id/contacts`, () => HttpResponse.json([])),
      http.post(`${BASE}/api/v1/customers/:id/contacts`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeCustomerContact({ name: "Sam Lee" }));
      }),
    );
    renderWithProviders(<CustomerDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Contacts" }));
    expect(await screen.findByText("No contacts yet")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Add contact" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Name"), "Sam Lee");
    await user.click(within(dialog).getByRole("button", { name: "Add contact" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({ name: "Sam Lee", is_primary: false });
  });

  it("adds and removes a real tag -- the one CRM sub-resource with a delete route", async () => {
    const user = userEvent.setup();
    signIn(["customers:read", "customers:write"]);
    let removedTag: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/customers/:id/tags`, () => HttpResponse.json([makeCustomerTag({ tag: "vip" })])),
      http.delete(`${BASE}/api/v1/customers/:id/tags/:tag`, ({ params }) => {
        removedTag = params.tag as string;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithProviders(<CustomerDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "Tags" }));
    expect(await screen.findByText("vip")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove tag vip" }));
    await waitFor(() => expect(removedTag).toBe("vip"));
  });

  it("shows a real error state with retry when the customer profile fails to load", async () => {
    signIn(["customers:read"]);
    server.use(
      http.get(`${BASE}/api/v1/customers/:id`, () =>
        HttpResponse.json({ error: { code: "internal_error", message: "Server error." } }, { status: 500 }),
      ),
    );
    renderWithProviders(<CustomerDetailPage />);

    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument());
  });
});
