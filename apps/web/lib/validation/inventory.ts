import { z } from "zod";

/**
 * Client-side validation for 7I's Inventory forms -- UX only, mirroring
 * apps/api/app/schemas/inventory.py's real constraints. Numeric fields
 * follow the established plain-`z.string()` + `.refine()` pattern (see
 * docs/frontend/09-organization-management.md's defect writeup).
 */

function optionalNonNegative(message = "Enter a number, 0 or more.") {
  return z.string().refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= 0), message);
}

function requiredPositiveInt(message = "Enter a whole number greater than 0.") {
  return z.string().refine((v) => /^\d+$/.test(v) && Number(v) > 0, message);
}

function optionalNonNegativeInt(message = "Enter a whole number, 0 or more.") {
  return z.string().refine((v) => v === "" || (/^\d+$/.test(v) && Number(v) >= 0), message);
}

export const createInventoryLocationSchema = z.object({
  branch_id: z.string().min(1, "Select a branch."),
  location_type: z.enum(["zone", "greenhouse", "outdoor_area", "rack", "bench", "section"]),
  name: z.string().min(1, "Name is required.").max(255),
  code: z.string().max(50).optional().or(z.literal("")),
  parent_location_id: z.string().optional().or(z.literal("")),
});
export type CreateInventoryLocationFormValues = z.infer<typeof createInventoryLocationSchema>;

export const createInventoryLineSchema = z.object({
  branch_id: z.string().min(1, "Select a branch."),
  category_id: z.string().min(1, "Select a category."),
  unit_id: z.string().min(1, "Select a unit."),
  name: z.string().min(1, "Name is required.").max(255),
  species_id: z.string().optional().or(z.literal("")),
  location_id: z.string().optional().or(z.literal("")),
  unit_cost: optionalNonNegative("Enter a cost, 0 or more."),
  unit_price: optionalNonNegative("Enter a price, 0 or more."),
  low_stock_threshold: optionalNonNegativeInt(),
  initial_quantity: optionalNonNegativeInt(),
});
export type CreateInventoryLineFormValues = z.infer<typeof createInventoryLineSchema>;

export const receiveStockSchema = z.object({
  quantity: requiredPositiveInt(),
  to_location_id: z.string().optional().or(z.literal("")),
  note: z.string().max(1000).optional().or(z.literal("")),
});
export type ReceiveStockFormValues = z.infer<typeof receiveStockSchema>;

export const transferStockSchema = z
  .object({
    quantity: requiredPositiveInt(),
    to_location_id: z.string().optional().or(z.literal("")),
    to_branch_id: z.string().optional().or(z.literal("")),
    note: z.string().max(1000).optional().or(z.literal("")),
  })
  .refine((v) => v.to_location_id !== "" || v.to_branch_id !== "", {
    message: "Specify a destination location or branch.",
    path: ["to_location_id"],
  });
export type TransferStockFormValues = z.infer<typeof transferStockSchema>;

export const reserveStockSchema = z.object({
  quantity: requiredPositiveInt(),
  reference_type: z.string().max(50).optional().or(z.literal("")),
  note: z.string().max(1000).optional().or(z.literal("")),
});
export type ReserveStockFormValues = z.infer<typeof reserveStockSchema>;

export const adjustStockSchema = z.object({
  quantity_delta: z.string().refine((v) => /^-?\d+$/.test(v) && Number(v) !== 0, "Enter a non-zero whole number (negative to remove stock)."),
  reason: z.enum(["damage", "correction", "internal_use", "purchase_order_receipt", "sale", "return", "other"]),
  note: z.string().max(1000).optional().or(z.literal("")),
});
export type AdjustStockFormValues = z.infer<typeof adjustStockSchema>;

export const markDamagedSchema = z.object({
  quantity: requiredPositiveInt(),
  note: z.string().max(1000).optional().or(z.literal("")),
});
export type MarkDamagedFormValues = z.infer<typeof markDamagedSchema>;

export const disposeStockSchema = z.object({
  quantity: requiredPositiveInt(),
  from_damaged: z.boolean(),
  note: z.string().max(1000).optional().or(z.literal("")),
});
export type DisposeStockFormValues = z.infer<typeof disposeStockSchema>;

export const sellStockSchema = z.object({
  quantity: requiredPositiveInt(),
});
export type SellStockFormValues = z.infer<typeof sellStockSchema>;

export const archiveInventoryLineSchema = z.object({
  reason: z.string().max(500).optional().or(z.literal("")),
});
export type ArchiveInventoryLineFormValues = z.infer<typeof archiveInventoryLineSchema>;
