# Application Shell — Phase 7C

Everything an authenticated user sees around their actual page content: sidebar, top navigation, breadcrumbs, global search, notification center, and the mobile equivalents of each. Every data-bearing piece of the shell talks to a real, already-implemented backend route — there is no mock business data, no fake search results, and no second notification system anywhere in this phase.

## Architecture

```
components/layout/app-shell.tsx        orchestrates everything below; rendered once by app/(app)/layout.tsx
components/layout/sidebar.tsx          desktop/tablet persistent nav (hidden below `tablet`)
components/layout/sidebar-nav-item.tsx a single nav link, one level of nested children, tooltip when collapsed
components/layout/top-nav.tsx          org context, branch selector, search trigger, notification bell, user menu
components/layout/org-context.tsx      real org name/logo from GET /orgs/{id} -- context, not a picker
components/layout/branch-selector.tsx  real GET /branches; static text / Select depending on branch count
components/layout/breadcrumbs.tsx      presentational; consumes lib/navigation/use-breadcrumbs.ts
components/layout/mobile-nav.tsx       MobileTabBar (bottom, mobile-only) + MobileNavSheet ("More" drawer)
components/layout/notification-center.tsx  bell trigger + panel; REST + WebSocket, real Module 11 backend
components/layout/global-search.tsx    ⌘K command palette; real per-entity search endpoints, no cmdk dependency
components/layout/user-menu.tsx        identity, Admin badge (permission-gated), Settings, Sign out
components/layout/page-container.tsx   the one place page padding/max-width is defined
components/layout/coming-soon.tsx      honest "not built yet" placeholder for real, permission-checked routes
components/layout/permission-denied.tsx    shown for a direct URL hit on a route the user can't access

lib/navigation/nav-config.ts           NAV_ITEMS / MOBILE_TAB_ITEMS -- the one source of truth for nav structure
lib/navigation/use-nav-items.ts        permission filtering + active-route detection
lib/navigation/use-breadcrumbs.ts      route-based breadcrumb generation

lib/shell/queries.ts                   useOrganizationQuery / useBranchesQuery (TanStack Query)
lib/shell/use-current-branch.ts        reconciles the persisted branch preference against real backend data
store/branch-context-store.ts          persisted branch *preference* only -- never an authorization decision

lib/notifications/queries.ts           useNotificationsQuery / useUnreadCountQuery
lib/notifications/mutations.ts         useMarkNotificationReadMutation / useMarkAllReadMutation
lib/notifications/use-notification-socket.ts   the real Module 11 WebSocket hub, with reconnect/backoff

lib/search/api.ts                      thin read-only wrappers around real /plants, /species, /customers, /inventory
lib/search/use-global-search.ts        permission-gated fan-out across those four endpoints, debounced

store/ui-store.ts                      sidebarCollapsed, mobileNavOpen, commandPaletteOpen, notificationCenterOpen
```

`AppShell` is a thin composition layer: `Sidebar` + `TopNav` + `Breadcrumbs` + `PageContainer`-wrapped `children`, plus the mobile-only surfaces and one shared `GlobalSearch` instance. `app/(app)/layout.tsx` still owns the actual auth gate (unchanged from 7B) and renders `AppShell` only once that gate has passed.

## Navigation structure

`lib/navigation/nav-config.ts`'s `NAV_ITEMS` is the single source of truth the sidebar, the mobile "More" sheet, and breadcrumb-label resolution all read from — there is no second, hand-maintained nav list anywhere. Every `permission`/`anyOf` on an item is a real, seeded permission code (`migrations/versions/0002_seed_system_metadata.py`), never an invented string.

Two real backend gaps are deliberately excluded, not silently papered over: **Invoices** and **Suppliers** have seeded permission codes (`invoices:read/write/void`, `purchase_orders:read/write/receive`) but no backend route file exists for either (confirmed by direct inspection of `apps/api/app/api/routes/` — no `invoices.py`, `suppliers.py`, or `purchase_orders.py`). Linking to a page that could never load real data would be exactly the "fake" navigation this phase's kickoff prohibited, so these have no sidebar entry at all.

