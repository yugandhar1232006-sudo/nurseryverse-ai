import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import SalesPage from "@/app/(app)/sales/page";
import SalesOrderDetailPage from "@/app/(app)/sales/orders/[id]/page";
import SaleDetailPage from "@/app/(app)/sales/[id]/page";
import ReturnDetailPage from "@/app/(app)/sales/returns/[id]/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeInventoryItem, makeInventoryPage } from "@/test/fixtures/inventory";
import {
  makeInvoice,
  makeQuotationPage,
  makeRefundPage,
  makeReturn,
  makeSale,
  makeSalePage,
  makeSalesOrder,
  makeSalesOrderPage,
} from "@/test/fixtures/sales";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ id: "detail-01" }),
}));

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7J Sales -- real MSW-mocked `apiClient` network responses, same
 * approach as 7D-7I's suites. Covers `/sales` (Quotations/Orders/Sales/
 * Returns/Refunds/Reports tabs) and the three detail pages that carry
 * real lifecycle actions: Sales Order (confirm/checkout/Invoice),
 * completed Sale (request return), and Return (approve/complete).
 * Quotation detail shares the same status-change shape already exercised
 * indirectly by the Return's approve/reject actions, so isn't separately
 * duplicated here.
 */
describe("SalesPage (7J)", () => {
  it("shows PermissionDenied for a role without sales:read", async () => {
    signIn([]);
    renderWithProviders(<SalesPage />);

    expect(await screen.findByText("You don't have access to this page")).toBeInTheDocument();
    expect(screen.queryByText("Sales")).not.toBeInTheDocument();
  });

  it("lists real quotations and creates one through the real form", async () => {
    const user = userEvent.setup();
    signIn(["sales:read", "sales:write"]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/api/v1/quotations`, () => HttpResponse.json(makeQuotationPage())),
      http.get(`${BASE}/api/v1/inventory`, () => HttpResponse.json(makeInventoryPage([makeInventoryItem({ name: "4in nursery pots" })]))),
      http.post(`${BASE}/api/v1/quotations`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeSale());
      }),
    );
    renderWithProviders(<SalesPage />);

    await user.click(await screen.findByRole("button", { name: "New quotation" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("combobox", { name: "Branch" }));
    await user.click(await screen.findByRole("option", { name: "Main Branch" }));
    await user.click(within(dialog).getByRole("combobox", { name: "Customer" }));
    await user.click(await screen.findByRole("option", { name: "Jordan Rivera" }));
    await user.click(within(dialog).getByRole("button", { name: "Add line" }));
    await user.click(within(dialog).getByRole("combobox", { name: "Inventory line" }));
    await user.click(await screen.findByRole("option", { name: "4in nursery pots" }));
    await user.click(within(dialog).getByRole("button", { name: "Create quotation" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({ branch_id: "44444444-4444-4444-4444-444444444444" });
    expect((created as unknown as { items: unknown[] }).items).toHaveLength(1);
  });

  it("lists real sales orders and creates one through the real form", async () => {
    const user = userEvent.setup();
    signIn(["sales:read", "sales:write"]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/api/v1/sales-orders`, () => HttpResponse.json(makeSalesOrderPage())),
      http.get(`${BASE}/api/v1/inventory`, () => HttpResponse.json(makeInventoryPage([makeInventoryItem({ name: "4in nursery pots" })]))),
      http.post(`${BASE}/api/v1/sales-orders`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeSalesOrder());
      }),
    );
    renderWithProviders(<SalesPage />);

    await user.click(await screen.findByRole("tab", { name: "Orders" }));
    await user.click(await screen.findByRole("button", { name: "New order" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("combobox", { name: "Branch" }));
    await user.click(await screen.findByRole("option", { name: "Main Branch" }));
    await user.click(within(dialog).getByRole("combobox", { name: "Customer" }));
    await user.click(await screen.findByRole("option", { name: "Jordan Rivera" }));
    await user.click(within(dialog).getByRole("button", { name: "Add line" }));
    await user.click(within(dialog).getByRole("combobox", { name: "Inventory line" }));
    await user.click(await screen.findByRole("option", { name: "4in nursery pots" }));
    await user.click(within(dialog).getByRole("button", { name: "Create sales order" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({ idempotency_key: null });
  });

  it("lists real completed Sales with no create action", async () => {
    signIn(["sales:read"]);
    server.use(http.get(`${BASE}/api/v1/sales`, () => HttpResponse.json(makeSalePage([makeSale({ total_amount: "215.00" })]))));
    renderWithProviders(<SalesPage />);

    await userEvent.setup().click(await screen.findByRole("tab", { name: "Sales" }));
    expect(await screen.findByText("$215.00")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /new sale/i })).not.toBeInTheDocument();
  });

  it("processes a real refund through the general-purpose form", async () => {
    const user = userEvent.setup();
    signIn(["sales:read", "invoices:write"]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/api/v1/refunds`, () => HttpResponse.json(makeRefundPage([]))),
      http.post(`${BASE}/api/v1/refunds`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({});
      }),
    );
    renderWithProviders(<SalesPage />);

    await user.click(await screen.findByRole("tab", { name: "Refunds" }));
    expect(await screen.findByText("No refunds yet")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Process refund" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("combobox", { name: "Branch" }));
    await user.click(await screen.findByRole("option", { name: "Main Branch" }));
    await user.type(within(dialog).getByLabelText("Amount"), "20");
    await user.click(within(dialog).getByRole("button", { name: "Process refund" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect(created).toMatchObject({ amount: 20, method: "cash" });
  });

  it("shows the real Sales Reports summary", async () => {
    const user = userEvent.setup();
    signIn(["sales:read"]);
    renderWithProviders(<SalesPage />);

    await user.click(await screen.findByRole("tab", { name: "Reports" }));
    expect(await screen.findByText("Total revenue")).toBeInTheDocument();
    expect(screen.getByText("$1240.50")).toBeInTheDocument();
  });
});

describe("SalesOrderDetailPage (7J)", () => {
  it("shows the real order's identity, items, and confirms it", async () => {
    const user = userEvent.setup();
    signIn(["sales:read", "sales:write"]);
    let confirmed = false;
    server.use(
      http.get(`${BASE}/api/v1/sales-orders/:id`, () => HttpResponse.json(makeSalesOrder({ order_status: "draft" }))),
      http.post(`${BASE}/api/v1/sales-orders/:id/confirm`, () => {
        confirmed = true;
        return HttpResponse.json(makeSalesOrder({ order_status: "confirmed" }));
      }),
    );
    renderWithProviders(<SalesOrderDetailPage />);

    expect(await screen.findByText("Sales Order")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(confirmed).toBe(true));
  });

  it("surfaces a real insufficient_stock 409 from confirm without crashing the page", async () => {
    const user = userEvent.setup();
    signIn(["sales:read", "sales:write"]);
    let attempted = false;
    server.use(
      http.get(`${BASE}/api/v1/sales-orders/:id`, () => HttpResponse.json(makeSalesOrder({ order_status: "draft" }))),
      http.post(`${BASE}/api/v1/sales-orders/:id/confirm`, () => {
        attempted = true;
        return HttpResponse.json({ error: { code: "insufficient_stock", message: "Not enough stock to reserve this line." } }, { status: 409 });
      }),
    );
    renderWithProviders(<SalesOrderDetailPage />);

    await user.click(await screen.findByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(attempted).toBe(true));
    // The failed mutation never invalidates the order query, so the page
    // keeps rendering its pre-error state rather than crashing -- the
    // Confirm button (only shown while `order_status === "draft"`) is
    // still present.
    expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
  });

  it("shows the real Invoice panel once checkout has populated invoice_id, and records a payment", async () => {
    const user = userEvent.setup();
    signIn(["sales:read", "invoices:read", "invoices:write"]);
    let paymentBody: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/api/v1/sales-orders/:id`, () => HttpResponse.json(makeSalesOrder({ order_status: "fulfilled", invoice_id: makeInvoice().id }))),
      http.get(`${BASE}/api/v1/invoices/:id`, () => HttpResponse.json(makeInvoice({ total_amount: "108.00", amount_paid: "0.00" }))),
      http.post(`${BASE}/api/v1/invoices/:id/payments`, async ({ request }) => {
        paymentBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({});
      }),
    );
    renderWithProviders(<SalesOrderDetailPage />);

    expect(await screen.findByText(/Invoice INV-0001/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Record payment" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Amount"), "50");
    await user.click(within(dialog).getByRole("button", { name: "Record payment" }));

    await waitFor(() => expect(paymentBody).not.toBeNull());
    expect(paymentBody).toMatchObject({ amount: 50, method: "cash" });
  });
});

