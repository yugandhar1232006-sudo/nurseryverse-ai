import { z } from "zod";

/**
 * Client-side validation for 7J's Customer/CRM forms -- UX only, mirroring
 * apps/api/app/schemas/customer.py's real constraints. Follows the
 * established plain-`z.string()` (never `z.coerce.number()`) pattern from
 * 7E/7I.
 */

const emailField = z
  .string()
  .max(320)
  .refine((v) => v === "" || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v), "Enter a valid email address.")
  .optional()
  .or(z.literal(""));

export const createCustomerSchema = z.object({
  branch_id: z.string().min(1, "Select a branch."),
  name: z.string().min(1, "Name is required.").max(255),
  email: emailField,
  phone: z.string().max(50).optional().or(z.literal("")),
  customer_type: z.enum(["retail", "wholesale"]),
});
export type CreateCustomerFormValues = z.infer<typeof createCustomerSchema>;

export const updateCustomerSchema = z.object({
  name: z.string().min(1, "Name is required.").max(255),
  email: emailField,
  phone: z.string().max(50).optional().or(z.literal("")),
  customer_type: z.enum(["retail", "wholesale"]),
});
export type UpdateCustomerFormValues = z.infer<typeof updateCustomerSchema>;

export const createCustomerContactSchema = z.object({
  name: z.string().min(1, "Name is required.").max(255),
  role: z.string().max(100).optional().or(z.literal("")),
  email: emailField,
  phone: z.string().max(50).optional().or(z.literal("")),
  is_primary: z.boolean(),
});
export type CreateCustomerContactFormValues = z.infer<typeof createCustomerContactSchema>;

export const createCustomerAddressSchema = z.object({
  address_type: z.enum(["billing", "shipping", "other"]),
  line1: z.string().min(1, "Address line 1 is required.").max(255),
  line2: z.string().max(255).optional().or(z.literal("")),
  city: z.string().max(100).optional().or(z.literal("")),
  state: z.string().max(100).optional().or(z.literal("")),
  postal_code: z.string().max(20).optional().or(z.literal("")),
  country: z.string().max(100).optional().or(z.literal("")),
  is_default: z.boolean(),
});
export type CreateCustomerAddressFormValues = z.infer<typeof createCustomerAddressSchema>;

export const addCustomerTagSchema = z.object({
  tag: z.string().min(1, "Enter a tag.").max(50),
});
export type AddCustomerTagFormValues = z.infer<typeof addCustomerTagSchema>;

export const createCustomerNoteSchema = z.object({
  note: z.string().min(1, "Note is required.").max(5000),
  pinned: z.boolean(),
});
export type CreateCustomerNoteFormValues = z.infer<typeof createCustomerNoteSchema>;

export const logCommunicationSchema = z.object({
  channel: z.enum(["email", "phone", "sms", "in_person", "other"]),
  direction: z.enum(["inbound", "outbound"]),
  subject: z.string().max(255).optional().or(z.literal("")),
  notes: z.string().max(5000).optional().or(z.literal("")),
});
export type LogCommunicationFormValues = z.infer<typeof logCommunicationSchema>;
