import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import { OrgContext } from "@/components/layout/org-context";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeOrganization } from "@/test/fixtures/shell";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

describe("OrgContext", () => {
  it("renders nothing while there is no org_id yet (mid-signup)", () => {
    useSessionStore.setState({ status: "authenticated", user: makeMe({ org_id: null }) });
    const { container } = renderWithProviders(<OrgContext />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a loading skeleton, then the real organization name from GET /orgs/{id}", async () => {
    server.use(http.get(`${BASE}/api/v1/orgs/:id`, () => HttpResponse.json(makeOrganization({ name: "Green Thumb Nursery" }))));
    useSessionStore.setState({ status: "authenticated", user: makeMe({ org_id: "22222222-2222-2222-2222-222222222222" }) });
    renderWithProviders(<OrgContext />);

    expect(await screen.findByText("Green Thumb Nursery")).toBeInTheDocument();
  });

  it("never renders a picker/switcher -- this is real backend org context, not a fabricated org list", async () => {
    server.use(http.get(`${BASE}/api/v1/orgs/:id`, () => HttpResponse.json(makeOrganization())));
    useSessionStore.setState({ status: "authenticated", user: makeMe() });
    renderWithProviders(<OrgContext />);

    await waitFor(() => expect(screen.queryByRole("combobox")).not.toBeInTheDocument());
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