describe("SaleDetailPage (7J)", () => {
  it("requests a real return against a completed sale's line items", async () => {
    const user = userEvent.setup();
    signIn(["sales:read", "sales:write"]);
    let created: Record<string, unknown> | null = null;
    server.use(
      http.get(`${BASE}/api/v1/sales/:id`, () => HttpResponse.json(makeSale({ status: "completed" }))),
      http.post(`${BASE}/api/v1/sales/:sale_id/returns`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeReturn());
      }),
    );
    renderWithProviders(<SaleDetailPage />);

    await user.click(await screen.findByRole("button", { name: "Request return" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByLabelText(/Include line/));
    await user.click(within(dialog).getByRole("button", { name: "Request return" }));

    await waitFor(() => expect(created).not.toBeNull());
    expect((created as unknown as { items: unknown[] }).items).toHaveLength(1);
  });
});

describe("ReturnDetailPage (7J)", () => {
  it("approves a real requested return", async () => {
    const user = userEvent.setup();
    signIn(["sales:read", "sales:write"]);
    let approved = false;
    server.use(
      http.get(`${BASE}/api/v1/returns/:id`, () => HttpResponse.json(makeReturn({ status: "requested" }))),
      http.post(`${BASE}/api/v1/returns/:id/approve`, () => {
        approved = true;
        return HttpResponse.json(makeReturn({ status: "approved" }));
      }),
    );
    renderWithProviders(<ReturnDetailPage />);

    await user.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() => expect(approved).toBe(true));
  });

  it("completes a real approved return -- the sales:void-gated, inventory-restocking step", async () => {
    const user = userEvent.setup();
    signIn(["sales:read", "sales:void"]);
    let completed = false;
    server.use(
      http.get(`${BASE}/api/v1/returns/:id`, () => HttpResponse.json(makeReturn({ status: "approved" }))),
      http.post(`${BASE}/api/v1/returns/:id/complete`, () => {
        completed = true;
        return HttpResponse.json(makeReturn({ status: "completed" }));
      }),
    );
    renderWithProviders(<ReturnDetailPage />);

    await user.click(await screen.findByRole("button", { name: "Complete return" }));
    await waitFor(() => expect(completed).toBe(true));
  });

  it("does not show Complete return for a role missing sales:void", async () => {
    signIn(["sales:read", "sales:write"]);
    server.use(http.get(`${BASE}/api/v1/returns/:id`, () => HttpResponse.json(makeReturn({ status: "approved" }))));
    renderWithProviders(<ReturnDetailPage />);

    await screen.findByText("Return");
    expect(screen.queryByRole("button", { name: "Complete return" })).not.toBeInTheDocument();
  });
});
