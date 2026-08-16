import { http, HttpResponse } from "msw";

import {
  makeDiseaseReport,
  makeEnvironmentalPage,
  makeEnvironmentalRecord,
  makeFertilizerPage,
  makeFertilizerRecord,
  makeGrowthPage,
  makeGrowthRecord,
  makeHealthPage,
  makeHealthRecord,
  makePlant,
  makePlantImage,
  makePlantPage,
  makePlantTransfer,
  makeTimelinePage,
  makeTreatment,
  makeWateringPage,
  makeWateringRecord,
} from "@/test/fixtures/plants";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7G's Module 6 Plant Lifecycle routes
 * (registration/profile/status/move/archive/images/timeline plus the
 * five immutable record types and disease reports/treatments). Listed
 * before `shellHandlers` in test/msw/server.ts on purpose -- same
 * handler-shadowing risk documented there for `GET /api/v1/plants`
 * (7C's global-search fan-out already registers its own empty stub).
 */
export const plantsHandlers = [
  http.get(`${BASE}/api/v1/plants`, () => HttpResponse.json(makePlantPage())),
  http.post(`${BASE}/api/v1/plants`, () => HttpResponse.json(makePlant())),
  http.get(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())),
  http.patch(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())),
  http.post(`${BASE}/api/v1/plants/:id/status`, () => HttpResponse.json(makePlant())),
  http.post(`${BASE}/api/v1/plants/:id/move`, () => HttpResponse.json(makePlant())),
  http.get(`${BASE}/api/v1/plants/:id/movement-history`, () => HttpResponse.json([makePlantTransfer()])),
  http.post(`${BASE}/api/v1/plants/:id/archive`, () => HttpResponse.json(makePlant({ archived_at: "2026-08-10T00:00:00Z" }))),
  http.get(`${BASE}/api/v1/plants/:id/images`, () => HttpResponse.json([makePlantImage()])),
  http.post(`${BASE}/api/v1/plants/:id/images`, () => HttpResponse.json(makePlantImage())),
  http.get(`${BASE}/api/v1/plants/:id/timeline`, () => HttpResponse.json(makeTimelinePage())),

  http.get(`${BASE}/api/v1/plants/:plant_id/growth-timeline`, () => HttpResponse.json(makeGrowthPage())),
  http.post(`${BASE}/api/v1/plants/:plant_id/growth-timeline`, () => HttpResponse.json(makeGrowthRecord())),

  http.get(`${BASE}/api/v1/plants/:plant_id/health-history`, () => HttpResponse.json(makeHealthPage())),
  http.post(`${BASE}/api/v1/plants/:plant_id/health-history`, () => HttpResponse.json(makeHealthRecord())),

  http.get(`${BASE}/api/v1/plants/:plant_id/watering-logs`, () => HttpResponse.json(makeWateringPage())),
  http.post(`${BASE}/api/v1/plants/:plant_id/watering-logs`, () => HttpResponse.json(makeWateringRecord())),

  http.get(`${BASE}/api/v1/plants/:plant_id/fertilizer-logs`, () => HttpResponse.json(makeFertilizerPage())),
  http.post(`${BASE}/api/v1/plants/:plant_id/fertilizer-logs`, () => HttpResponse.json(makeFertilizerRecord())),

  http.get(`${BASE}/api/v1/plants/:plant_id/environmental-readings`, () => HttpResponse.json(makeEnvironmentalPage())),
  http.post(`${BASE}/api/v1/plants/:plant_id/environmental-readings`, () => HttpResponse.json(makeEnvironmentalRecord())),

  http.get(`${BASE}/api/v1/plants/:plant_id/disease-reports`, () => HttpResponse.json([makeDiseaseReport()])),
  http.post(`${BASE}/api/v1/plants/:plant_id/disease-reports`, () => HttpResponse.json(makeDiseaseReport())),
  http.post(`${BASE}/api/v1/disease-reports/:id/confirm`, () => HttpResponse.json(makeDiseaseReport({ status: "confirmed" }))),
  http.post(`${BASE}/api/v1/disease-reports/:id/dismiss`, () => HttpResponse.json(makeDiseaseReport({ status: "dismissed" }))),
  http.get(`${BASE}/api/v1/disease-reports/:id/treatments`, () => HttpResponse.json([makeTreatment()])),
  http.post(`${BASE}/api/v1/disease-reports/:id/treatments`, () => HttpResponse.json(makeTreatment())),
];
