import { http, HttpResponse } from "msw";

import { makePlantCategory, makePlantVarietyPage, makeSpeciesPage } from "@/test/fixtures/catalog";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7F's Module 5 Species Catalog routes
 * -- same real-`apiClient` interception approach as
 * organization-handlers.ts.
 *
 * `GET /api/v1/species/:id` (a real defect found in 7G): `lib/catalog/
 * queries.ts`'s `useSpeciesDetailQuery` was written in 7F but had no
 * real consumer at the time -- `species-detail-dialog.tsx` takes the
 * species as a prop from the already-loaded list row instead of
 * re-fetching it. So this handler was never added, and the gap stayed
 * invisible through all of 7F's own tests. 7G's `plant-header.tsx` is
 * the first real caller (it only has a `species_id`, not the full
 * species object, so it must fetch by id) -- surfaced as a genuine "MSW
 * Error: intercepted a request without a matching request handler" in
 * two of 7G's own tests. Fixed here, in catalog-handlers.ts (not
 * plants-handlers.ts), since `/species/:id` is rightfully a catalog
 * resource regardless of which phase's component ends up calling it.
 */
export const catalogHandlers = [
  http.get(`${BASE}/api/v1/plant-categories`, () => HttpResponse.json([makePlantCategory()])),
  http.get(`${BASE}/api/v1/species`, () => HttpResponse.json(makeSpeciesPage())),
  http.get(`${BASE}/api/v1/species/:id`, () => HttpResponse.json(makeSpeciesPage().items[0])),
  http.post(`${BASE}/api/v1/species`, () => HttpResponse.json(makeSpeciesPage().items[0])),
  http.patch(`${BASE}/api/v1/species/:id`, () => HttpResponse.json(makeSpeciesPage().items[0])),
  http.delete(`${BASE}/api/v1/species/:id`, () => HttpResponse.json(makeSpeciesPage().items[0])),
  http.get(`${BASE}/api/v1/plant-varieties`, () => HttpResponse.json(makePlantVarietyPage())),
  http.post(`${BASE}/api/v1/plant-varieties`, () => HttpResponse.json(makePlantVarietyPage().items[0])),
  http.patch(`${BASE}/api/v1/plant-varieties/:id`, () => HttpResponse.json(makePlantVarietyPage().items[0])),
  http.delete(`${BASE}/api/v1/plant-varieties/:id`, () => HttpResponse.json(makePlantVarietyPage().items[0])),
];
