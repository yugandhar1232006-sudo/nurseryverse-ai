import { http, HttpResponse } from "msw";

import {
  makeAssistantConversationDetail,
  makeAssistantMessage,
  makePrediction,
  makePredictionPage,
  makeRecommendation,
  makeRecommendationPage,
  makeRevenueForecastResult,
} from "@/test/fixtures/ai";

const BASE = "http://localhost:8000";

/**
 * Default, happy-path handlers for 7L's Module 10 AI Predictions + AI
 * Assistant routes. One combined file, matching 7K's `passport-handlers.ts`
 * precedent (a single small module, not split like 7J's Customers/Sales).
 */
export const aiHandlers = [
  http.get(`${BASE}/api/v1/plants/:plant_id/ai-predictions`, () => HttpResponse.json(makePredictionPage())),
  http.post(`${BASE}/api/v1/ai/disease-detection/scan`, () => HttpResponse.json(makePrediction({ prediction_type: "disease_detection" }))),
  http.post(`${BASE}/api/v1/plants/:plant_id/ai-predictions/growth`, () =>
    HttpResponse.json(makePrediction({ prediction_type: "growth_prediction" })),
  ),
  http.post(`${BASE}/api/v1/plants/:plant_id/ai-predictions/survival`, () =>
    HttpResponse.json(makePrediction({ prediction_type: "survival_prediction" })),
  ),
  http.post(`${BASE}/api/v1/plants/:plant_id/ai-predictions/water`, () =>
    HttpResponse.json(makePrediction({ prediction_type: "water_recommendation" })),
  ),

  http.get(`${BASE}/api/v1/ai/predictions/survival-risk`, () => HttpResponse.json(makePredictionPage())),
  // `result` is explicitly the real `RevenueForecastResult` shape here --
  // `makePrediction()`'s own default `result` is survival-shaped (that's
  // its most common caller), which would silently mismatch
  // `RevenueForecastPanel`'s `method === "seasonal_naive"` branch check
  // if left as the default for a revenue_forecast-typed fixture.
  http.post(`${BASE}/api/v1/ai/predictions/revenue-forecast`, () =>
    HttpResponse.json(
      makePrediction({
        prediction_type: "revenue_forecast",
        plant_id: null,
        result: makeRevenueForecastResult() as unknown as Record<string, never>,
      }),
    ),
  ),
  http.get(`${BASE}/api/v1/ai/predictions/revenue-forecast`, () =>
    HttpResponse.json(
      makePredictionPage({
        items: [
          makePrediction({
            prediction_type: "revenue_forecast",
            plant_id: null,
            result: makeRevenueForecastResult() as unknown as Record<string, never>,
          }),
        ],
      }),
    ),
  ),

  http.get(`${BASE}/api/v1/ai/recommendations`, () => HttpResponse.json(makeRecommendationPage())),
  http.post(`${BASE}/api/v1/ai/recommendations/refresh`, () => HttpResponse.json([makeRecommendation()])),

  http.post(`${BASE}/api/v1/ai/assistant/message`, () => HttpResponse.json(makeAssistantMessage())),
  http.post(`${BASE}/api/v1/ai/assistant/actions/:message_id/confirm`, () =>
    HttpResponse.json(makeAssistantMessage({ action_status: "confirmed" })),
  ),
  http.get(`${BASE}/api/v1/ai/assistant/conversations/:conversation_id`, () => HttpResponse.json(makeAssistantConversationDetail())),
];
