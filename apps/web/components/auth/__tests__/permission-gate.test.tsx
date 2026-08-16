import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PermissionGate } from "@/components/auth/permission-gate";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";

function setPermissions(permissions: string[]) {
  useSessionStore.setState({ user: makeMe({ permissions }), status: "authenticated" });
}

describe("PermissionGate", () => {
  it("renders children when the user has the required single permission", () => {
    setPermissions(["roles:manage"]);
    render(<PermissionGate permission="roles:manage">Admin panel</PermissionGate>);
    expect(screen.getByText("Admin panel")).toBeInTheDocument();
  });

  it("renders nothing (no fallback given) when the user lacks the required permission", () => {
    setPermissions(["plants:read"]);
    render(<PermissionGate permission="roles:manage">Admin panel</PermissionGate>);
    expect(screen.queryByText("Admin panel")).not.toBeInTheDocument();
  });

  it("renders the fallback when the check fails and a fallback is supplied", () => {
    setPermissions([]);
    render(
      <PermissionGate permission="roles:manage" fallback={<span>No access</span>}>
        Admin panel
      </PermissionGate>,
    );
    expect(screen.getByText("No access")).toBeInTheDocument();
    expect(screen.queryByText("Admin panel")).not.toBeInTheDocument();
  });

  it("anyOf: renders children when the user has at least one of the listed permissions", () => {
    setPermissions(["employees:write"]);
    render(
      <PermissionGate anyOf={["roles:manage", "employees:write"]}>Admin badge</PermissionGate>,
    );
    expect(screen.getByText("Admin badge")).toBeInTheDocument();
  });

  it("anyOf: renders nothing when the user has none of the listed permissions", () => {
    setPermissions(["plants:read"]);
    render(
      <PermissionGate anyOf={["roles:manage", "employees:write"]}>Admin badge</PermissionGate>,
    );
    expect(screen.queryByText("Admin badge")).not.toBeInTheDocument();
  });

  it("allOf: renders children only when the user has every listed permission", () => {
    setPermissions(["plants:read", "plants:write"]);
    const { rerender } = render(
      <PermissionGate allOf={["plants:read", "plants:write"]}>Full plant access</PermissionGate>,
    );
    expect(screen.getByText("Full plant access")).toBeInTheDocument();

    setPermissions(["plants:read"]);
    rerender(<PermissionGate allOf={["plants:read", "plants:write"]}>Full plant access</PermissionGate>);
    expect(screen.queryByText("Full plant access")).not.toBeInTheDocument();
  });

  it("fails closed (denies) when there is no authenticated user at all", () => {
    useSessionStore.setState({ user: null, status: "unauthenticated" });
    render(<PermissionGate permission="plants:read">Should be hidden</PermissionGate>);
    expect(screen.queryByText("Should be hidden")).not.toBeInTheDocument();
  });
});
