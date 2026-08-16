import type {
  PagePlantResponse,
  PagePlantTimelineEntryResponse,
  PlantImageResponse,
  PlantResponse,
  PlantTimelineEntryResponse,
  PlantTransferResponse,
} from "@/lib/api/plants";
import type {
  EnvironmentalRecordResponse,
  FertilizerRecordResponse,
  GrowthRecordResponse,
  HealthRecordResponse,
  PageEnvironmentalRecordResponse,
  PageFertilizerRecordResponse,
  PageGrowthRecordResponse,
  PageHealthRecordResponse,
  PageWateringRecordResponse,
  WateringRecordResponse,
} from "@/lib/api/plant-records";
import type { DiseaseReportResponse, TreatmentResponse } from "@/lib/api/disease-reports";

/** Shared fixtures for 7G Plant Lifecycle tests -- mirrors test/fixtures/catalog.ts's pattern. */

export function makePlant(overrides: Partial<PlantResponse> = {}): PlantResponse {
  return {
    id: "cccccccc-cccc-cccc-cccc-cccccccccc01",
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: "44444444-4444-4444-4444-444444444444",
    species_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01",
    variety_id: null,
    common_label: "Bench 3 - Fig #1",
    zone: "Greenhouse A",
    status: "in_production",
    qr_code_token: "qr-token-plant-1",
    price: 24.99,
    planted_at: "2026-01-01T00:00:00Z",
    sold_at: null,
    deceased_at: null,
    deceased_reason: null,
    batch_number: "B-2026-001",
    supplier_id: null,
    purchase_price: null,
    purchase_date: null,
    registered_by_user_id: "11111111-1111-1111-1111-111111111111",
    archived_at: null,
    archived_reason: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    age_days: 30,
    ...overrides,
  } as PlantResponse;
}

export function makePlantPage(items: PlantResponse[] = [makePlant()]): PagePlantResponse {
  return {
    items,
    meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 },
  };
}

export function makeGrowthRecord(overrides: Partial<GrowthRecordResponse> = {}): GrowthRecordResponse {
  return {
    id: "dddddddd-dddd-dddd-dddd-dddddddddd01",
    plant_id: makePlant().id,
    height_cm: 45,
    spread_cm: 30,
    leaf_count: 12,
    flower_count: 0,
    fruit_count: 0,
    growth_stage: "growing",
    photo_url: null,
    photo_urls: null,
    notes: "Healthy new growth.",
    recorded_by_user_id: "11111111-1111-1111-1111-111111111111",
    recorded_at: "2026-08-01T00:00:00Z",
    ...overrides,
  } as GrowthRecordResponse;
}

export function makeGrowthPage(items: GrowthRecordResponse[] = [makeGrowthRecord()]): PageGrowthRecordResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeHealthRecord(overrides: Partial<HealthRecordResponse> = {}): HealthRecordResponse {
  return {
    id: "eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01",
    plant_id: makePlant().id,
    status_label: "healthy",
    health_score: 92,
    notes: null,
    photo_url: null,
    is_ai_observation: false,
    recorded_by_user_id: "11111111-1111-1111-1111-111111111111",
    recorded_at: "2026-08-01T00:00:00Z",
    ...overrides,
  } as HealthRecordResponse;
}

export function makeHealthPage(items: HealthRecordResponse[] = [makeHealthRecord()]): PageHealthRecordResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeWateringRecord(overrides: Partial<WateringRecordResponse> = {}): WateringRecordResponse {
  return {
    id: "ffffffff-ffff-ffff-ffff-ffffffffff01",
    plant_id: makePlant().id,
    branch_id: "44444444-4444-4444-4444-444444444444",
    zone: "Greenhouse A",
    volume_ml: 250,
    method: "drip",
    notes: null,
    recorded_by_user_id: "11111111-1111-1111-1111-111111111111",
    recorded_at: "2026-08-01T00:00:00Z",
    ...overrides,
  } as WateringRecordResponse;
}

