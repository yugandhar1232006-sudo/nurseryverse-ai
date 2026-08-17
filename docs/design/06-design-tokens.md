# Design Tokens

Implementation-ready values for everything defined conceptually in `01-design-system.md`. These map directly onto a Tailwind CSS theme extension (`tailwind.config`) and shadcn/ui CSS variables in Phase 7 — token names below are the source of truth; Phase 7 wires them into the actual config file.

## Color Tokens

### Primary (brand green)
| Token | Hex | Usage |
|---|---|---|
| `primary-50` | #F0F9F1 | Subtle backgrounds (selected nav item bg) |
| `primary-100` | #DCF0DE | Light accents |
| `primary-300` | #8FCB98 | Hover states on light backgrounds |
| `primary-500` | #2F8F42 | Default — buttons, links, active nav |
| `primary-600` | #24732F | Hover state on primary-500 elements |
| `primary-700` | #1C5B26 | Pressed/active state |
| `primary-900` | #0F3315 | High-contrast text-on-light use |

### Neutral
| Token | Hex |
|---|---|
| `neutral-50` | #FAFAF9 |
| `neutral-100` | #F2F1EF |
| `neutral-200` | #E5E3E0 |
| `neutral-300` | #D1CEC9 |
| `neutral-400` | #A8A39C |
| `neutral-500` | #7C766D |
| `neutral-600` | #5C574F |
| `neutral-700` | #423E38 |
| `neutral-800` | #2C2925 |
| `neutral-900` | #1B1917 |
| `neutral-950` | #100F0D |

### Semantic
| Token | Light step | DEFAULT | Dark step |
|---|---|---|---|
| `success` | #E6F6EC | #1E9E4F | #14622F |
| `warning` | #FEF6E7 | #D68A0C | #8A5906 |
| `danger` | #FBEAEA | #D6392E | #8C231C |
| `info` | #E9F1FC | #2D6FD1 | #1C4785 |

### Health-Status Scale (domain, 5-step)
| Token | Hex | Meaning |
|---|---|---|
| `health-excellent` | #1E9E4F | Thriving |
| `health-good` | #7CB518 | Healthy, minor watch items |
| `health-fair` | #D68A0C | Needs attention soon |
| `health-poor` | #E36414 | Needs attention now |
| `health-critical` | #D6392E | Urgent |

### Growth-Stage Scale (domain, sequential, non-alarming)
| Token | Hex | Stage |
|---|---|---|
| `growth-seedling` | #7FB3D5 | Seedling |
| `growth-juvenile` | #52A675 | Juvenile |
| `growth-mature` | #2F8F42 | Mature |
| `growth-flowering` | #C77DBB | Flowering/Fruiting |
| `growth-dormant` | #8C8577 | Dormant |

### AI Accent
| Token | Hex | Usage |
|---|---|---|
| `ai-accent-50` | #F3F0FC | AI card background tint |
| `ai-accent-300` | #B6A3EE | AI border/divider |
| `ai-accent-500` | #7C5CE0 | AI icon/badge default |
| `ai-accent-700` | #5A3DB8 | AI text on light background |

### Dark Mode Mapping (surface + text, not a full re-derivation table — full spec owned by Phase 7 theme file)
| Token | Light mode | Dark mode |
|---|---|---|
| `surface-page` | `neutral-50` | `neutral-950` |
| `surface-card` | `#FFFFFF` | `neutral-900` |
| `text-primary` | `neutral-900` | `neutral-50` |
| `text-secondary` | `neutral-600` | `neutral-400` |
| `border-default` | `neutral-200` | `neutral-700` |

## Typography Tokens

| Token | Size | Line height | Weight | Usage |
|---|---|---|---|---|
| `text-display` | 36px | 44px | 700 | Dashboard hero KPI figures |
| `text-h1` | 28px | 36px | 700 | Page titles |
| `text-h2` | 22px | 30px | 600 | Section headers |
| `text-h3` | 18px | 26px | 600 | Card/subsection headers |
| `text-h4` | 16px | 22px | 600 | Minor headers, form section titles |
| `text-body-lg` | 16px | 24px | 400 | Emphasized body text |
| `text-body` | 14px | 20px | 400 | Default UI text |
| `text-body-sm` | 13px | 18px | 400 | Table cells, secondary info |
| `text-caption` | 12px | 16px | 400 | Metadata, timestamps |
| `text-overline` | 11px | 14px | 500 (uppercase, letter-spaced) | Table column labels, category tags |

