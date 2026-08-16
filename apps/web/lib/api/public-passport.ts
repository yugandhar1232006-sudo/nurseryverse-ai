import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 9's *public, unauthenticated* Plant
 * Passport & QR Intelligence routes (`passport.py`'s `public_router`).
 * Neither route below ever sends an `Authorization` header (there is no
 * session to attach one from on this page -- see
 * `app/(passport)/passport/[token]/page.tsx`'s own docstring for why it
 * lives outside both `(app)`'s auth gate and `(public)`'s
 * signed-out-visitor chrome), and neither route ever returns a database
 * id, `nursery_id`, `branch_id`, or `plant_id` -- only a derived
 * `passport_number` display label and the passport's own frozen content.
 * A bad/forged/expired token is a generic 404 either way, so `unwrap`'s
 * existing `ApiError` handling covers this with no special-casing.
 *
 * `PublicPassportResponse.content` / `QRScanResponse`'s several
 * `Record<string, never>` fields are the same "opaque JSON blob" pattern
 * `lib/api/digital-twin.ts`'s `TwinSnapshot` already documents -- the
 * backend's own Pydantic schema declares `dict[str, Any]` with no
 * sub-schema, so the OpenAPI generator emits an opaque type. The
 * `PassportContent`/`QrScanContent` interfaces below are hand-written
 * from `passport_service.py`'s `_build_snapshot`/`scan` methods (the
 * exact shape each one builds), not a guess.
 */

export type PublicPassportResponse = components["schemas"]["PublicPassportResponse"];
export type QRScanResponseRaw = components["schemas"]["QRScanResponse"];

export interface PassportContent {
  plant_origin: {
    species: string | null;
    botanical_name: string | null;
    variety: string | null;
    batch_number: string | null;
    planted_at: string | null;
    common_label: string | null;
  };
  nursery_information: {
    name: string | null;
    contact_email: string | null;
    branch_name: string | null;
  };
  care_guide: {
    light_requirement: string | null;
    water_baseline_ml_per_week: number | null;
    soil_type: string | null;
    temperature_min_celsius: number | null;
    temperature_max_celsius: number | null;
  };
  growth_timeline: Array<{ height_cm: number | null; growth_stage: string | null; recorded_at: string | null }>;
  health_timeline: Array<{ status_label: string | null; health_score: number | null; recorded_at: string | null }>;
  // Always [] until Module 10 (AI Platform) writes AI recommendations for
  // a plant -- the identical, already-established precedent 7H's Digital
  // Twin and 7J's Sales module both document at their own call sites.
  ai_care_recommendations: unknown[];
  purchase_information: { sale_id: string; sold_at: string | null; unit_price: string | null } | null;
}

export interface QrScanContent {
  passport: PassportContent;
  care_instructions: PassportContent["care_guide"] | null;
  water_schedule: { baseline_ml_per_week: number | null } | null;
  fertilizer_schedule: { product_name: string; schedule: string | null; next_application_date: string | null } | null;
  health_status: { status_label: string | null; health_score: number | null } | null;
  growth_timeline: PassportContent["growth_timeline"];
  ai_recommendations: unknown[];
}

/** The public, factual, point-in-time certificate view -- `passport_number` is a one-way digest, never the raw UUID. */
export async function getPublicPassport(token: string): Promise<PublicPassportResponse> {
  return unwrap(() => apiClient.GET("/api/v1/public/passport/{token}", { params: { path: { token } } }));
}

/**
 * The "what does this plant need right now" live view -- recording a
 * `QRScanEvent` server-side as a side effect of this exact call (see
 * `QRService.scan`'s docstring), so this should only be called once per
 * genuine page load, not spuriously refetched.
 */
export async function scanPassportQr(token: string): Promise<QRScanResponseRaw> {
  return unwrap(() => apiClient.GET("/api/v1/public/qr/{token}", { params: { path: { token } } }));
}
