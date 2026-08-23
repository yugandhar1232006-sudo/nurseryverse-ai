import { z } from "zod";

/**
 * Client-side validation for 7G's Plant Lifecycle forms -- UX only,
 * mirroring apps/api/app/schemas/plants.py's real constraints. Numeric
 * fields follow the same plain-`z.string()` + `.refine()` pattern
 * established in lib/validation/organization.ts/catalog.ts (see
 * docs/frontend/09-organization-management.md's defect writeup for why
 * `z.coerce.number()`/`.default()` break `useForm<T>`'s single generic).
 */

function optionalNonNegative(message = "Enter a number, 0 or more.") {
  return z.string().refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= 0), message);
}

function optionalNonNegativeInt(message = "Enter a whole number, 0 or more.") {
  return z.string().refine((v) => v === "" || (/^\d+$/.test(v) && Number(v) >= 0), message);
}

function optionalPercent(message = "Enter a percentage between 0 and 100.") {
  return z.string().refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= 0 && Number(v) <= 100), message);
}

export const registerPlantSchema = z.object({
  branch_id: z.string().min(1, "Select a branch."),
  species_id: z.string().min(1, "Select a species."),
  variety_id: z.string().optional().or(z.literal("")),
  common_label: z.string().max(255).optional().or(z.literal("")),
  zone: z.string().max(100).optional().or(z.literal("")),
  batch_number: z.string().max(100).optional().or(z.literal("")),
  supplier_id: z.string().optional().or(z.literal("")),
  purchase_price: optionalNonNegative("Enter a purchase price, 0 or more."),
  purchase_date: z.string().optional().or(z.literal("")),
  planted_at: z.string().optional().or(z.literal("")),
  price: optionalNonNegative("Enter a price, 0 or more."),
  description: z.string().max(5000).optional().or(z.literal("")),
});
export type RegisterPlantFormValues = z.infer<typeof registerPlantSchema>;

export const movePlantSchema = z
  .object({
    to_branch_id: z.string().optional().or(z.literal("")),
    to_zone: z.string().max(100).optional().or(z.literal("")),
    note: z.string().optional().or(z.literal("")),
  })
  .refine((v) => v.to_branch_id !== "" || v.to_zone !== "", {
    message: "Specify a destination branch or zone.",
    path: ["to_zone"],
  });
export type MovePlantFormValues = z.infer<typeof movePlantSchema>;

export const transitionStatusSchema = z.object({
  to_status: z.enum(["in_production", "ready_for_sale", "under_treatment", "sold", "deceased"]),
  reason: z.string().optional().or(z.literal("")),
});
export type TransitionStatusFormValues = z.infer<typeof transitionStatusSchema>;

export const archivePlantSchema = z.object({
  reason: z.string().optional().or(z.literal("")),
});
export type ArchivePlantFormValues = z.infer<typeof archivePlantSchema>;

export const updatePlantProfileSchema = z.object({
  common_label: z.string().max(255).optional().or(z.literal("")),
  variety_id: z.string().optional().or(z.literal("")),
  batch_number: z.string().max(100).optional().or(z.literal("")),
  supplier_id: z.string().optional().or(z.literal("")),
  purchase_price: optionalNonNegative("Enter a purchase price, 0 or more."),
  purchase_date: z.string().optional().or(z.literal("")),
  price: optionalNonNegative("Enter a price, 0 or more."),
  description: z.string().max(5000).optional().or(z.literal("")),
});
export type UpdatePlantProfileFormValues = z.infer<typeof updatePlantProfileSchema>;

export const uploadPlantImageSchema = z.object({
  url: z.string().min(1, "A URL is required.").url("Enter a valid URL."),
  thumbnail_url: z.string().refine((v) => v === "" || /^https?:\/\//.test(v), "Enter a valid URL."),
  caption: z.string().max(255).optional().or(z.literal("")),
});
export type UploadPlantImageFormValues = z.infer<typeof uploadPlantImageSchema>;

export const recordGrowthSchema = z.object({
  height_cm: optionalNonNegative(),
  spread_cm: optionalNonNegative(),
  leaf_count: optionalNonNegativeInt(),
  flower_count: optionalNonNegativeInt(),
  fruit_count: optionalNonNegativeInt(),
  growth_stage: z.string().max(50).optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type RecordGrowthFormValues = z.infer<typeof recordGrowthSchema>;

export const recordHealthSchema = z.object({
  status_label: z.string().min(1, "Enter a status label.").max(50),
  health_score: optionalPercent("Health score must be between 0 and 100."),
  notes: z.string().optional().or(z.literal("")),
});
export type RecordHealthFormValues = z.infer<typeof recordHealthSchema>;

export const recordWateringSchema = z.object({
  volume_ml: optionalNonNegative(),
  method: z.string().max(50).optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type RecordWateringFormValues = z.infer<typeof recordWateringSchema>;

export const recordFertilizerSchema = z.object({
  product_name: z.string().min(1, "Product name is required.").max(255),
  quantity_ml: optionalNonNegative(),
  npk_ratio: z.string().max(20).optional().or(z.literal("")),
  method: z.string().max(50).optional().or(z.literal("")),
  notes: z.string().optional().or(z.literal("")),
});
export type RecordFertilizerFormValues = z.infer<typeof recordFertilizerSchema>;

export const recordEnvironmentalSchema = z.object({
  temperature_celsius: z.string().refine((v) => v === "" || !Number.isNaN(Number(v)), "Enter a valid temperature."),
  humidity_percent: optionalPercent(),
  soil_moisture_percent: optionalPercent(),
  light_lux: optionalNonNegative(),
  ph_level: z.string().refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= 0 && Number(v) <= 14), "pH must be between 0 and 14."),
});
export type RecordEnvironmentalFormValues = z.infer<typeof recordEnvironmentalSchema>;

export const createDiseaseReportSchema = z.object({
  condition_name: z.string().min(1, "Condition name is required.").max(255),
  severity: z.enum(["low", "medium", "high", "critical"]),
});
export type CreateDiseaseReportFormValues = z.infer<typeof createDiseaseReportSchema>;

export const dismissDiseaseReportSchema = z.object({
  dismissed_reason: z.string().min(1, "A reason is required."),
});
export type DismissDiseaseReportFormValues = z.infer<typeof dismissDiseaseReportSchema>;

export const applyTreatmentSchema = z.object({
  description: z.string().min(1, "Describe the treatment."),
  outcome: z.enum(["ongoing", "recovered", "plant_lost"]),
});
export type ApplyTreatmentFormValues = z.infer<typeof applyTreatmentSchema>;
