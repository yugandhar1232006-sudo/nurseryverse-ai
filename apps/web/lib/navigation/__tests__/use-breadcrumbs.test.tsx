import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { useBreadcrumbs } from "@/lib/navigation/use-breadcrumbs";

const { mockUsePathname } = vi.hoisted(() => ({ mockUsePathname: vi.fn() }));

vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

describe("useBreadcrumbs", () => {
  it("returns a single, current Dashboard crumb at the root", () => {
    mockUsePathname.mockReturnValue("/");
    const { result } = renderHook(() => useBreadcrumbs());
    expect(result.current).toEqual([{ label: "Dashboard", href: "/", isCurrent: true }]);
  });

  it("resolves a nav-mapped segment to its real label", () => {
    mockUsePathname.mockReturnValue("/plants");
    const { result } = renderHook(() => useBreadcrumbs());
    expect(result.current).toEqual([
      { label: "Dashboard", href: "/", isCurrent: false },
      { label: "Plants", href: "/plants", isCurrent: true },
    ]);
  });

  it("builds a full trail for a nested nav-mapped route", () => {
    mockUsePathname.mockReturnValue("/plants/species");
    const { result } = renderHook(() => useBreadcrumbs());
    expect(result.current).toEqual([
      { label: "Dashboard", href: "/", isCurrent: false },
      { label: "Plants", href: "/plants", isCurrent: false },
      { label: "Species Catalog", href: "/plants/species", isCurrent: true },
    ]);
  });

  it("falls back to a title-cased label for an unmapped segment rather than rendering blank", () => {
    mockUsePathname.mockReturnValue("/account");
    const { result } = renderHook(() => useBreadcrumbs());
    expect(result.current[1]).toEqual({ label: "Account", href: "/account", isCurrent: true });
  });

  it("title-cases a hyphenated unmapped segment", () => {
    mockUsePathname.mockReturnValue("/ai-center");
    const { result } = renderHook(() => useBreadcrumbs());
    // ai-center IS nav-mapped ("AI Center"); use a genuinely unmapped hyphenated segment instead.
    mockUsePathname.mockReturnValue("/some-detail-page");
    const { result: result2 } = renderHook(() => useBreadcrumbs());
    expect(result2.current[1]).toEqual({ label: "Some Detail Page", href: "/some-detail-page", isCurrent: true });
    expect(result.current[1].label).toBe("AI Center");
  });

  it("lets dynamicLabels override a specific segment with a real resource name", () => {
    mockUsePathname.mockReturnValue("/plants/abc-123");
    const { result } = renderHook(() => useBreadcrumbs({ "abc-123": "Ficus Lyrata #FLY-0142" }));
    expect(result.current[2]).toEqual({
      label: "Ficus Lyrata #FLY-0142",
      href: "/plants/abc-123",
      isCurrent: true,
    });
  });
});