export function makeWateringPage(items: WateringRecordResponse[] = [makeWateringRecord()]): PageWateringRecordResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeFertilizerRecord(overrides: Partial<FertilizerRecordResponse> = {}): FertilizerRecordResponse {
  return {
    id: "11111111-2222-3333-4444-555555555501",
    plant_id: makePlant().id,
    branch_id: "44444444-4444-4444-4444-444444444444",
    zone: "Greenhouse A",
    product_name: "Balanced 10-10-10",
    quantity_ml: 50,
    npk_ratio: "10-10-10",
    method: "soil drench",
    schedule: null,
    next_application_date: null,
    notes: null,
    recorded_by_user_id: "11111111-1111-1111-1111-111111111111",
    recorded_at: "2026-08-01T00:00:00Z",
    ...overrides,
  } as FertilizerRecordResponse;
}

export function makeFertilizerPage(items: FertilizerRecordResponse[] = [makeFertilizerRecord()]): PageFertilizerRecordResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeEnvironmentalRecord(overrides: Partial<EnvironmentalRecordResponse> = {}): EnvironmentalRecordResponse {
  return {
    id: "22222222-3333-4444-5555-666666666601",
    plant_id: makePlant().id,
    branch_id: "44444444-4444-4444-4444-444444444444",
    zone: "Greenhouse A",
    temperature_celsius: 22,
    humidity_percent: 55,
    soil_moisture_percent: 40,
    light_lux: 8000,
    ph_level: 6.5,
    weather_snapshot: null,
    source: "manual",
    recorded_at: "2026-08-01T00:00:00Z",
    ...overrides,
  } as EnvironmentalRecordResponse;
}

export function makeEnvironmentalPage(
  items: EnvironmentalRecordResponse[] = [makeEnvironmentalRecord()],
): PageEnvironmentalRecordResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeDiseaseReport(overrides: Partial<DiseaseReportResponse> = {}): DiseaseReportResponse {
  return {
    id: "33333333-4444-5555-6666-777777777701",
    plant_id: makePlant().id,
    condition_name: "Root rot",
    status: "draft",
    severity: "medium",
    is_ai_sourced: false,
    ai_confidence: null,
    photo_url: null,
    confirmed_by_user_id: null,
    confirmed_at: null,
    dismissed_reason: null,
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  } as DiseaseReportResponse;
}

export function makeTreatment(overrides: Partial<TreatmentResponse> = {}): TreatmentResponse {
  return {
    id: "44444444-5555-6666-7777-888888888801",
    disease_report_id: makeDiseaseReport().id,
    description: "Reduced watering frequency and repotted with fresh soil.",
    outcome: "ongoing",
    applied_by_user_id: "11111111-1111-1111-1111-111111111111",
    applied_at: "2026-08-02T00:00:00Z",
    ...overrides,
  };
}

export function makePlantImage(overrides: Partial<PlantImageResponse> = {}): PlantImageResponse {
  return {
    id: "55555555-6666-7777-8888-999999999901",
    plant_id: makePlant().id,
    url: "https://example.com/photo.jpg",
    thumbnail_url: null,
    caption: "First photo",
    captured_at: "2026-08-01T00:00:00Z",
    uploaded_by_user_id: "11111111-1111-1111-1111-111111111111",
    ...overrides,
  };
}

export function makePlantTransfer(overrides: Partial<PlantTransferResponse> = {}): PlantTransferResponse {
  return {
    id: "66666666-7777-8888-9999-aaaaaaaaaa01",
    plant_id: makePlant().id,
    from_branch_id: "44444444-4444-4444-4444-444444444444",
    to_branch_id: "77777777-7777-7777-7777-777777777777",
    from_zone: "Greenhouse A",
    to_zone: "Greenhouse B",
    note: "Rebalancing stock.",
    transferred_by_user_id: "11111111-1111-1111-1111-111111111111",
    transferred_at: "2026-08-05T00:00:00Z",
    ...overrides,
  };
}

export function makeTimelineEntry(overrides: Partial<PlantTimelineEntryResponse> = {}): PlantTimelineEntryResponse {
  return {
    event_type: "plant.registered",
    occurred_at: "2026-01-01T00:00:00Z",
    summary: "Plant registered at Main Branch.",
    source_id: makePlant().id,
    actor_user_id: "11111111-1111-1111-1111-111111111111",
    ...overrides,
  };
}

export function makeTimelinePage(items: PlantTimelineEntryResponse[] = [makeTimelineEntry()]): PagePlantTimelineEntryResponse {
  return { items, meta: { page: 1, page_size: 30, total_items: items.length, total_pages: 1 } };
}
