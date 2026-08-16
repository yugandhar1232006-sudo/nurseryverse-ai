import { z } from "zod";

/**
 * Client-side validation for 7E's forms -- UX only, mirroring
 * apps/api/app/schemas/{organization,branch,employee}.py's real
 * constraints (min/max lengths, ISO codes) so a submit never gets
 * rejected by the backend for a reason this form could have caught
 * first. The backend re-validates everything regardless.
 */

export const createOrganizationSchema = z.object({
  name: z.string().min(1, "Organization name is required.").max(255),
  contact_email: z.string().min(1, "Contact email is required.").email("Enter a valid email address."),
  contact_phone: z.string().max(50).optional().or(z.literal("")),
});
export type CreateOrganizationFormValues = z.infer<typeof createOrganizationSchema>;

export const orgProfileSchema = z.object({
  name: z.string().min(1, "Organization name is required.").max(255),
  contact_email: z.string().min(1, "Contact email is required.").email("Enter a valid email address."),
  contact_phone: z.string().max(50).optional().or(z.literal("")),
  logo_url: z.string().max(500).optional().or(z.literal("")),
});
export type OrgProfileFormValues = z.infer<typeof orgProfileSchema>;

export const orgSettingsSchema = z.object({
  currency: z.string().length(3, "Use a 3-letter ISO 4217 code, e.g. USD.").toUpperCase(),
  timezone: z.string().min(1, "Timezone is required."),
  branding_primary_color: z
    .string()
    .regex(/^#[0-9A-Fa-f]{6}$/, "Use a hex color like #2E7D32.")
    .optional()
    .or(z.literal("")),
  email_sender_identity: z.string().max(255).optional().or(z.literal("")),
  sms_enabled: z.boolean(),
});
export type OrgSettingsFormValues = z.infer<typeof orgSettingsSchema>;

const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/;

// A single flat `z.object` (not `.and()`-merged) on purpose: react-hook-form's
// `Path<T>`/`Control<T>` generic inference (used by `FormField`'s `name`
// prop, e.g. `hours.${day}.closed`) doesn't flatten Zod intersection types
// cleanly, which previously produced "Two different types with this name
// exist, but they are unrelated" errors. `latitude`/`longitude` stay plain
// strings (not `z.coerce.number()`) because the real form field is always a
// string coming out of an `<Input>` -- coercion happens once, explicitly, at
// submit time in `branch-form-dialog.tsx`, not inside the schema.
export const branchSchema = z.object({
  name: z.string().min(1, "Branch name is required.").max(255),
  address_line1: z.string().min(1, "Address is required.").max(255),
  address_line2: z.string().max(255).optional().or(z.literal("")),
  city: z.string().min(1, "City is required.").max(120),
  region: z.string().max(120).optional().or(z.literal("")),
  postal_code: z.string().max(20).optional().or(z.literal("")),
  country: z.string().length(2, "Use a 2-letter ISO 3166-1 country code, e.g. US.").toUpperCase(),
  timezone: z.string().min(1, "Timezone is required."),
  phone: z.string().max(50).optional().or(z.literal("")),
  email: z.string().email("Enter a valid email address.").optional().or(z.literal("")),
  latitude: z
    .string()
    .refine(
      (v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= -90 && Number(v) <= 90),
      "Latitude must be between -90 and 90.",
    ),
  longitude: z
    .string()
    .refine(
      (v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= -180 && Number(v) <= 180),
      "Longitude must be between -180 and 180.",
    ),
  hours: z.record(
    z.string(),
    z.object({ closed: z.boolean(), open: z.string().regex(timePattern), close: z.string().regex(timePattern) }),
  ),
});
export type BranchFormValues = z.infer<typeof branchSchema>;

export const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;

// `branch_ids` deliberately has no `.default([])` -- both callers always
// supply `branch_ids: []` in `defaultValues`, so the schema's input and
// output types stay identical and match useForm's single `TFieldValues`
// generic (a Zod `.default()` here would split them, which previously broke
// `zodResolver`'s `Resolver<Input, ..., Output>` assignability).
export const inviteEmployeeSchema = z.object({
  email: z.string().min(1, "Email is required.").email("Enter a valid email address."),
  role_code: z.string().min(1, "Select a role."),
  branch_ids: z.array(z.string()),
});
export type InviteEmployeeFormValues = z.infer<typeof inviteEmployeeSchema>;

export const reactivateEmployeeSchema = z.object({
  role_code: z.string().min(1, "Select a role."),
  branch_ids: z.array(z.string()),
});
export type ReactivateEmployeeFormValues = z.infer<typeof reactivateEmployeeSchema>;
