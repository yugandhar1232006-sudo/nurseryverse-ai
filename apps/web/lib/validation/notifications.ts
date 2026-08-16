import { z } from "zod";

/**
 * 7M / PG-58 -- validation for the quiet-hours + frequency controls that
 * apply uniformly across the category x channel matrix (see
 * `NotificationPreferencesPanel`'s docstring for why per-row quiet hours
 * were judged out of scope). The category x channel checkboxes themselves
 * are plain component state, not an RHF form -- there's nothing to
 * validate about a boolean grid, only about the shared quiet-hours/
 * frequency fields below, so only those go through RHF+Zod, matching
 * `branch-form-dialog.tsx`'s `timePattern` (`HH:MM`, no seconds -- the
 * real `time` field is converted to/from `HH:MM:SS` at the API boundary).
 */
const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/;

export const notificationPreferencesSchema = z
  .object({
    quiet_hours_start: z.string().regex(timePattern, "Use HH:MM, e.g. 21:00.").optional().or(z.literal("")),
    quiet_hours_end: z.string().regex(timePattern, "Use HH:MM, e.g. 07:00.").optional().or(z.literal("")),
    quiet_hours_timezone: z.string().max(64).optional().or(z.literal("")),
    frequency: z.enum(["immediate", "daily_digest", "weekly_digest"]),
  })
  .refine((v) => (v.quiet_hours_start ? v.quiet_hours_end !== "" : true), {
    message: "Set an end time for quiet hours.",
    path: ["quiet_hours_end"],
  })
  .refine((v) => (v.quiet_hours_end ? v.quiet_hours_start !== "" : true), {
    message: "Set a start time for quiet hours.",
    path: ["quiet_hours_start"],
  });
export type NotificationPreferencesFormValues = z.infer<typeof notificationPreferencesSchema>;
