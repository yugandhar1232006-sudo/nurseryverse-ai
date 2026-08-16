import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { BranchSelector } from "@/components/layout/branch-selector";
import { useSessionStore } from "@/store/session-store";
import { useBranchContextStore } from "@/store/branch-context-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeBranch } from "@/test/fixtures/shell";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

function signIn() {
  useSessionStore.setState({ status: "authenticated", user: makeMe() });
}

describe("BranchSelector", () => {
  it("renders nothing for a brand-new org with zero branches (no context to switch, not a broken dropdown)", async () => {
    server.use(http.get(`${BASE}/api/v1/branches`, () => HttpResponse.json([])));
    signIn();
    const { container } = renderWithProviders(<BranchSelector />);

    // Let the loading skeleton resolve before asserting on the settled (empty) state.
    await waitFor(() => expect(container.querySelector('[data-slot="skeleton"]')).not.toBeInTheDocument());
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("renders the single branch as static text, not an interactive dropdown, when there's exactly one", async () => {
    server.use(http.get(`${BASE}/api/v1/branches`, () => HttpResponse.json([makeBranch({ name: "Downtown Branch" })])));
    signIn();
    renderWithProviders(<BranchSelector />);

    expect(await screen.findByText("Downtown Branch")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("renders a real Select with every branch once there are 2+", async () => {
    server.use(
      http.get(`${BASE}/api/v1/branches`, () =>
        HttpResponse.json([makeBranch({ id: "b-1", name: "Downtown" }), makeBranch({ id: "b-2", name: "Uptown" })]),
      ),
    );
    signIn();
    renderWithProviders(<BranchSelector />);

    const trigger = await screen.findByRole("combobox", { name: "Select branch" });
    expect(trigger).toHaveTextContent("Downtown"); // auto-selects the first real branch
  });

  it("never trusts a stale/invalid persisted branch id -- falls back to a real branch instead", async () => {
    useBranchContextStore.setState({ selectedBranchId: "does-not-exist-anymore" });
    server.use(
      http.get(`${BASE}/api/v1/branches`, () =>
        HttpResponse.json([makeBranch({ id: "b-1", name: "Downtown" })]),
      ),
    );
    signIn();
    renderWithProviders(<BranchSelector />);

    expect(await screen.findByText("Downtown")).toBeInTheDocument();
  });
});
