import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 7's Plant Digital Twin Query API
 * (`digital_twin.py`) -- every route here is a `GET`. There is no write
 * route anywhere in this module: the Digital Twin is written to exactly
 * once, internally, by a server-side event handler reacting to a
 * `domain_events` row (see that file's own module docstring). This
 * frontend module mirrors that guarantee structurally -- it exposes no
 * mutation hooks at all, and 7H's UI never offers to edit a twin
 * directly; every real change happens by using 7G's plant/record forms,
 * which is what actually produces the events this twin re-projects from.
 *
 * Authorization reuses `plants:read`, not a separate `digital_twin:read`
 * permission -- the Digital Twin is another view of a Plant the caller
 * already needs `plants:read` for (same reasoning Module 5 reused
 * `species:read` for `/plant-categories`).
 */

export type DigitalTwinResponse = components["schemas"]["DigitalTwinResponse"];
export type DigitalTwinVersionResponse = components["schemas"]["DigitalTwinVersionResponse"];
export type PageDigitalTwinResponse = components["schemas"]["Page_DigitalTwinResponse_"];
export type PageDigitalTwinVersionResponse = components["schemas"]["Page_DigitalTwinVersionResponse_"];
export type PageDomainEventResponse = components["schemas"]["Page_DomainEventResponse_"];
export type VersionComparisonResponse = components["schemas"]["VersionComparisonResponse"];
export type DomainEventResponse = components["schemas"]["DomainEventResponse"];
export type ReplayConsistencyResponse = components["schemas"]["ReplayConsistencyResponse"];

/**
 * `DigitalTwinResponse.snapshot`/`DigitalTwinVersionResponse.snapshot`
 * are typed `Record<string, never>` in the generated client -- the
 * backend's own Pydantic schema declares `snapshot: dict` with no
 * sub-schema (see schemas/digital_twin.py), so the OpenAPI generator
 * emits an opaque type, same as `AtRiskPlantResponse.result` in 7D and
 * `VersionComparisonResponse.snapshot_a/b` here. This interface is
 * hand-written from `digital_twin_service.py`'s own module docstring
 * (the exact shape every `_on_*` projector method builds) -- it is a
 * best-effort client-side type for a real, documented, but structurally
 * untyped backend contract, not a guess. Every `latest.*` entry is
 * `null` until at least one event of that kind has been projected.
 */
export interface TwinSnapshot {
  identity: {
    plant_id: string;
    nursery_id: string | null;
    species_id: string | null;
    variety_id: string | null;
    qr_code_token: string | null;
    common_label: string | null;
    batch_number: string | null;
    registered_at: string;
  };
  lifecycle_state: string;
  operational_status: string;
  growth_stage: string | null;
  current_location: { branch_id: string | null; zone: string | null };
  counts: {
    growth: number;
    health: number;
    watering: number;
    fertilizer: number;
    environmental: number;
    disease_reports: number;
    treatments: number;
    movements: number;
    images: number;
    inventory_movements: number;
    plant_sold: number;
    plant_returned: number;
    passports_generated: number;
    qr_generated: number;
    ai_predictions: number;
  };
  latest: {
    growth: { entry_id: string; height_cm: number | null; growth_stage: string | null; recorded_at: string } | null;
    health: { entry_id: string; status_label: string; health_score: number | null; recorded_at: string } | null;
    watering: { entry_id: string; volume_ml: number | null; method: string | null; recorded_at: string } | null;
    fertilizer: { entry_id: string; product_name: string; schedule: string | null; recorded_at: string } | null;
    environmental: {
      entry_id: string;
      temperature_celsius: number | null;
      humidity_percent: number | null;
      recorded_at: string;
    } | null;
    disease: { report_id: string; condition_name: string; severity: string; status: string; detected_at: string } | null;
    treatment: { treatment_id: string; disease_report_id: string; outcome: string; applied_at: string } | null;
    inventory_movement: Record<string, unknown> | null;
    sale: { sale_id: string; sale_item_id: string; customer_id: string | null; unit_price: number | null; sold_at: string } | null;
    return: {
      return_id: string;
      return_item_id: string | null;
      condition: string | null;
      refund_amount: number | null;
      returned_at: string;
    } | null;
    passport: { passport_id: string; version: number | null; generated_at: string } | null;
    qr: { passport_id: string; generated_at: string } | null;
    ai_prediction: {
      prediction_id: string;
      prediction_type: string | null;
      model_version: string | null;
      confidence: number | null;
      generated_at: string;
    } | null;
  };
  ownership: { owner_type: "nursery" | "customer"; customer_id: string | null; since: string | null };
  sold_at: string | null;
  deceased_at: string | null;
  deceased_reason: string | null;
  archived_at: string | null;
  archived_reason: string | null;
}

export interface ListDigitalTwinsParams {
  page?: number;
  page_size?: number;
  lifecycle_state?: string;
  branch_id?: string;
  sort_by?: string;
  sort_dir?: string;
}

export async function getCurrentTwin(plantId: string): Promise<DigitalTwinResponse> {
  return unwrap(() => apiClient.GET("/api/v1/plants/{id}/digital-twin", { params: { path: { id: plantId } } }));
}

export async function getTwinTimeline(plantId: string, page = 1, pageSize = 20): Promise<PageDigitalTwinVersionResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{id}/digital-twin/timeline", {
      params: { path: { id: plantId }, query: { page, page_size: pageSize } },
    }),
  );
}

export async function getVersionHistory(plantId: string, page = 1, pageSize = 20): Promise<PageDigitalTwinVersionResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{id}/digital-twin/versions", {
      params: { path: { id: plantId }, query: { page, page_size: pageSize } },
    }),
  );
}

export async function compareVersions(plantId: string, versionA: number, versionB: number): Promise<VersionComparisonResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{id}/digital-twin/versions/compare", {
      params: { path: { id: plantId }, query: { version_a: versionA, version_b: versionB } },
    }),
  );
}

export async function getVersion(plantId: string, version: number): Promise<DigitalTwinVersionResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{id}/digital-twin/versions/{version}", { params: { path: { id: plantId, version } } }),
  );
}

export async function getSnapshotByDate(plantId: string, asOf: string): Promise<DigitalTwinVersionResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{id}/digital-twin/snapshot", { params: { path: { id: plantId }, query: { as_of: asOf } } }),
  );
}

export async function getEventHistory(plantId: string, page = 1, pageSize = 20): Promise<PageDomainEventResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/plants/{id}/digital-twin/events", {
      params: { path: { id: plantId }, query: { page, page_size: pageSize } },
    }),
  );
}

/** A live diagnostic, not a cached value -- replays the plant's full event history from scratch on every call. Not fetched eagerly; only run on demand (see the "Verify" tab's own note). */
export async function verifyTwinConsistency(plantId: string): Promise<ReplayConsistencyResponse> {
  return unwrap(() => apiClient.GET("/api/v1/plants/{id}/digital-twin/verify", { params: { path: { id: plantId } } }));
}

export async function listDigitalTwins(params: ListDigitalTwinsParams = {}): Promise<PageDigitalTwinResponse> {
  return unwrap(() => apiClient.GET("/api/v1/digital-twins", { params: { query: params } }));
}
