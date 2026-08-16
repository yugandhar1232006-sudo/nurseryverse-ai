import { http, HttpResponse } from "msw";

import {
  makeDigitalTwin,
  makeDomainEventPage,
  makeReplayConsistency,
  makeTwinVersion,
  makeTwinVersionPage,
  makeVersionComparison,
} from "@/test/fixtures/digital-twin";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7H's Module 7 Plant Digital Twin
 * Query API. `/versions/compare` is registered before
 * `/versions/:version` -- mirrors the real backend's own route
 * registration-order requirement (see `digital_twin.py`'s
 * `compare_versions` docstring: "compare" would otherwise match the
 * `{version}: int` path param and fail to parse), so a test exercising
 * comparison isn't accidentally routed to the single-version handler.
 */
export const digitalTwinHandlers = [
  http.get(`${BASE}/api/v1/plants/:id/digital-twin`, () => HttpResponse.json(makeDigitalTwin())),
  http.get(`${BASE}/api/v1/plants/:id/digital-twin/timeline`, () => HttpResponse.json(makeTwinVersionPage())),
  http.get(`${BASE}/api/v1/plants/:id/digital-twin/versions/compare`, () => HttpResponse.json(makeVersionComparison())),
  http.get(`${BASE}/api/v1/plants/:id/digital-twin/versions/:version`, () => HttpResponse.json(makeTwinVersion())),
  http.get(`${BASE}/api/v1/plants/:id/digital-twin/versions`, () => HttpResponse.json(makeTwinVersionPage())),
  http.get(`${BASE}/api/v1/plants/:id/digital-twin/snapshot`, () => HttpResponse.json(makeTwinVersion())),
  http.get(`${BASE}/api/v1/plants/:id/digital-twin/events`, () => HttpResponse.json(makeDomainEventPage())),
  http.get(`${BASE}/api/v1/plants/:id/digital-twin/verify`, () => HttpResponse.json(makeReplayConsistency())),
  http.get(`${BASE}/api/v1/digital-twins`, () => HttpResponse.json({ items: [makeDigitalTwin()], meta: { page: 1, page_size: 20, total_items: 1, total_pages: 1 } })),
];
