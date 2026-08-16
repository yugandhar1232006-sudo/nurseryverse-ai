import type { PassportResponse } from "@/lib/api/passport";
import type { PassportContent, PublicPassportResponse, QRScanResponseRaw, QrScanContent } from "@/lib/api/public-passport";

/** Shared fixtures for 7K Plant Passport tests -- mirrors test/fixtures/inventory.ts's pattern. */

export function makePassportContent(overrides: Partial<PassportContent> = {}): PassportContent {
  return {
    plant_origin: {
      species: "Ficus lyrata",
      botanical_name: "Ficus lyrata",
      variety: null,
      batch_number: "BATCH-001",
      planted_at: "2026-01-01T00:00:00Z",
      common_label: "Bench 3 - Fig #1",
    },
    nursery_information: { name: "Green Thumb Nursery", contact_email: "hello@greenthumb.test", branch_name: "Main Branch" },
    care_guide: {
      light_requirement: "Bright indirect",
      water_baseline_ml_per_week: 500,
      soil_type: "Well-draining potting mix",
      temperature_min_celsius: 15,
      temperature_max_celsius: 27,
    },
    growth_timeline: [{ height_cm: 45, growth_stage: "vegetative", recorded_at: "2026-06-01T00:00:00Z" }],
    health_timeline: [{ status_label: "Healthy", health_score: 92, recorded_at: "2026-06-01T00:00:00Z" }],
    ai_care_recommendations: [],
    purchase_information: null,
    ...overrides,
  };
}

export function makePassport(overrides: Partial<PassportResponse> = {}): PassportResponse {
  return {
    id: "passport-01",
    plant_id: "cccccccc-cccc-cccc-cccc-cccccccccc01",
    version: 1,
    public_token: "tok_abc123",
    public_url: "http://localhost:3000/passport/tok_abc123",
    token_expires_at: null,
    content_snapshot: makePassportContent() as unknown as Record<string, never>,
    generated_by_user_id: "11111111-1111-1111-1111-111111111111",
    generated_at: "2026-06-15T00:00:00Z",
    ...overrides,
  };
}

export function makePublicPassport(overrides: Partial<PublicPassportResponse> = {}): PublicPassportResponse {
  return {
    passport_number: "NVA-PP-ABCD1234",
    version: 1,
    content: makePassportContent() as unknown as Record<string, never>,
    generated_at: "2026-06-15T00:00:00Z",
    ...overrides,
  };
}

export function makeQrScanContent(overrides: Partial<QrScanContent> = {}): QrScanContent {
  return {
    passport: makePassportContent(),
    care_instructions: makePassportContent().care_guide,
    water_schedule: { baseline_ml_per_week: 500 },
    fertilizer_schedule: { product_name: "10-10-10 fertilizer", schedule: "Monthly", next_application_date: "2026-09-01" },
    health_status: { status_label: "Healthy", health_score: 92 },
    growth_timeline: [{ height_cm: 46, growth_stage: "vegetative", recorded_at: "2026-08-01T00:00:00Z" }],
    ai_recommendations: [],
    ...overrides,
  };
}

export function makeQrScanResponse(overrides: Partial<QRScanResponseRaw> = {}): QRScanResponseRaw {
  const content = makeQrScanContent();
  return {
    passport: content.passport as unknown as Record<string, never>,
    care_instructions: content.care_instructions as unknown as Record<string, never>,
    water_schedule: content.water_schedule as unknown as Record<string, never>,
    fertilizer_schedule: content.fertilizer_schedule as unknown as Record<string, never>,
    health_status: content.health_status as unknown as Record<string, never>,
    growth_timeline: content.growth_timeline as unknown as Record<string, never>[],
    ai_recommendations: content.ai_recommendations as unknown as Record<string, never>[],
    ...overrides,
  };
}
