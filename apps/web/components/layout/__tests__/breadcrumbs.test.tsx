import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { Breadcrumbs } from "@/components/layout/breadcrumbs";

const { mockUsePathname } = vi.hoisted(() => ({ mockUsePathname: vi.fn() }));

vi.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

describe("Breadcrumbs", () => {
  it("renders nothing on the Dashboard route (a single crumb is noise, not navigation)", () => {
    mockUsePathname.mockReturnValue("/");
    const { container } = render(<Breadcrumbs />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a real accessible nav landmark with the full trail for a nested route", () => {
    mockUsePathname.mockReturnValue("/plants/species");
    render(<Breadcrumbs />);

    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(nav).toBeInTheDocument();

    // Ancestor crumbs are real links...
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Plants" })).toHaveAttribute("href", "/plants");

    // ...the current page is plain text with aria-current, not a link.
    const current = screen.getByText("Species Catalog");
    expect(current).toHaveAttribute("aria-current", "page");
    expect(current.tagName).not.toBe("A");
  });
});