Font family token: `font-sans` = Inter, system-ui fallback stack.

## Border Radius Tokens

| Token | Value | Usage |
|---|---|---|
| `radius-sm` | 4px | Inputs, small buttons, badges (non-pill) |
| `radius-md` | 8px | Cards, modals, standard buttons (default) |
| `radius-lg` | 12px | Feature cards, AI Assistant panel |
| `radius-full` | 9999px | StatusBadge, tag chips |

## Shadow Tokens

| Token | Value (approx.) | Usage |
|---|---|---|
| `shadow-flat` | none | Default resting cards |
| `shadow-raised` | 0 1px 2px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.08) | Hover/focus card elevation |
| `shadow-overlay` | 0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.06) | Dropdowns, popovers, tooltips |
| `shadow-modal` | 0 20px 25px rgba(0,0,0,0.10), 0 8px 10px rgba(0,0,0,0.08) | Dialogs, drawers |

## Z-Index Tokens

| Token | Value | Layer |
|---|---|---|
| `z-base` | 0 | Page content |
| `z-sticky` | 10 | Sticky headers, TabNav |
| `z-dropdown` | 20 | Dropdown/ContextMenu |
| `z-overlay-scrim` | 30 | Modal/SlideOverPanel backdrop |
| `z-overlay` | 40 | Modal, SlideOverPanel content |
| `z-toast` | 50 | Toast notifications |
| `z-tooltip` | 60 | Tooltips (must always render above modals) |

Nesting note: floating popovers/menus that portal to `<body>` and can open
*inside* a modal (`Select`, `Popover`, `DropdownMenu`) use `z-overlay` (40),
not `z-dropdown` (20) — at 20 they'd sit below the modal's `z-overlay-scrim`
(30), which would intercept every click on them. They tie the modal content
at 40 and win on DOM order (their portal mounts after the dialog's).

## Spacing Tokens

| Token | Value |
|---|---|
| `space-1` | 4px |
| `space-2` | 8px |
| `space-3` | 12px |
| `space-4` | 16px |
| `space-6` | 24px |
| `space-8` | 32px |
| `space-12` | 48px |
| `space-16` | 64px |
| `space-24` | 96px |

## Transition Timing Tokens

| Token | Duration | Easing | Usage |
|---|---|---|---|
| `duration-instant` | 100ms | ease-out | Hover/focus state changes |
| `duration-fast` | 150ms | ease-out | Toggles, small state changes |
| `duration-standard` | 225ms | cubic-bezier(0.4, 0, 0.2, 1) | Modal/drawer open, section transitions |
| `duration-deliberate` | 400ms | ease-in-out | AI thinking indicator, skeleton-to-content |

## Icon Size Tokens

| Token | Value | Usage |
|---|---|---|
| `icon-sm` | 16px | Inline with body text, table row actions |
| `icon-md` | 20px | Form field icons, nav items |
| `icon-lg` | 24px | Page-header actions, standalone buttons |
| `icon-xl` | 32px | Empty-state illustrations, stat-card icons |

## Component Spacing Tokens

| Token | Value | Usage |
|---|---|---|
| `component-padding-sm` | `space-2` (8px) | Badge, compact button internal padding |
| `component-padding-md` | `space-3` (12px) horizontal, `space-2` (8px) vertical | Standard button, input padding |
| `component-padding-lg` | `space-4` (16px) | Card internal padding |
| `component-gap-tight` | `space-2` (8px) | Icon-to-label gap, form field-to-helper-text gap |
| `component-gap-standard` | `space-4` (16px) | Between form fields, between card grid items |
| `component-gap-section` | `space-8` (32px) | Between page sections |

## Breakpoint Tokens

| Token | Min-width |
|---|---|
| `screen-tablet` | 640px |
| `screen-laptop` | 1024px |
| `screen-desktop` | 1440px |
