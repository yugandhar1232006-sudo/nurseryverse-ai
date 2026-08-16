# Frontend Architecture

Next.js 14+ (App Router), TypeScript strict mode, Tailwind CSS + shadcn/ui, Framer Motion — per the project charter's Phase 7 stack decision. This document is what Phase 7 (Frontend implementation) builds against, and reflects every screen/component/state defined in Phase 3.

## 1. Next.js App Router Structure

```
apps/web/
├── app/
│   ├── (public)/                   # PG-01–06, minimal layout (no AppShell)
│   │   ├── page.tsx                # PG-01 Landing
│   │   ├── signup/page.tsx         # PG-02
│   │   ├── login/page.tsx          # PG-03
│   │   ├── forgot-password/page.tsx
│   │   ├── reset-password/page.tsx
│   │   └── invite/[token]/page.tsx # PG-06
│   ├── (app)/                      # authenticated app shell, layout.tsx = AppShell
│   │   ├── layout.tsx
│   │   ├── dashboard/page.tsx      # PG-07/08 (role-conditional render)
│   │   ├── plants/
│   │   │   ├── page.tsx            # PG-20
│   │   │   ├── new/page.tsx        # PG-21
│   │   │   └── [plantId]/
│   │   │       ├── page.tsx        # PG-22 overview
│   │   │       ├── growth/page.tsx # PG-23
│   │   │       ├── health/page.tsx # PG-24
│   │   │       ├── environmental/page.tsx # PG-25
│   │   │       └── predictions/page.tsx   # PG-26
│   │   ├── disease-reports/[...]
│   │   ├── ai/
│   │   │   ├── page.tsx            # PG-31
│   │   │   ├── revenue-forecast/page.tsx  # PG-32
│   │   │   └── recommendations/page.tsx   # PG-33
│   │   ├── watering/page.tsx       # PG-34
│   │   ├── inventory/[...]
│   │   ├── sales/[...]             # PG-39/40/41
│   │   ├── customers/[...]
│   │   ├── invoices/[...]
│   │   ├── suppliers/[...]
│   │   ├── purchase-orders/[...]
│   │   ├── reports/[...]
│   │   ├── audit-log/page.tsx      # PG-54
│   │   └── settings/
│   │       ├── layout.tsx          # Settings TabNav
│   │       ├── org/page.tsx        # PG-55
│   │       ├── billing/page.tsx    # PG-56
│   │       ├── roles/page.tsx      # PG-57
│   │       ├── notifications/page.tsx # PG-58
│   │       └── integrations/page.tsx  # PG-59
│   ├── passport/[token]/page.tsx   # PG-53 public tokenized view (outside (app) group, own minimal layout)
│   ├── api/                        # Next.js route handlers used ONLY for BFF-style concerns (see §7), not a duplicate backend
│   ├── layout.tsx                  # root layout (fonts, providers)
│   └── globals.css
├── src/
│   ├── features/                   # one folder per domain, mirrors docs/ux sitemap grouping
│   │   └── <domain>/{components,hooks,api.ts,types.ts}
│   ├── components/ui/              # shadcn/ui-based design-system primitives (Button, Card, etc.)
│   ├── components/shared/          # cross-domain composed components (DataTable, AIResultCard, etc.)
│   ├── layouts/                    # AppShell, PublicLayout, SettingsLayout
│   ├── hooks/                      # useAuth, usePermission, useWebSocket, useBranchScope
│   ├── services/                   # apiClient (axios/fetch wrapper), websocketClient
│   ├── stores/                     # Zustand stores (session, ui, notifications)
│   ├── lib/                        # zod schemas, formatters, constants, the domain icon dictionary
│   └── types/                      # generated API types (from OpenAPI, packages/shared-types)
```

Route groups (`(public)`, `(app)`) share no layout — this is what makes PG-01–06's minimal header (per `docs/design/03-screen-specifications.md`) structurally distinct from the authenticated AppShell rather than a conditionally-hidden sidebar.

## 2. State Management

**Server state:** TanStack Query exclusively — every API read/write goes through a `useQuery`/`useMutation` hook defined in the owning feature's `api.ts`, never a raw `fetch`/`axios` call from a component. Query keys are structured `[domain, resourceId, params]` for predictable invalidation (e.g., completing a sale invalidates `['inventory', branchId]` and `['plants', plantId]` together, matching the transactional reality in the backend). **Client/UI state:** Zustand — `sessionStore` (current user, active branch, permissions), `uiStore` (sidebar collapsed, active modal), `notificationStore` (unread count, live feed, fed by the WebSocket client). No global state library is used for server data — this split is deliberate and non-negotiable (mixing the two is the most common source of stale-cache bugs in this class of app).

## 3. React Query (TanStack Query) Conventions

