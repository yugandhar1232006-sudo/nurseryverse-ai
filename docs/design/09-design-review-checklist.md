# Design Review Checklist

Every screen must satisfy this checklist before it moves from design to implementation (Phase 7), and again before implementation is considered done (Phase 9 QA references this same checklist). Organized to mirror the structure of this Phase 3 document set.

## Design System Compliance
- [ ] Uses only tokens defined in `06-design-tokens.md` — no arbitrary/one-off colors, spacing, or font sizes.
- [ ] Color usage follows the semantic split in `01-design-system.md` §1 (brand vs. semantic vs. health-status vs. growth-stage vs. AI-accent are never mixed/confused).
- [ ] Typography uses only the defined type scale (§2) — no ad-hoc font sizes.
- [ ] Icons are from the single defined icon set, at a defined size step, never color-only carriers of meaning.
- [ ] Border radius, shadow, and elevation choices match the defined steps and their intended usage (§4/§5).

## Component Usage
- [ ] Every UI element maps to a component defined in `02-component-library.md` — no bespoke one-off components introduced without being added to the library first.
- [ ] All required component states are accounted for on this screen (not just the "happy path" populated state).
- [ ] Destructive/hard-to-reverse actions use ConfirmationDialog, tiered correctly (standard vs. typed-confirmation) per `08-ux-documentation.md` §5.

## Screen Completeness (per `03-screen-specifications.md`)
- [ ] Header, sidebar, breadcrumb behavior matches the Shared Chrome definition (or the documented exception for public pages).
- [ ] All sections, cards, tables, charts, buttons, forms, and dialogs specified for this screen are present and match the spec.
- [ ] Filters and search (if applicable) follow `08-ux-documentation.md` §7/§8 behavior rules.
- [ ] Primary and secondary actions are visually distinguished (one primary action per screen/section, not several competing primaries).

## Required States (per `07-ui-state-documentation.md`)
- [ ] Empty state implemented, and the correct variant used (first-use vs. filtered-empty vs. positive-empty).
- [ ] Loading state implemented (skeleton preferred over spinner for structured content).
- [ ] Error state implemented at the correct granularity (field / section / full-page) with plain-language messaging and a retry/recovery path.
- [ ] Success state implemented and specific to the action taken (not a generic "Success").
- [ ] Offline behavior considered where the screen involves data entry (per §4).
- [ ] Validation behavior (client-side and server-side) matches §6's timing and messaging rules.
- [ ] AI processing state implemented correctly if this screen surfaces AI output (thinking state, stale-prediction flag, unavailable/fallback state).

## Responsive Behavior (per `04-responsive-design-specifications.md`)
- [ ] Layout defined and verified at all four breakpoints (Mobile, Tablet, Laptop, Desktop) — not just designed for desktop and "assumed to reflow."
- [ ] DataTable instances correctly transform to stacked cards below Tablet, where applicable.
- [ ] Touch targets meet the 44×44px minimum on Tablet/Mobile.
- [ ] No hover-only interactions without a tap/long-press equivalent below Laptop.
- [ ] Camera-first components (PhotoUpload, QRScanner) behave correctly per device capability.

## Accessibility (per `01-design-system.md` §10 and `08-ux-documentation.md` §3)
- [ ] Color contrast meets WCAG 2.1 AA (4.5:1 body text, 3:1 large text/UI components) in both light and dark mode.
- [ ] Every interactive element is keyboard-reachable and operable, with a visible focus ring.
- [ ] Every icon-only control has an accessible name.
- [ ] Every form input has a visible, programmatically associated label (not placeholder-as-label).
- [ ] Dynamic content (toasts, AI results, live updates) is announced via appropriate `aria-live` regions.
- [ ] Focus is trapped and correctly restored for any modal/panel opened from this screen.
- [ ] Meaning is never conveyed by color alone anywhere on this screen.

## AI-Specific Review (where applicable)
- [ ] AI-sourced content is visually distinguished via the AI-accent treatment, never presented with the same certainty as factual data.
- [ ] Every AI result shown includes a confidence indicator and an accessible "why" (AIExplanationPanel or equivalent).
- [ ] No AI output is displayed without a corresponding persisted `ai_predictions`/`ai_recommendations` record (FR-8.7 — a build/implementation check, but the design must not present output that couldn't have been logged).
- [ ] Any AI-proposed write action requires explicit human confirmation via AssistantActionConfirmCard before executing (FR-9.3).

## Content & Copy
- [ ] All copy uses the plain, nursery-industry terminology defined in `docs/ux/08-information-architecture.md` §4 — no generic SaaS jargon leaking into user-facing text.
- [ ] Error messages are actionable and specific, never a raw technical string.
- [ ] Confirmation dialog copy states the specific consequence, not a generic "Are you sure?"

## Permissions
- [ ] Every action/element on the screen is gated by the correct permission code(s) from `docs/ux/07-role-permission-matrix.md`.
- [ ] Permission-denied elements are absent, not visibly disabled, except the documented Enterprise-upsell exception.
- [ ] Branch-scoped (`B`) permissions are verified against the resource's actual branch, not just the user's role.

## Sign-off
- [ ] Screen reviewed against this checklist by design and against `docs/ux/09-page-inventory.md` for functional completeness by product.
- [ ] Any deviation from this checklist is logged as an explicit, approved exception (ADR-style note in `docs/adr/`), not a silent gap.
