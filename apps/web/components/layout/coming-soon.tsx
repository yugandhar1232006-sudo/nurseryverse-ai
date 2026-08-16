import type { LucideIcon } from "lucide-react";

import { EmptyState } from "@/components/empty-state";

/**
 * Honest placeholder for a real nav destination whose actual feature
 * build hasn't happened yet (7D-7O, per the phase plan). Every route
 * that renders this is a genuine, permission-checked, working Next.js
 * route -- unlike Invoices/Suppliers (dropped from nav entirely, see
 * `nav-config.ts`), these destinations *will* have real content once
 * their phase lands. The distinction matters: this is "not built yet,"
 * never "fake data standing in for real data."
 */
export function ComingSoon({
  icon,
  title,
  description = "This part of NurseryVerse AI hasn't been built yet. Check back once this module ships.",
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
}) {
  return <EmptyState icon={icon} title={title} description={description} className="py-24" />;
}