`Plants` nests `Species Catalog` as the one real example of nested navigation (`plants:read` / `species:read`, both real). Notifications and global search are header overlays, not sidebar destinations, per the UX doc. Mobile's bottom tab bar (`MOBILE_TAB_ITEMS`) is a separate, shorter list (Dashboard, Plants, Watering, Alerts) — Watering has no desktop sidebar entry at all (it lives inside the Plant Digital Twin's tabs in a later phase) but is a real, permission-checked route reachable from the field-workflow-oriented mobile tab bar.

**Permission filtering** (`lib/navigation/use-nav-items.ts`) is recursive: a parent with its own gate is dropped *before* its children are even considered (there's no case where a user can see a `Plants` child without `plants:read`, since every child route lives under `/plants`); a parent with no gate whose children are all denied still renders, sans children. This is UX-only — a hidden item is a convenience, never the security boundary. Every one of the nine placeholder pages this phase created (`/plants`, `/plants/species`, `/ai-center`, `/inventory`, `/sales`, `/customers`, `/reports`, `/watering`, and the ungated `/settings`) independently re-checks its own permission via `<PermissionGate>` and renders `PermissionDenied` on failure — so a direct URL hit, a stale bookmark, or a shared link from a since-demoted teammate never shows a blank screen or the "coming soon" placeholder a genuinely permitted user would see.

**Placeholder pages, not missing ones**: 7D–7O haven't been built yet, so every real nav destination that isn't Dashboard/Settings/Account renders `ComingSoon` — an honest "this hasn't shipped yet" `EmptyState`, never fake data standing in for real data. This also fixed a real gap this phase found: `app/page.tsx` was still the unmodified `create-next-app` boilerplate template, sitting *outside* the `(app)` route group — meaning `/`, the actual post-login redirect target, had no auth guard or shell chrome at all before this phase. It's deleted; `app/(app)/page.tsx` is the real, protected Dashboard route now.

## Permission handling

Nothing new architecturally beyond `05-permission-aware-ui.md` and 7B's `<PermissionGate>` — this phase is simply its most thorough consumer yet: nav filtering, the Admin badge in `UserMenu`, every placeholder page's own gate, and `lib/search/use-global-search.ts`'s per-entity permission checks (a user without `customers:read` never fires, and never sees results from, a customer search — same "hidden, not disabled" rule applied to search as to navigation). The backend re-authorizes every request regardless of what any of this renders.

## Organization / branch context

**Organization**: `OrgContext` shows the real org name/logo from `GET /orgs/{id}` — deliberately *context*, not a switcher. `create_organization` (Module 4) enforces one organization per user server-side, and there is no "list my organizations" or "switch organization" endpoint to build a picker against. A picker here would be UI for a capability that doesn't exist; this is a scope decision matching the real backend contract, not a missing feature.

**Branch**: `BranchSelector` renders nothing for a brand-new org with zero branches, static text for exactly one (a one-option dropdown is noise), and a real `Select` for two or more — backed by `GET /branches`. The selected branch is a two-layer system: `store/branch-context-store.ts` holds only the *persisted preference* (an id, not a credential — safe to keep in localStorage like `sidebarCollapsed`), and `lib/shell/use-current-branch.ts` is the enforcement point that validates that preference against the real `GET /branches` response on every read. A stale id (switched accounts, an archived branch, a hand-edited localStorage value) fails that check and falls back to the first real branch — it is never trusted as an authorization decision. Every branch-scoped request this preference eventually drives (starting in later phases) still carries its own `branch_id` that the backend independently re-authorizes; nothing client-selected is ever proof of access.

## Notification integration

Integrates the real Module 11 backend end to end, with no second notification system:

- **Initial load**: `GET /notifications` (paginated) + `GET /notifications/unread-count` via TanStack Query.
- **Live updates**: `lib/notifications/use-notification-socket.ts` opens `GET /api/v1/notifications/ws?token=<access_token>` — the token goes as a query parameter because browsers cannot set an `Authorization` header on a WebSocket handshake; this is the backend's actual, already-implemented contract, not a workaround invented here. Frame shapes (`{"type": "notification", "notification": {...}, "unread_count": n}` and `{"type": "unread_count", "unread_count": n}`) were read directly from `apps/api/app/notifications/notification_handler.py`, not guessed. Exponential backoff (1s → 30s cap) on an unexpected close; the effect tears down and reopens cleanly whenever the access token changes (e.g. after a silent refresh).
- **Store as single source of truth**: `useNotificationStore` (built in 7A) is what the panel actually renders once the first REST page has seeded it; the socket pushes incremental updates into that same store rather than maintaining a second list. A pushed frame never includes `nursery_id`/`recipient_user_id` — these are filled from the real, current session snapshot (the hub only ever pushes to the current user, scoped to their own org), not left blank or fabricated.
- **Shared open state, one panel**: `useUiStore`'s `notificationCenterOpen` (not a local `useState`) means the header bell and the mobile bottom tab bar's "Alerts" button open the exact same panel instance — never two competing notification UIs.
- **Mark read / mark all read**: real `PATCH /notifications/{id}/read` and `POST /notifications/mark-all-read`, updating the store directly on success (the hub also pushes its own `unread_count` frame for this same action, so this is belt-and-suspenders for a momentarily-disconnected socket, not the only path). Clicking a notification with a `deep_link` navigates there for real.

## Responsive behavior

Verified against `docs/design/04-responsive-design-specifications.md`'s breakpoints (`tablet`/`laptop`/`desktop` custom Tailwind variants, already defined in `app/globals.css` from 7A) and per-breakpoint content padding, all applied through the one `PageContainer`:

- **Desktop / Laptop** (≥1024px): persistent `Sidebar`, expand/collapse toggle (`useUiStore`'s `sidebarCollapsed`, persisted), icon+label when expanded, icon-only rail with tooltips when collapsed.
- **Tablet** (640–1023px): same persistent `Sidebar` component (it's `hidden` only below `tablet`, not specifically tablet-collapsed by default — this is a deliberate simplification from a separate tablet-drawer mode: the icon-rail collapse toggle already covers the "less horizontal room" case without a third distinct nav pattern).
- **Mobile** (<640px): the desktop `Sidebar` is fully hidden (`display: none`, removed from the accessibility tree too) and replaced entirely by `MobileTabBar` (fixed bottom, 4 items) plus `MobileNavSheet` (a left-side `Sheet` reachable from `TopNav`'s hamburger button, carrying the full permitted nav tree for anything not in the 4-item bottom set).
- **Header**: `TopNav` itself is present at every breakpoint (org context, search, bell, user menu never disappear), with the search box's placeholder text and keyboard-shortcut hint progressively hidden below `laptop` to keep the header from overflowing on narrow screens.
- **Breadcrumbs**: hidden entirely on the Dashboard route (a single crumb is noise); on narrow viewports, earlier ancestor crumbs collapse (`hidden tablet:flex`) so only the immediate parent and current page show, rather than wrapping or overflowing.

## Accessibility

- **Semantic landmarks**: `<nav aria-label="Primary">` on both the desktop `Sidebar` and mobile `MobileTabBar` (never both visible at once, since one is `display:none` whenever the other renders); `<nav aria-label="More navigation">` on the mobile sheet's tree (distinct name, since it *can* be in the DOM simultaneously with the tab bar while open); `<nav aria-label="Breadcrumb">` for the trail.
- **Keyboard navigation**: `GlobalSearch` supports `ArrowUp`/`ArrowDown` to move selection and `Enter` to navigate, with `role="combobox"`/`aria-activedescendant` wiring; `⌘K`/`Ctrl+K` opens it from anywhere in the shell.
- **Focus management / restoration / Escape**: inherited from Radix's `Dialog`/`Sheet` primitives everywhere they're used (notification panel, mobile nav drawer, global search) — focus trap, Escape-to-close, and focus restoration on close all come from the same primitive `components/ui/dialog.tsx` already established in 7A, not reimplemented per component.
- **Screen-reader labels**: every icon-only control (`Sidebar`'s collapse toggle, `TopNav`'s hamburger and search button, `NotificationCenter`'s bell) has an explicit `aria-label`. **A real defect found and fixed here**: the collapsed sidebar's nav links had no visible label text and relied solely on a hover/focus tooltip — but a tooltip only ever wires up `aria-describedby` (a *description*), not an accessible *name* (WCAG 4.1.2), so a screen-reader user got nothing. Fixed by adding an explicit, unconditional `aria-label={item.label}` in `sidebar-nav-item.tsx`.
- **Reduced motion**: covered globally (from 7A) by `app/globals.css`'s `prefers-reduced-motion` media query, which every `animate-in`/`animate-out` class this phase's new components use already flows through — no per-component opt-in needed.

## UI states

Every shell component that fetches data handles loading / empty / error / offline explicitly, never a blank screen: `Sidebar` and `MobileTabBar` show skeletons while the session resolves; `OrgContext` and `BranchSelector` show skeletons then resolve to real data or a correctly-empty render (no org yet, no branches yet); `NotificationCenter` and `GlobalSearch` both handle loading (skeleton rows), empty (`EmptyState`), error (`ErrorState` with retry), and results explicitly, and `NotificationCenter` additionally surfaces the WebSocket's own connection status ("Reconnecting…" / "Offline") in its header. Unauthorized/permission-denied is `PermissionDenied` on every gated placeholder page, distinct from the "not built yet" `ComingSoon` state a genuinely permitted user sees for the same route.

## Testing

**Vitest + React Testing Library**: 124 tests across 21 files (all passing), covering every item the kickoff listed: sidebar rendering/active-route/permission-filtering/collapse, mobile navigation (tab bar filtering, shared notification-panel trigger, "More" sheet), breadcrumb generation (root/nested/unmapped-fallback/`dynamicLabels` override), organization context (loading/empty/populated, never a picker), branch selector (zero/one/many branches, stale-id fallback), user menu (identity, permission-gated Admin badge, logout), notification center (unread badge, list, mark-read, mark-all-read, empty, error, real deep-link navigation), a dedicated WebSocket suite (`use-notification-socket.test.ts` — open/message/close/reconnect-backoff/teardown, using a `MockWebSocket` test double since jsdom's own `WebSocket` is unimplemented), global search (permission-scoped fan-out, debounced minimum-length, keyboard navigation, real result rendering, reopen-resets-query), and the existing 7A/7B suites, all still green (no regressions).

**Playwright** (`e2e/shell.spec.ts`, plus updated assertions in `e2e/auth.spec.ts` where 7B's tests referenced the now-retired `AppHeader`): login → shell, sidebar navigation + active-route marking, breadcrumb presence/absence, direct-URL permission-denied handling, org/branch context correctly rendering nothing for an org-less test account, notification panel open + empty state, global search open via button and `Ctrl+K`, logout via the user menu, and a mobile-viewport suite (bottom tab bar, "More" sheet, Alerts panel). `npx playwright test --list` confirms both spec files parse and collect all 19 tests correctly.

**This suite could not be execution-verified in this environment** — no `docker`/Postgres here (confirmed via a live `:8000`/`:3000`/`:5432` connection probe, all refused), the same disclosed constraint on record since Module 14 and 7B. Written and reviewed against the real backend routes and the real components in this repo, not executed end-to-end here.

**Backend regression**: `python3 -m pytest tests/unit -q` — **770/770 passed** (the DB-independent portion of the suite; these use fake repositories and need no live database). The remaining ~389 integration tests require live Postgres and were not run here, for the same reason the Playwright suite wasn't — `pytest --collect-only` confirms all 1,159 backend tests still import and collect cleanly (no broken imports/fixtures from this phase's work, which touched no backend code at all).

### Defects found and fixed during this phase's testing

- **Stray unprotected `/` route**: `app/page.tsx` was still `create-next-app`'s default boilerplate, sitting outside the `(app)` route group — the actual post-login redirect target had no auth guard or shell chrome. Deleted; replaced with the real, protected `app/(app)/page.tsx`.
- **Collapsed sidebar links had no accessible name** (a11y defect, not just a style gap) — see Accessibility, above.
- **Global search's query didn't always reset on reopen**: the palette's `open` boolean lives in a shared store (`useUiStore`) that three independent call sites can flip to `true` — this component's own `⌘K` listener, Radix's own close/reopen, and `TopNav`'s search button, which writes to the store directly. An earlier version reset `rawQuery`/`activeIndex` inside a single `onOpenChange` handler passed to the Dialog, which meant opening via the header button silently skipped the reset. Caught by this phase's own test (`GlobalSearch > closes and resets the query when reopened`), fixed by switching to React's documented "compare against a ref of the previous value during render" pattern, which reacts to the `open` value itself regardless of which call site changed it.
- **Two `react-hooks` lint violations** (`set-state-in-effect`, `refs`) surfaced by this phase's ESLint config, both indicating real (if subtle) correctness risks, not just style: `GlobalSearch` was calling `setState` synchronously inside effects reacting to already-changed values (cascading-render-prone); `NotificationCenter` was reading a `ref.current` value during render (refs aren't meant to affect what's rendered — React doesn't guarantee re-rendering when a ref changes). Both fixed by moving to render-time-safe patterns (a derived/clamped value in `GlobalSearch`; a real `useState` flag instead of a ref read in `NotificationCenter`).
- **jsdom has no working `WebSocket`** (on its own documented "unimplemented" list — present but throws on construction) — not a product defect, but blocked every shell test touching the notification socket until `test/mock-websocket.ts` (a minimal constructable stand-in, install via `Object.defineProperty` since jsdom's `WebSocket` is a read-only getter) was added to `test/setup.ts`.

All are described here per the standing rule that defects get explained, fixed, and regression-tested, not silently patched.

## Known limitations

- **No organization switcher** — by design; see Organization/Branch Context. There is no backend capability to switch between organizations for v1.
- **Tablet gets the same `Sidebar` component as desktop/laptop**, not a distinct collapsible-drawer-by-default mode — a deliberate simplification (the existing expand/collapse toggle already addresses "less horizontal room" without a third nav pattern to build and test).
- **Global search has no "recent searches"** — the existing UX specification for this phase doesn't call for it, and the kickoff's instruction was explicit ("Recent searches only if supported by the product specification"), so none was added.
- **Global search results link to their entity's real list page, not a per-item detail page** — e.g. a plant result opens `/plants`, not `/plants/{id}`. No detail routes exist yet (7F/7G/7H haven't shipped), and fabricating a per-id URL that goes nowhere real would violate the same "no fake destinations" rule the nav config follows. The data in the results themselves is entirely real, from the real search endpoints.
- **Invoices and Suppliers have no nav entry at all** — real backend gap (seeded permissions, no route files), documented in Navigation Structure.
- **Accessibility checks were manual/code-review based, not automated** — no `axe-core`/`jest-axe` tooling exists in this repo yet; landmarks, labels, focus management, and keyboard navigation were verified by direct inspection and by the RTL test suite's `getByRole`-based queries (which fail if an accessible name/role is missing), not by an automated scanner. Adding one is a reasonable candidate for 7Q.
- **E2E and backend-integration test execution both blocked by the sandbox's missing Postgres/Docker** — see Testing, above; same standing constraint as every phase since Module 14.

## What's built vs. what's next

7C ships the complete authenticated shell described above, on real, working, permission-checked routes for every nav destination — populated with honest "not built yet" placeholders where the feature itself is a later phase. 7D (Dashboards) is the first phase to replace one of those placeholders (`/`, the Dashboard route) with real content.
