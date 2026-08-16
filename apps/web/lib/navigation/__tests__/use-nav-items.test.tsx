import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { isNavItemActive, useMobileTabItems, useNavItems } from "@/lib/navigation/use-nav-items";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

function signInWith(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }) });
}

describe("useNavItems (permission filtering)", () => {
  it("always shows Dashboard and Settings -- neither is permission-gated", () => {
    signInWith([]);
    const { result } = renderHook(() => useNavItems());
    const labels = result.current.map((item) => item.label);
    expect(labels).toContain("Dashboard");
    expect(labels).toContain("Settings");
  });

  it("hides a top-level item entirely when the required permission is missing (absence, not disabled)", () => {
    signInWith([]);
    const { result } = renderHook(() => useNavItems());
    expect(result.current.find((item) => item.id === "plants")).toBeUndefined();
    expect(result.current.find((item) => item.id === "inventory")).toBeUndefined();
  });

  it("shows a gated item once its permission is held", () => {
    signInWith(["inventory:read"]);
    const { result } = renderHook(() => useNavItems());
    expect(result.current.find((item) => item.id === "inventory")).toBeDefined();
  });

  it("drops a parent's children before the parent itself is even considered, if the parent's own gate fails", () => {
    // species:read alone (no plants:read) should never surface "Plants" or its "Species Catalog" child --
    // every child route lives under /plants, which requires plants:read.
    signInWith(["species:read"]);
    const { result } = renderHook(() => useNavItems());
    expect(result.current.find((item) => item.id === "plants")).toBeUndefined();
  });

  it("shows Plants with only the permitted child when holding plants:read but not species:read", () => {
    signInWith(["plants:read"]);
    const { result } = renderHook(() => useNavItems());
    const plants = result.current.find((item) => item.id === "plants");
    expect(plants).toBeDefined();
    expect(plants?.children?.map((c) => c.id)).toEqual(["plants-all"]);
  });

  it("shows both Plants children when holding both plants:read and species:read", () => {
    signInWith(["plants:read", "species:read"]);
    const { result } = renderHook(() => useNavItems());
    const plants = result.current.find((item) => item.id === "plants");
    expect(plants?.children?.map((c) => c.id)).toEqual(["plants-all", "plants-species"]);
  });

  it("fails closed (shows nothing gated) while signed out / resolving", () => {
    useSessionStore.setState({ status: "resolving", user: null });
    const { result } = renderHook(() => useNavItems());
    expect(result.current.find((item) => item.id === "plants")).toBeUndefined();
    // Ungated items are still present -- there's no user-specific reason to hide them.
    expect(result.current.find((item) => item.id === "dashboard")).toBeDefined();
  });
});

describe("isNavItemActive", () => {
  it("matches the Dashboard route only on an exact '/' -- never as a prefix", () => {
    expect(isNavItemActive("/", "/")).toBe(true);
    expect(isNavItemActive("/plants", "/")).toBe(false);
  });

  it("matches an exact non-root route", () => {
    expect(isNavItemActive("/plants", "/plants")).toBe(true);
  });

  it("matches a nested child route as a path-segment prefix", () => {
    expect(isNavItemActive("/plants/123", "/plants")).toBe(true);
  });

  it("does not match a route that merely starts with the same characters but isn't a path segment", () => {
    expect(isNavItemActive("/plants-archive", "/plants")).toBe(false);
  });
});

describe("useMobileTabItems", () => {
  it("filters the mobile bottom-tab set by the same permission codes", () => {
    signInWith(["plants:read"]);
    const { result } = renderHook(() => useMobileTabItems());
    const ids = result.current.map((item) => item.id);
    expect(ids).toContain("dashboard");
    expect(ids).toContain("plants");
    expect(ids).not.toContain("watering"); // requires watering:read, not held
    expect(ids).toContain("notifications"); // never gated
  });

  it("includes Watering once watering:read is held", () => {
    signInWith(["watering:read"]);
    const { result } = renderHook(() => useMobileTabItems());
    expect(result.current.map((item) => item.id)).toContain("watering");
  });
});
