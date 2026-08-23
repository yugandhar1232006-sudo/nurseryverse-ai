import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Standard shadcn/ui `cn` helper -- merges Tailwind classes with
 * conflict resolution (e.g. `cn("p-2", condition && "p-4")` correctly
 * keeps only `p-4` when `condition` is true, rather than emitting both
 * classes and leaving the cascade to decide).
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Currency formatting for real monetary figures returned by the backend
 * (dashboard/analytics/sales/inventory-valuation responses, etc.) --
 * `currencyCode` should always come from `OrgSettingsResponse.default_currency`
 * (see lib/api/organizations.ts), never assumed, since NurseryVerse is
 * multi-currency across orgs. Falls back to "INR" only for the brief
 * window before that org settings query resolves -- never a silent
 * guess presented as final.
 */
export function formatCurrency(value: number, currencyCode = "INR"): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: currencyCode, maximumFractionDigits: 2 }).format(value);
  } catch {
    // An org settings row with an invalid/unsupported ISO code would throw
    // inside Intl.NumberFormat -- degrade to a plain number rather than
    // crashing the dashboard over a formatting preference.
    return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
  }
}

/** Plain thousands-grouped integer/decimal formatting for non-currency counts (plant counts, unit counts, etc.). */
export function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined).format(value);
}

/** Compact form (1.2K, 3.4M) for space-constrained KPI cards. */
export function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

/** One decimal place percentage from a 0-1 ratio (e.g. gross margin, repeat-customer rate). */
export function formatPercent(ratio: number): string {
  return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 }).format(ratio);
}
