import { z } from "zod";

/**
 * 7N -- validation for the "Generate report" and "New scheduled report"
 * dialogs. `report_type`/`format`/`frequency` are the real 18/4/3-value
 * enums from `lib/api/reports.ts` (`ReportType`/`ReportFormat`/
 * `ReportScheduleFrequency`), not re-declared here -- `z.string().min(1)`
 * is enough since the field is always populated from a `<Select>` whose
 * options are the real enum values, matching `lib/validation/ai.ts`'s
 * established "don't re-encode a generated enum in a second place"
 * approach.
 *
 * **Scope decision, not an oversight**: `ReportFilters` has ~9 real
 * fields (species_id, category_id, customer_id, customer_type, status,
 * category, prediction_type, low_stock_only, date_from/date_to), each
 * meaningful only for a subset of the 18 report types (e.g.
 * `low_stock_only` only means something for an Inventory report,
 * `prediction_type` only for an AI Summary report). Building 18 distinct
 * per-type filter forms was judged out of scope for this pass -- both
 * dialogs below expose only the two filters that apply to every report
 * type regardless of shape (`date_from`/`date_to`) plus branch scope.
 * See docs/frontend/18-reports-analytics.md's Known Limitations.
 */
export const generateReportSchema = z.object({
  report_type: z.string().min(1, "Choose a report type."),
  format: z.enum(["pdf", "excel", "csv", "json"]),
  branch_id: z.string().optional().or(z.literal("")),
  date_from: z.string().optional().or(z.literal("")),
  date_to: z.string().optional().or(z.literal("")),
});
export type GenerateReportFormValues = z.infer<typeof generateReportSchema>;

const isoDateTimeLocal = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;

export const scheduledReportSchema = z.object({
  name: z.string().min(1, "Name is required.").max(255),
  report_type: z.string().min(1, "Choose a report type."),
  format: z.enum(["pdf", "excel", "csv", "json"]),
  branch_id: z.string().optional().or(z.literal("")),
  frequency: z.enum(["daily", "weekly", "monthly"]),
  next_run_at: z
    .string()
    .min(1, "Choose a first run time.")
    .regex(isoDateTimeLocal, "Use the date/time picker.")
    .refine((v) => new Date(v).getTime() > Date.now(), "First run time must be in the future."),
  date_from: z.string().optional().or(z.literal("")),
  date_to: z.string().optional().or(z.literal("")),
});
export type ScheduledReportFormValues = z.infer<typeof scheduledReportSchema>;
