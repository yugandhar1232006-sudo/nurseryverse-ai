import { z } from "zod";

/**
 * Client-side validation for 7J's Sales forms -- UX only, mirroring
 * apps/api/app/schemas/sales.py's real constraints. Follows the
 * established plain-`z.string()` (never `z.coerce.number()`) pattern from
 * 7E/7I.
 *
 * Line-item builders (Quotation/Sales Order creation) only build
 * inventory-linked (bulk-stock) lines in this initial build -- see
 * docs/frontend/14-sales-crm.md's Known Limitations for why plant-linked
 * lines are deferred.
 */

function requiredPositiveInt(message = "Enter a whole number greater than 0.") {
  return z.string().refine((v) => /^\d+$/.test(v) && Number(v) > 0, message);
}

function requiredNonNegative(message = "Enter a number, 0 or more.") {
  return z.string().refine((v) => !Number.isNaN(Number(v)) && Number(v) >= 0, message);
}

function requiredPositive(message = "Enter a number greater than 0.") {
  return z.string().refine((v) => !Number.isNaN(Number(v)) && Number(v) > 0, message);
}

function optionalNonNegative(message = "Enter a number, 0 or more.") {
  return z.string().refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= 0), message);
}

function optionalRate(message = "Enter a rate between 0 and 1 (e.g. 0.08 for 8%).") {
  return z.string().refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= 0 && Number(v) <= 1), message);
}

export const orderLineItemSchema = z.object({
  inventory_id: z.string().min(1, "Select an inventory line."),
  description: z.string().max(500).optional().or(z.literal("")),
  quantity: requiredPositiveInt(),
  unit_price: requiredNonNegative("Enter a unit price, 0 or more."),
  discount_amount: optionalNonNegative(),
});
export type OrderLineItemFormValues = z.infer<typeof orderLineItemSchema>;

export const createQuotationSchema = z.object({
  branch_id: z.string().min(1, "Select a branch."),
  customer_id: z.string().min(1, "Select a customer."),
  items: z.array(orderLineItemSchema).min(1, "Add at least one line item."),
  tax_rate: optionalRate(),
  header_discount: optionalNonNegative(),
  valid_until: z.string().optional().or(z.literal("")),
  note: z.string().max(2000).optional().or(z.literal("")),
});
export type CreateQuotationFormValues = z.infer<typeof createQuotationSchema>;

export const createSalesOrderSchema = z.object({
  branch_id: z.string().min(1, "Select a branch."),
  customer_id: z.string().min(1, "Select a customer."),
  items: z.array(orderLineItemSchema).min(1, "Add at least one line item."),
  tax_rate: optionalRate(),
  header_discount: optionalNonNegative(),
});
export type CreateSalesOrderFormValues = z.infer<typeof createSalesOrderSchema>;

export const quotationStatusChangeSchema = z.object({
  status: z.enum(["draft", "sent", "accepted", "rejected", "expired"]),
});
export type QuotationStatusChangeFormValues = z.infer<typeof quotationStatusChangeSchema>;

export const cancelOrderSchema = z.object({
  reason: z.string().max(1000).optional().or(z.literal("")),
});
export type CancelOrderFormValues = z.infer<typeof cancelOrderSchema>;

export const recordPaymentSchema = z.object({
  amount: requiredPositive(),
  method: z.enum(["cash", "upi", "card", "bank_transfer", "other"]),
  reference: z.string().max(100).optional().or(z.literal("")),
});
export type RecordPaymentFormValues = z.infer<typeof recordPaymentSchema>;

export const returnLineItemSchema = z.object({
  sale_item_id: z.string().min(1, "Select a line item."),
  quantity: requiredPositiveInt(),
  restock: z.boolean(),
  condition: z.enum(["resalable", "damaged", "disposed"]),
});
export type ReturnLineItemFormValues = z.infer<typeof returnLineItemSchema>;

export const createReturnSchema = z.object({
  customer_id: z.string().min(1, "Select a customer."),
  reason: z.string().max(2000).optional().or(z.literal("")),
  items: z.array(returnLineItemSchema).min(1, "Add at least one line item."),
});
export type CreateReturnFormValues = z.infer<typeof createReturnSchema>;

export const rejectReturnSchema = z.object({
  reason: z.string().max(1000).optional().or(z.literal("")),
});
export type RejectReturnFormValues = z.infer<typeof rejectReturnSchema>;

export const processRefundSchema = z.object({
  branch_id: z.string().min(1, "Select a branch."),
  amount: requiredPositive(),
  method: z.enum(["cash", "upi", "card", "bank_transfer", "other"]),
  return_id: z.string().optional().or(z.literal("")),
  invoice_id: z.string().optional().or(z.literal("")),
  sale_id: z.string().optional().or(z.literal("")),
  reference: z.string().max(100).optional().or(z.literal("")),
});
export type ProcessRefundFormValues = z.infer<typeof processRefundSchema>;
