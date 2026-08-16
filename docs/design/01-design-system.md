# Design System

Foundational visual and interaction language for NurseryVerse AI. This document defines rationale and rules; exact numeric values are canonicalized as implementation-ready tokens in `06-design-tokens.md` — the two are kept in sync, this file explains *why*, that file gives the *value* to implement against. Target stack: Tailwind CSS + shadcn/ui (Radix primitives) + Framer Motion, per the project charter — this system is designed to map cleanly onto that stack without fighting it.

## 1. Color Palette

**Brand core:** a grounded, natural green family (`primary`) — this is a horticultural product; the brand color should read as "plant," not generic "tech SaaS blue." Primary is used for the main navigation active state, primary buttons, links, and brand moments (logo, empty-state illustrations) — deliberately *not* used for status/data-viz encoding, which has its own dedicated palettes below, to avoid ambiguity between "this is the brand" and "this plant is healthy."

**Neutral scale:** an 11-step gray scale (50–950) used for all text, borders, backgrounds, and surfaces. Neutral is the workhorse of the UI — the vast majority of any screen (tables, forms, cards) should read as neutral, with color reserved for meaning (status, action, brand).

**Semantic scale (system feedback):** `success`, `warning`, `danger`, `info` — four colors, each with a light/DEFAULT/dark step for backgrounds, borders, and text respectively. Used exclusively for system feedback (toasts, form validation, alert banners) — never repurposed for domain status, which keeps "your form failed to save" visually distinct from "this plant is unhealthy" even though both might otherwise trend red.

**Health-status scale (domain-specific, 5-step):** `excellent → good → fair → poor → critical`, a perceptually-ordered green-to-red ramp used exclusively for plant/branch health indicators (StatusBadge, HealthRiskBadge, dashboard risk cards). Per NFR-7.2, color is never the only signal — every health-status usage pairs the color with an icon and a text label.

**Growth-stage scale (domain-specific, sequential, non-alarming):** a cool-to-warm sequence (e.g., seedling → juvenile → mature → flowering/fruiting → dormant) using hue variation rather than a red/green alarm ramp, since growth stage is descriptive, not a warning signal — mixing it visually with the health-status scale would incorrectly imply "later stage = worse," which is not true.

