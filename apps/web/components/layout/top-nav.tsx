"use client";

import { Menu, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { BranchSelector } from "@/components/layout/branch-selector";
import { NotificationCenter } from "@/components/layout/notification-center";
import { OrgContext } from "@/components/layout/org-context";
import { UserMenu } from "@/components/layout/user-menu";
import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { PermissionGate } from "@/components/auth/permission-gate";
import { useUiStore } from "@/store/ui-store";

/**
 * The persistent header: org context, branch selector, global search
 * trigger, AI Assistant trigger, notification bell, and the user menu --
 * everything the 7C kickoff's "TOP NAVIGATION" section calls for except
 * logout (which lives inside `UserMenu`, matching where a user actually
 * looks for it). `AssistantPanel` (7L) was added after 7C shipped, per
 * `nav-config.ts`'s docstring that AI Assistant is "deliberately NOT" a
 * sidebar destination -- "a persistent header overlay," the same category
 * as Notifications -- placed to its left so the two overlay triggers sit
 * together.
 *
 * The mobile hamburger (`tablet:hidden`) opens the same `mobileNavOpen`
 * Sheet state `components/layout/mobile-nav.tsx` renders from -- this
 * header never builds a second nav surface of its own for small screens.
 *
 * The search trigger only opens `useUiStore`'s `commandPaletteOpen` flag;
 * the actual search UI (`components/layout/global-search.tsx`) is
 * mounted once in `AppShell`, not per-trigger, so its own `⌘K`/`Ctrl+K`
 * keyboard listener and the header button both drive the same instance.
 */
export function TopNav() {
  const setMobileNavOpen = useUiStore((state) => state.setMobileNavOpen);
  const setCommandPaletteOpen = useUiStore((state) => state.setCommandPaletteOpen);

  return (
    <header className="sticky top-0 z-sticky flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-3 tablet:px-4 laptop:px-6">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="tablet:hidden"
        aria-label="Open navigation menu"
        onClick={() => setMobileNavOpen(true)}
      >
        <Menu className="size-5" aria-hidden="true" />
      </Button>

      <OrgContext />

      <div className="hidden tablet:block">
        <BranchSelector />
      </div>

      <button
        type="button"
        onClick={() => setCommandPaletteOpen(true)}
        aria-label="Search"
        className="ml-2 flex flex-1 max-w-sm items-center gap-2 rounded-md border border-input bg-transparent px-3 py-1.5 text-body-sm text-muted-foreground shadow-flat transition-colors duration-fast hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Search className="size-4 shrink-0" aria-hidden="true" />
        <span className="hidden truncate laptop:inline">Search plants, customers, inventory…</span>
        <kbd className="ml-auto hidden shrink-0 rounded border border-border bg-muted px-1.5 py-0.5 text-caption laptop:inline">
          ⌘K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-1">
        <PermissionGate permission="ai_assistant:use">
          <AssistantPanel />
        </PermissionGate>
        <NotificationCenter />
        <UserMenu />
      </div>
    </header>
  );
}
