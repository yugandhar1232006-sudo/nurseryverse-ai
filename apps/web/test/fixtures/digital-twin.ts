import type {
  DigitalTwinResponse,
  DigitalTwinVersionResponse,
  DomainEventResponse,
  PageDigitalTwinVersionResponse,
  PageDomainEventResponse,
  ReplayConsistencyResponse,
  TwinSnapshot,
  VersionComparisonResponse,
} from "@/lib/api/digital-twin";
import { makePlant } from "@/test/fixtures/plants";

/** Shared fixtures for 7H Plant Digital Twin tests -- mirrors test/fixtures/plants.ts's pattern. */

export function makeTwinSnapshot(overrides: Partial<TwinSnapshot> = {}): TwinSnapshot {
  return {
    identity: {
      plant_id: makePlant().id,
      nursery_id: "22222222-2222-2222-2222-222222222222",
      species_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa01",
      variety_id: null,
      qr_code_token: "qr-token-plant-1",
      common_label: "Bench 3 - Fig #1",
      batch_number: "B-2026-001",
      registered_at: "2026-01-01T00:00:00Z",
    },
    lifecycle_state: "in_production",
    operational_status: "active",
    growth_stage: "growing",
    current_location: { branch_id: "44444444-4444-4444-4444-444444444444", zone: "Greenhouse A" },
    counts: {
      growth: 3, health: 2, watering: 5, fertilizer: 1, environmental: 1,
      disease_reports: 0, treatments: 0, movements: 0, images: 1,
      inventory_movements: 0, plant_sold: 0, plant_returned: 0,
      passports_generated: 0, qr_generated: 1, ai_predictions: 1,
    },
    latest: {
      growth: { entry_id: "g1", height_cm: 45, growth_stage: "growing", recorded_at: "2026-08-01T00:00:00Z" },
      health: { entry_id: "h1", status_label: "healthy", health_score: 92, recorded_at: "2026-08-01T00:00:00Z" },
      watering: { entry_id: "w1", volume_ml: 250, method: "drip", recorded_at: "2026-08-01T00:00:00Z" },
      fertilizer: { entry_id: "f1", product_name: "Balanced 10-10-10", schedule: null, recorded_at: "2026-08-01T00:00:00Z" },
      environmental: { entry_id: "e1", temperature_celsius: 22, humidity_percent: 55, recorded_at: "2026-08-01T00:00:00Z" },
      disease: null,
      treatment: null,
      inventory_movement: null,
      sale: null,
      return: null,
      passport: null,
      qr: { passport_id: "p1", generated_at: "2026-01-01T00:00:00Z" },
      ai_prediction: {
        prediction_id: "ai1", prediction_type: "growth_forecast", model_version: "v1",
        confidence: 0.82, generated_at: "2026-08-01T00:00:00Z",
      },
    },
    ownership: { owner_type: "nursery", customer_id: null, since: null },
    sold_at: null,
    deceased_at: null,
    deceased_reason: null,
    archived_at: null,
    archived_reason: null,
    ...overrides,
  };
}

export function makeDigitalTwin(overrides: Partial<DigitalTwinResponse> = {}): DigitalTwinResponse {
  return {
    id: "77777777-8888-9999-aaaa-bbbbbbbbbb01",
    plant_id: makePlant().id,
    nursery_id: "22222222-2222-2222-2222-222222222222",
    branch_id: "44444444-4444-4444-4444-444444444444",
    current_version: 5,
    lifecycle_state: "in_production",
    operational_status: "active",
    growth_stage: "growing",
    snapshot: makeTwinSnapshot() as unknown as Record<string, never>,
    last_event_id: "88888888-9999-aaaa-bbbb-cccccccccc01",
    last_event_type: "plant.watering_recorded",
    last_event_sequence: 5,
    last_projected_at: "2026-08-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeTwinVersion(overrides: Partial<DigitalTwinVersionResponse> = {}): DigitalTwinVersionResponse {
  return {
    id: "99999999-aaaa-bbbb-cccc-dddddddddd01",
    plant_id: makePlant().id,
    version: 5,
    snapshot: makeTwinSnapshot() as unknown as Record<string, never>,
    event_id: "88888888-9999-aaaa-bbbb-cccccccccc01",
    event_type: "plant.watering_recorded",
    event_sequence: 5,
    occurred_at: "2026-08-01T00:00:00Z",
    created_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

export function makeTwinVersionPage(items: DigitalTwinVersionResponse[] = [makeTwinVersion()]): PageDigitalTwinVersionResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeVersionComparison(overrides: Partial<VersionComparisonResponse> = {}): VersionComparisonResponse {
  return {
    plant_id: makePlant().id,
    version_a: 4,
    version_b: 5,
    snapshot_a: (makeTwinSnapshot({ growth_stage: "seedling" }) as unknown) as Record<string, never>,
    snapshot_b: makeTwinSnapshot() as unknown as Record<string, never>,
    changed_keys: ["growth_stage", "counts", "latest"],
    ...overrides,
  };
}

export function makeDomainEvent(overrides: Partial<DomainEventResponse> = {}): DomainEventResponse {
  return {
    id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee01",
    event_type: "plant.watering_recorded",
    aggregate_type: "Plant",
    aggregate_id: makePlant().id,
    nursery_id: "22222222-2222-2222-2222-222222222222",
    actor_user_id: "11111111-1111-1111-1111-111111111111",
    // `DomainEventResponse.payload` is `Record<string, never>` in the
    // generated client (same untyped-dict pattern as `TwinSnapshot`
    // above) -- cast needed for a fixture carrying real payload keys.
    payload: { plant_id: makePlant().id, watering_log_id: "w1", volume_ml: 250 } as unknown as Record<string, never>,
    request_id: "req-test-1",
    occurred_at: "2026-08-01T00:00:00Z",
    sequence: 5,
    ...overrides,
  };
}

export function makeDomainEventPage(items: DomainEventResponse[] = [makeDomainEvent()]): PageDomainEventResponse {
  return { items, meta: { page: 1, page_size: 20, total_items: items.length, total_pages: 1 } };
}

export function makeReplayConsistency(overrides: Partial<ReplayConsistencyResponse> = {}): ReplayConsistencyResponse {
  return {
    plant_id: makePlant().id,
    consistent: true,
    current_version: 5,
    differing_keys: [],
    ...overrides,
  };
}