**AI/prediction accent:** a distinct violet/indigo accent reserved specifically for AI-generated content (AIResultCard borders, ConfidenceIndicator, AssistantChatPanel) so users can tell at a glance "this came from the model" vs. "this is a fact a human recorded" — directly supporting the product principle that AI output must never be visually indistinguishable from ground truth (ties to FR-8.7's logging requirement and the AIExplanationPanel component).

**Dark mode:** every color above has a dark-mode-mapped equivalent (not a naive invert) — neutrals flip via a separate dark-optimized ramp (avoiding the common mistake of raw-inverting a light gray scale, which produces muddy, low-contrast darks), while brand/semantic/health/growth/AI hues are adjusted for sufficient contrast against dark surfaces rather than reused unchanged.

## 2. Typography

**Typeface:** a single humanist sans-serif family for all UI text (e.g., Inter or equivalent geometric-humanist sans) — chosen for high legibility at small sizes (dense tables, mobile field-use screens) and full weight-range availability. No secondary/display typeface — a single-family system reduces load weight and keeps a technical/operational product feeling consistent rather than "marketed."

**Type scale:** a modular scale from `display` (dashboard hero numbers, e.g., a KPI card's headline figure) down through `h1`–`h4` (page/section headers), `body-lg`/`body`/`body-sm` (default UI text, table cells, form labels), and `caption`/`overline` (metadata, timestamps, table column labels). Line-height is tied to each step (tighter for large display/headers, more generous for body text) rather than a single global value.

**Weights:** four weights in active use — regular (body text), medium (UI labels, table headers, emphasized inline text), semibold (section headers, button labels), bold (page titles, KPI figures only). Weight, not size alone, is the primary tool for establishing hierarchy in dense data screens (tables, the Plant Digital Twin) where size variation would waste vertical space.

**Numeric/tabular figures:** tables and KPI cards use tabular (fixed-width) numeral rendering so columns of numbers (prices, quantities, dates) align vertically — a functional requirement for a data-dense operational product, not a stylistic preference.

## 3. Iconography

**Icon set:** Lucide (pairs natively with shadcn/ui, per stack decision) — a single consistent icon family throughout; no mixing icon sets.

**Sizing scale:** four fixed sizes — 16px (inline with body text, table row actions), 20px (form field icons, nav items), 24px (page-header actions, standalone buttons), 32px (empty-state illustrations, dashboard stat-card icons). Icons are never arbitrarily scaled outside this set.

**Usage rule:** every icon used to convey status or meaning (not purely decorative) is always paired with a text label or accessible label — icons alone are never the sole carrier of meaning (NFR-7.2), consistent with the health-status color rule above.

**Domain icon mapping:** a fixed icon-to-concept dictionary is maintained (e.g., droplet = watering, leaf = growth, shield-alert = disease, QR glyph = passport/scan) so the same concept always renders with the same icon across every screen — defined once in `03-component-library.md`'s icon usage notes, not redefined per screen.

## 4. Elevation & Shadows

Four elevation levels, each a shadow token: `flat` (0 — default page background, most cards at rest), `raised` (subtle shadow — cards on hover/focus, dropdown triggers), `overlay` (dropdowns, popovers, tooltips), `modal` (dialogs, drawers — the highest elevation, always paired with a scrim). Elevation increases only with genuine z-axis meaning (something is now floating above the page) — it is not used decoratively to make flat content "pop."

## 5. Border Radius

Three radius steps: `sm` (form inputs, small buttons, badges), `md` (cards, modals, standard buttons — the default for most surfaces), `lg` (large feature cards, the AI Assistant panel). No fully-sharp (0) or fully-pill radius is used except where semantically appropriate (pill/`full` radius reserved for StatusBadge and tag-like components specifically, to visually distinguish "this is a status chip" from "this is a card").

## 6. Grid System

A 12-column responsive grid with fixed gutter width, contained within a max-width that scales per breakpoint (full-bleed on mobile, capped and centered on large desktop so dense dashboards don't stretch into unreadable line lengths on ultra-wide monitors). Dashboard widget layouts (StatCard grids, chart placement) are specified in column-span terms (e.g., "StatCard spans 3 columns on desktop, 6 on tablet, 12 on mobile") in the screen specifications, not pixel widths.

## 7. Spacing System

A 4px base unit, scaling geometrically (4/8/12/16/24/32/48/64/96) — the same scale governs padding, margin, and gap everywhere, so vertical rhythm is consistent whether you're looking at form field spacing or dashboard card gaps. Component-internal spacing (e.g., padding inside a button) uses the smaller steps (4/8/12); layout-level spacing (between cards, page section gaps) uses the larger steps (24/32/48+).

## 8. Breakpoints

| Breakpoint | Width | Maps to |
|---|---|---|
| `mobile` | < 640px | Mobile (phone, portrait-first) |
| `tablet` | 640–1023px | Tablet |
| `laptop` | 1024–1439px | Laptop |
| `desktop` | ≥ 1440px | Desktop (large monitor) |

Full per-breakpoint layout behavior (sidebar collapse, table-to-card transformation, etc.) is in `04-responsive-design-specifications.md`.

## 9. Animation System & Motion Guidelines

**Duration scale:** `instant` (100ms — hover/focus state changes), `fast` (150ms — toggles, small component state changes), `standard` (200–250ms — modal/drawer open-close, page-section transitions), `deliberate` (400ms — the AI processing/thinking indicator, first-load skeleton-to-content transition).

**Easing:** ease-out for anything entering the screen (modals, toasts, new content), ease-in for anything leaving, standard ease-in-out for state toggles — motion should feel like it has physical weight, not linear/robotic.

**Motion principles:** motion is always purposeful (confirms an action happened, orients the user during a layout change, or communicates system processing state — e.g., AI inference in progress) and never purely decorative. `prefers-reduced-motion` is respected system-wide — all non-essential animation (page transitions, hover effects) is disabled/reduced for users who request it, while essential state changes (a form submitted, an item added to cart) still communicate via a non-motion cue (e.g., a checkmark) so information isn't lost.

**AI-specific motion:** the AI "thinking" state (disease scan processing, assistant generating a response) uses a distinct, recognizable pulse/shimmer pattern — reused consistently everywhere AI inference is in flight, so users learn once what "the AI is working on this" looks like.

## 10. Accessibility Guidelines

Target: WCAG 2.1 AA, matching NFR-7. Concretely: minimum 4.5:1 contrast for body text and 3:1 for large text/UI components against their background, in both light and dark mode; every interactive element reachable and operable via keyboard alone, with a visible focus ring (never `outline: none` without a replacement); every icon-only control has an accessible name (`aria-label` or equivalent); all form inputs have an associated, visible label (not placeholder-as-label); color is never the sole carrier of meaning (restated from §1/§3); motion respects `prefers-reduced-motion`; touch targets on mobile/tablet are a minimum 44×44px hit area even where the visual element is smaller. Full interaction-level accessibility rules (keyboard shortcuts, focus order, screen-reader announcements for dynamic content like toasts and live AI results) are in `08-ux-documentation.md`.
