"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Package, Search, Sprout, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useSession } from "@/lib/auth/use-session";
import { useGlobalSearch, type SearchResult, type SearchResultKind } from "@/lib/search/use-global-search";
import { useUiStore } from "@/store/ui-store";
import { cn } from "@/lib/utils";

const KIND_ICON: Record<SearchResultKind, LucideIcon> = {
  plant: Sprout,
  species: Sprout,
  customer: Users,
  inventory: Package,
};

const KIND_LABEL: Record<SearchResultKind, string> = {
  plant: "Plant",
  species: "Species",
  customer: "Customer",
  inventory: "Inventory",
};

/**
 * Global command-palette-style search, per the 7C kickoff's "Build the
 * global search interface according to the existing UX specification.
 * Support the real backend search capabilities where available. Do not
 * create fake search results." -- every result on screen comes straight
 * from `useGlobalSearch`'s real fan-out across `/plants`, `/species`,
 * `/customers`, `/inventory` (`lib/search/api.ts`); there is no mock/demo
 * data path anywhere in this component.
 *
 * Built on `@radix-ui/react-dialog` directly (same primitive as
 * `components/ui/dialog.tsx`/`sheet.tsx`) since no `cmdk` dependency is
 * installed -- confirmed absent from package.json during research for
 * this phase. This gets the same focus trap, Escape-to-close, and focus
 * restoration Radix Dialog already provides, without a new dependency.
 *
 * A single instance is mounted once in `AppShell` (not per-trigger) so
 * the global `⌘K`/`Ctrl+K` shortcut and the header's search button both
 * open the same dialog via `useUiStore`'s shared `commandPaletteOpen`
 * flag.
 */
export function GlobalSearch() {
  const router = useRouter();
  const open = useUiStore((state) => state.commandPaletteOpen);
  const setOpen = useUiStore((state) => state.setCommandPaletteOpen);
  const { isAuthenticated } = useSession();

  const [rawQuery, setRawQuery] = React.useState("");
  const [activeIndex, setActiveIndex] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const { items, isLoading, isError, error, isQueryValid, hasAnySearchPermission } = useGlobalSearch(rawQuery);

  // Global ⌘K / Ctrl+K shortcut -- only wired while authenticated, since
  // the shell (and this component) only ever mounts inside the
  // authenticated route group.
  React.useEffect(() => {
    if (!isAuthenticated) return;
    function handleKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isAuthenticated, setOpen]);

  // `open` is a shared boolean in `useUiStore` that THREE independent
  // call sites can flip to true: this component's own `⌘K` listener,
  // Radix's own Escape/overlay-click close, and -- critically --
  // `TopNav`'s search button, which calls `setCommandPaletteOpen(true)`
  // directly rather than through any handler defined here. An earlier
  // version of this reset lived in a single "handleOpenChange" wrapper
  // passed to the Dialog's `onOpenChange`, which meant opening via the
  // header button silently skipped the reset -- a real bug (caught by
  // this component's own tests), not just a style preference.
  //
  // The fix is React's own documented pattern for "reset state when a
  // value changes": compare the prop/store value against a ref of its
  // previous value *during render* (not inside a `useEffect`, which is
  // what the lint's `set-state-in-effect` rule is warning against) and
  // call `setState` conditionally right there. This reacts to `open`
  // itself, so it fires correctly no matter which of the three call
  // sites caused the transition.
  const [prevOpen, setPrevOpen] = React.useState(open);
  if (prevOpen !== open) {
    setPrevOpen(open);
    if (open) {
      setRawQuery("");
      setActiveIndex(0);
    }
  }

  // Imperative focus (not a state update, so it's outside the pattern
  // above) still needs an effect: Radix moves focus into the dialog
  // content on open, but the input itself needs an explicit focus once
  // it's actually mounted in the DOM.
  React.useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Clamped at read-time instead of reset via a second effect keyed on
  // `items` -- `activeIndex` itself only ever advances/wraps through
  // user keystrokes (`handleKeyDown` below); this derived value is what
  // every render actually uses, so a shrinking result set can never
  // point past the end of the list without a dedicated "resync on
  // `items` change" effect.
  const safeActiveIndex = items.length === 0 ? 0 : Math.min(activeIndex, items.length - 1);

  function navigateTo(result: SearchResult) {
    setOpen(false);
    router.push(result.href);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (items.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((safeActiveIndex + 1) % items.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((safeActiveIndex - 1 + items.length) % items.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const target = items[safeActiveIndex];
      if (target) navigateTo(target);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        showCloseButton={false}
        className="top-[20%] max-w-xl translate-y-0 gap-0 overflow-hidden p-0"
        aria-describedby={undefined}
      >
        <DialogTitle className="sr-only">Search</DialogTitle>

        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded={items.length > 0}
            aria-controls="global-search-results"
            aria-activedescendant={items[safeActiveIndex] ? `global-search-result-${items[safeActiveIndex].id}` : undefined}
            autoComplete="off"
            value={rawQuery}
            onChange={(e) => setRawQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search plants, species, customers, inventory…"
            className="flex-1 border-none bg-transparent text-body outline-none placeholder:text-muted-foreground"
          />
        </div>

        <div id="global-search-results" role="listbox" className="max-h-80 overflow-y-auto p-2">
          {!hasAnySearchPermission ? (
            <EmptyState
              icon={Search}
              title="Nothing to search yet"
              description="Your current role doesn't have access to any searchable records."
            />
          ) : !isQueryValid ? (
            <p className="px-3 py-6 text-center text-body-sm text-muted-foreground">
              Type at least 2 characters to search.
            </p>
          ) : isLoading ? (
            <div className="flex flex-col gap-2 p-1">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full rounded-md" />
              ))}
            </div>
          ) : isError ? (
            <ErrorState error={error} />
          ) : items.length === 0 ? (
            <EmptyState icon={Search} title="No results" description={`Nothing matched "${rawQuery.trim()}".`} />
          ) : (
            <ul className="flex flex-col gap-0.5">
              {items.map((result, index) => {
                const Icon = KIND_ICON[result.kind];
                const isActive = index === safeActiveIndex;
                return (
                  <li key={`${result.kind}-${result.id}`} id={`global-search-result-${result.id}`} role="option" aria-selected={isActive}>
                    <button
                      type="button"
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => navigateTo(result)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left transition-colors duration-fast",
                        isActive ? "bg-accent text-accent-foreground" : "hover:bg-muted",
                      )}
                    >
                      <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <span className="flex-1 truncate text-body-sm">
                        {result.title}
                        {result.subtitle && <span className="ml-2 text-muted-foreground">{result.subtitle}</span>}
                      </span>
                      <span className="shrink-0 text-caption text-muted-foreground">{KIND_LABEL[result.kind]}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
