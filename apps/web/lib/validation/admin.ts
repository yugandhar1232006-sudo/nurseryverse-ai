import { z } from "zod";

/** 7O -- validation for the Users/Feature Flags/Notification Administration forms. Mirrors the real backend constraints in `apps/api/app/schemas/admin.py`/`notifications.py` so a submit rarely gets rejected for a reason this form could have caught first. */

export const changeRoleSchema = z.object({
  new_role_code: z.string().min(1, "Choose a role."),
});
export type ChangeRoleFormValues = z.infer<typeof changeRoleSchema>;

/** Real constraint: `LockAccountRequest.duration_minutes` is 1 minute to 7 days (10080 minutes). */
export const lockAccountSchema = z.object({
  duration_minutes: z
    .string()
    .min(1, "Enter a duration.")
    .refine((v) => !Number.isNaN(Number(v)) && Number(v) >= 1 && Number(v) <= 10080, "Enter 1 to 10080 minutes (7 days)."),
});
export type LockAccountFormValues = z.infer<typeof lockAccountSchema>;

export const setFeatureFlagSchema = z.object({
  is_enabled: z.boolean(),
  description: z.string().max(500).optional().or(z.literal("")),
});
export type SetFeatureFlagFormValues = z.infer<typeof setFeatureFlagSchema>;

export const notificationTemplateSchema = z.object({
  category: z.string().min(1, "Choose a category."),
  channel: z.enum(["in_app", "email", "sms", "push"]),
  format: z.string().min(1).max(50),
  locale: z.string().min(1).max(20),
  subject_template: z.string().max(500).optional().or(z.literal("")),
  body_template: z.string().min(1, "Body template is required."),
});
export type NotificationTemplateFormValues = z.infer<typeof notificationTemplateSchema>;

export const systemAlertSchema = z.object({
  title: z.string().min(1, "Title is required.").max(255),
  message: z.string().min(1, "Message is required.").max(2000),
  severity: z.enum(["info", "warning", "critical"]),
});
export type SystemAlertFormValues = z.infer<typeof systemAlertSchema>;
