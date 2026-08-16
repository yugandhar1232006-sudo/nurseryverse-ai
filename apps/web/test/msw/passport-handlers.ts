import { http, HttpResponse } from "msw";

import { makePassport, makePublicPassport, makeQrScanResponse } from "@/test/fixtures/passport";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7K's Module 9 Plant Passport routes --
 * both the internal, authenticated `/plants/{plant_id}/passports` routes
 * and the public, unauthenticated `/public/passport/{token}`/`/public/qr/{token}`
 * routes, kept in one file since they're a single small module (unlike
 * Customers/Sales in 7J, which each got their own file for size reasons).
 */
export const passportHandlers = [
  http.get(`${BASE}/api/v1/plants/:plant_id/passports`, () => HttpResponse.json([makePassport()])),
  http.post(`${BASE}/api/v1/plants/:plant_id/passports`, () => HttpResponse.json(makePassport({ version: 2 }))),

  http.get(`${BASE}/api/v1/public/passport/:token`, () => HttpResponse.json(makePublicPassport())),
  http.get(`${BASE}/api/v1/public/qr/:token`, () => HttpResponse.json(makeQrScanResponse())),
];
