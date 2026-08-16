"use client";

import type { ReactNode } from "react";

import { Breadcrumbs } from "@/components/layout/breadcrumbs";
import { EmailVerificationBanner } from "@/components/layout/email-verification-banner";
import { GlobalSearch } from "@/components/layout/global-search";
import { MobileNavSheet, MobileTabBar } from "@/components/layout/mobile-nav";
import { PageContainer } from "@/components/layout/page-container";
import { Sidebar } from "@/components/layout/sidebar";
import { TopNav } from "@/components/layout/top-nav";
import { useSession } from "@/lib/auth/use-session";

export interface AppShellProps {
  children: ReactNode;
  /** Passed through to `Breadcrumbs` for detail pages that know a real resource name -- see `useBreadcrumbs`'s docstring. */
  breadcrumbDynamicLabels?: Record<string, string>;
}

/**
 * The complete authenticated application shell, per the 7C kickoff:
 * `Sidebar` (desktop/tablet persistent nav) + `TopNav` (org/branch
 * context, search, notifications, user menu) + `Breadcrumbs` +
 * `PageContainer`-wrapped page content, plus the mobile-only surfaces
 * (`MobileTabBar`, `MobileNavSheet`) and the single shared
 * `GlobalSearch` overlay instance.
 *
 * `app/(app)/layout.tsx` owns the actual auth gate (redirect-if-signed-
 * out, the resolving-state skeleton) and renders this only once that
 * gate has passed -- this component assumes an authenticated session and
 * does not re-check it, except for the email verification banner, which
 * reads `useSession()` directly the same way 7B's `AppLayout` did.
 *
 * `pb-16 tablet:pb-0` on `<main>` reserves room for the fixed
 * `MobileTabBar` below the `tablet` breakpoint so it never overlaps the
 * last bit of page content -- the bar itself is `tablet:hidden`, so this
 * padding only ever matters exactly when the bar is actually on screen.
 */
export function AppShell({ children, breadcrumbDynamicLabels }: AppShellProps) {
  const { user } = useSession();

  return (
    <div className="flex min-h-screen">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-toast focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to main content
      </a>

      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopNav />
        {user && !user.is_email_verified && <EmailVerificationBanner />}

        <main id="main-content" className="flex-1 pb-16 tablet:pb-0">
          <PageContainer className="py-3 tablet:py-4">
            <Breadcrumbs dynamicLabels={breadcrumbDynamicLabels} className="mb-3" />
            {children}
          </PageContainer>
        </main>
      </div>

      <MobileTabBar />
      <MobileNavSheet />
      <GlobalSearch />
    </div>
  );
}
