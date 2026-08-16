import { http, HttpResponse } from "msw";

import {
  makeCustomer,
  makeCustomerAddress,
  makeCustomerAnalytics,
  makeCustomerCommunication,
  makeCustomerCommunicationPage,
  makeCustomerContact,
  makeCustomerNote,
  makeCustomerNotePage,
  makeCustomerPage,
  makeCustomerReportRow,
  makeCustomerTag,
} from "@/test/fixtures/customers";
import { makeSalePage } from "@/test/fixtures/sales";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7J's Module 9 Customer/CRM routes.
 * Listed before `shellHandlers` in test/msw/server.ts for the same
 * handler-shadowing reason `plantsHandlers`/`inventoryHandlers` are --
 * `shellHandlers` registers its own empty `/customers` stub for 7C's
 * global-search fan-out. `GET /customers/report` is registered ahead of
 * `GET /customers/:id` here too, mirroring the real backend's static-
 * route-before-parameterized-route ordering (`customers.py`'s docstring).
 */
export const customersHandlers = [
  http.get(`${BASE}/api/v1/customers/report`, () => HttpResponse.json([makeCustomerReportRow()])),

  http.get(`${BASE}/api/v1/customers`, () => HttpResponse.json(makeCustomerPage())),
  http.post(`${BASE}/api/v1/customers`, () => HttpResponse.json(makeCustomer())),
  http.get(`${BASE}/api/v1/customers/:id`, () => HttpResponse.json(makeCustomer())),
  http.patch(`${BASE}/api/v1/customers/:id`, () => HttpResponse.json(makeCustomer())),

  http.get(`${BASE}/api/v1/customers/:id/purchase-history`, () => HttpResponse.json(makeSalePage())),
  http.get(`${BASE}/api/v1/customers/:id/analytics`, () => HttpResponse.json(makeCustomerAnalytics())),

  http.get(`${BASE}/api/v1/customers/:id/contacts`, () => HttpResponse.json([makeCustomerContact()])),
  http.post(`${BASE}/api/v1/customers/:id/contacts`, () => HttpResponse.json(makeCustomerContact())),

  http.get(`${BASE}/api/v1/customers/:id/addresses`, () => HttpResponse.json([makeCustomerAddress()])),
  http.post(`${BASE}/api/v1/customers/:id/addresses`, () => HttpResponse.json(makeCustomerAddress())),

  http.get(`${BASE}/api/v1/customers/:id/tags`, () => HttpResponse.json([makeCustomerTag()])),
  http.post(`${BASE}/api/v1/customers/:id/tags`, () => HttpResponse.json(makeCustomerTag())),
  http.delete(`${BASE}/api/v1/customers/:id/tags/:tag`, () => new HttpResponse(null, { status: 204 })),

  http.get(`${BASE}/api/v1/customers/:id/notes`, () => HttpResponse.json(makeCustomerNotePage())),
  http.post(`${BASE}/api/v1/customers/:id/notes`, () => HttpResponse.json(makeCustomerNote())),

  http.get(`${BASE}/api/v1/customers/:id/communications`, () => HttpResponse.json(makeCustomerCommunicationPage())),
  http.post(`${BASE}/api/v1/customers/:id/communications`, () => HttpResponse.json(makeCustomerCommunication())),
];
