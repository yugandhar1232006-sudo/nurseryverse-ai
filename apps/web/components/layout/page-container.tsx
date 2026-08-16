import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The one place page-level horizontal padding and max-width are defined,
 * per docs/design/04-responsive-design-specifications.md's per-breakpoint
 * content padding (Mobile 12px / Tablet 16px / Laptop 24px / Desktop
 * 32px -- Tailwind's `3`/`4`/`6`/`8` spacing steps map to those exactly)
 * and its ~1600px centered max-width at Desktop. Every authenticated page
 * should render its content through this rather than hand-rolling its own
 * padding, so a later global spacing change is a one-file edit.
 */
export function PageContainer({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("mx-auto w-full max-w-[1600px] px-3 py-4 tablet:px-4 laptop:px-6 desktop:px-8", className)}>
      {children}
    </div>
  );
}
