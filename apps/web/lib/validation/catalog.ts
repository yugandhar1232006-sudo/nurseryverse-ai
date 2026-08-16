import { z } from "zod";

/**
 * Client-side validation for 7F's Species/Variety forms -- UX only,
 * mirroring apps/api/app/schemas/catalog.py's real constraints. Numeric
 * fields (`water_baseline_ml_per_week`, the two temperature fields) are
 * plain `z.string()` with a `.refine()`, not `z.coerce.number()` -- see
 * docs/frontend/09-organization-management.md's "A real TypeScript
 * defect class" section for why `z.coerce.number()` splits a schema's
 * input/output types and breaks `useForm<T>`'s single generic. Every
 * numeric field here is optional (matches the backend's `| None`), so an
 * empty string is a valid, meaningful "not specified," not a validation
 * failure.
 */

function optionalNonNegativeInt(message: string) {
  return z.string().refine((v) => v === "" || (/^\d+$/.test(v) && Number(v) >= 0), message);
}

function optionalTemperature(message: string) {
  return z.string().refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= -50 && Number(v) <= 60), message);
}

export const speciesSchema = z.object({
  category_id: z.string().min(1, "Select a category."),
  common_name: z.string().min(1, "Common name is required.").max(255),
  botanical_name: z.string().min(1, "Botanical name is required.").max(255),
  light_requirement: z.string().max(50).optional().or(z.literal("")),
  water_baseline_ml_per_week: optionalNonNegativeInt("Enter a whole number of mL, 0 or more."),
  soil_type: z.string().max(100).optional().or(z.literal("")),
  temperature_min_celsius: optionalTemperature("Enter a temperature between -50 and 60°C."),
  temperature_max_celsius: optionalTemperature("Enter a temperature between -50 and 60°C."),
  disease_susceptibility: z.string().max(500).optional().or(z.literal("")),
});
export type SpeciesFormValues = z.infer<typeof speciesSchema>;

export const plantVarietySchema = z.object({
  species_id: z.string().min(1, "Select a species."),
  name: z.string().min(1, "Variety name is required.").max(255),
  description: z.string().max(500).optional().or(z.literal("")),
});
export type PlantVarietyFormValues = z.infer<typeof plantVarietySchema>;
