import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 9's *internal, authenticated* Plant
 * Passport management routes (`passport.py`'s `router`). The public,
 * unauthenticated `/public/passport/{token}` and `/public/qr/{token}`
 * routes live in a separate module, `lib/api/public-passport.ts` --
 * deliberately kept apart the same way the backend keeps `router` and
 * `public_router` in two variables in one file: this file's calls carry
 * the caller's bearer token and go through the normal permission checks,
 * the other file's calls never do and never should.
 *
 * Per docs/ux/15-plant-passport-workflow.md ("All versions remain
 * retrievable from the plant's Digital Twin ... for audit purposes"),
 * this frontend only surfaces the per-plant passport list/generate flow
 * (`components/plants/tabs/passport-tab.tsx`, on the existing `/plants/[id]`
 * page) -- the org-wide `GET /passports` list and `GET /passports/reports/summary`
 * routes exist server-side but are intentionally not wired to a standalone
 * page in this phase; see docs/frontend/15-plant-passport.md's Known
 * Limitations for why.
 */

export type PassportResponse = components["schemas"]["PassportResponse"];
export type GeneratePassportRequest = components["schemas"]["GeneratePassportRequest"];

/** `sale_id`/`sale_item_id` are optional and purely additive -- see passport.py's `generate_passport` docstring. */
export async function generatePassport(plantId: string, body: GeneratePassportRequest): Promise<PassportResponse> {
  return unwrap(() => apiClient.POST("/api/v1/plants/{plant_id}/passports", { params: { path: { plant_id: plantId } }, body }));
}

/** Every version ever generated for this plant, newest included -- append-only, never overwritten. */
export async function listPlantPassports(plantId: string): Promise<PassportResponse[]> {
  return unwrap(() => apiClient.GET("/api/v1/plants/{plant_id}/passports", { params: { path: { plant_id: plantId } } }));
}