Default `staleTime` varies by data volatility: reference data (Species, Suppliers) — 5 minutes; operational lists (Plants, Inventory) — 30 seconds; realtime-critical data (Notifications, POS availability checks) — 0 (always refetch, supplemented by WebSocket push for true realtime). Mutations use optimistic updates only for low-risk, easily-reversible actions (per `docs/design/07-ui-state-documentation.md` §5) — e.g., marking a notification read updates the cache immediately with rollback-on-error; a Sale completion waits for server confirmation given its financial/inventory consequences. WebSocket events (§6) invalidate the relevant query keys directly rather than maintaining a parallel realtime state store, keeping TanStack Query the single source of truth for server data regardless of how the update arrived (poll, push, or user action).

## 4. Forms

React Hook Form + Zod for every form in the system. Zod schemas live in `lib/schemas/<domain>.ts` and are hand-kept in sync with the backend's Pydantic schemas field-for-field (both derive from the same Functional Requirements — Phase 6 and Phase 7 are built from the same FR/page-inventory source of truth, so drift is a review-catchable defect, not an expected occurrence). Every form follows the FormSection/FormActions composition pattern from `docs/design/02-component-library.md`; validation timing (on-blur, not on-keystroke) and error display match `docs/design/08-ux-documentation.md` §6 exactly.

## 5. Routing

App Router file-based routing per §1's tree. Dynamic segments (`[plantId]`, `[token]`) are typed via a generated route-params helper. Protected routes are enforced in `middleware.ts` (Next.js Edge Middleware) — checks for a valid session cookie before any `(app)` route renders, redirecting to `/login` otherwise; this is a defense-in-depth layer, not the primary authorization mechanism (every actual data access is still permission-checked server-side by the FastAPI backend regardless of what the frontend route guard allows, per NFR-4.4's "never trust the client" principle).

## 6. Authentication Flow

JWT access token is held in memory (a Zustand store, not `localStorage` — mitigates XSS token theft); the refresh token is set as an `httpOnly`, `Secure`, `SameSite=Lax` cookie by the backend on login, invisible to client-side JS entirely. On app load, a silent refresh call exchanges the httpOnly refresh cookie for a new access token before rendering any protected content. Axios/fetch interceptor in `services/apiClient.ts` catches 401s, attempts one silent refresh, and retries the original request once — a second 401 forces logout and redirect to `/login`. WebSocket connections authenticate via the short-lived ticket pattern (`03-backend-architecture.md` §10), fetched via a normal authenticated REST call, not by exposing the access token to the socket URL.

## 7. Error Boundaries

A root `error.tsx` (Next.js App Router convention) catches unhandled render errors app-wide, rendering the full-page ErrorState component (per `docs/design/02-component-library.md`) with a "reload" action and automatic Sentry reporting. Each major route segment (`plants/`, `sales/`, etc.) additionally has its own `error.tsx` so a crash in one feature area doesn't take down the whole app shell — mirrors the section-level ErrorState pattern from the design spec (NFR-3.3's graceful degradation, applied at the frontend routing layer). `app/api/` route handlers exist only for a small number of BFF (backend-for-frontend) concerns that genuinely benefit from running server-side in the Next.js process — namely proxying the httpOnly-cookie refresh flow — and are not a parallel API layer duplicating FastAPI's responsibilities.

## 8. Layout System

Nested layouts per App Router convention: root `layout.tsx` (fonts, theme provider, TanStack Query provider, Zustand hydration) → `(app)/layout.tsx` (AppShell: Sidebar + Header) → `settings/layout.tsx` (adds the Settings TabNav) → page-level content. Plant Digital Twin's tabs (PG-23–26) are implemented as sibling routes under `plants/[plantId]/`, not client-side-only tab state, so each tab is deep-linkable per the navigation architecture's requirement (`docs/ux/04-navigation-architecture.md`).

## 9. Component Architecture

Feature-based, matching `docs/ux/09-page-inventory.md` and `docs/design/02-component-library.md` exactly — no component is invented during implementation that wasn't already specified in Phase 3; conversely, every component in the Phase 3 library has a corresponding implementation home here (`components/ui/` for design-system primitives, `components/shared/` for cross-domain composed components like DataTable/AIResultCard, `features/<domain>/components/` for domain-specific UI). Components are function components with typed props (no default-props-required violations — every component either has no required props or sensible defaults, supporting isolated Storybook-style development, flagged as a Phase 7 tooling recommendation). Server Components (App Router default) are used for initial data-fetch-and-render where no client interactivity is needed (e.g., the initial Plants List render); Client Components (`"use client"`) are reserved for anything using hooks, state, or browser APIs (forms, charts, the AssistantChatPanel, QRScanner) — this split is made deliberately per component, not applied blanket, to get the App Router's server-rendering performance benefit where it's actually available.
