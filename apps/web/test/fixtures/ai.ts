import type {
  AIPredictionResponse,
  AIRecommendationResponse,
  PageAIPredictionResponse,
  PageAIRecommendationResponse,
  RevenueForecastResult,
  SurvivalPredictionResult,
} from "@/lib/api/ai-predictions";
import type {
  AssistantConversationDetailResponse,
  AssistantConversationResponse,
  AssistantMessageResponse,
  ProposedAction,
} from "@/lib/api/ai-assistant";

/** Shared fixtures for 7L AI Experience tests -- mirrors test/fixtures/passport.ts's pattern. */

export function makeSurvivalResult(overrides: Partial<SurvivalPredictionResult> = {}): SurvivalPredictionResult {
  return {
    risk_score: 62,
    risk_level: "high",
    factors: {
      latest_health_status: "stressed",
      health_risk_contribution: 55,
      disease_risk_contribution: 0,
      environmental_variance_risk_contribution: 5,
      watering_risk_contribution: 0,
      days_since_last_watering: 3,
      disease_report_count: 0,
    },
    data_points_used: 12,
    ...overrides,
  };
}

export function makeRevenueForecastResult(overrides: Partial<RevenueForecastResult> = {}): RevenueForecastResult {
  return {
    method: "seasonal_naive",
    data_points_used: 30,
    overall_mean_daily_revenue: 450.25,
    overall_stdev_daily_revenue: 60.1,
    forecast: [
      { date: "2026-08-16", projected_revenue: 452.0, lower_bound: 334.24, upper_bound: 569.76 },
      { date: "2026-08-17", projected_revenue: 470.5, lower_bound: 352.74, upper_bound: 588.26 },
    ],
    ...overrides,
  };
}

export function makePrediction(overrides: Partial<AIPredictionResponse> = {}): AIPredictionResponse {
  return {
    id: "prediction-01",
    nursery_id: "org-01",
    branch_id: "branch-01",
    plant_id: "cccccccc-cccc-cccc-cccc-cccccccccc01",
    prediction_type: "survival_prediction",
    model_version: "v1.0.0-weighted-risk-baseline",
    result: makeSurvivalResult() as unknown as Record<string, never>,
    confidence: "0.55",
    explanation: "Survival risk 62/100 (high). Latest health status: stressed.",
    inputs_summary: null,
    created_at: "2026-08-14T00:00:00Z",
    ...overrides,
  };
}

export function makePredictionPage(overrides: Partial<PageAIPredictionResponse> = {}): PageAIPredictionResponse {
  return {
    items: [makePrediction()],
    meta: { page: 1, page_size: 20, total_items: 1, total_pages: 1 },
    ...overrides,
  };
}

export function makeRecommendation(overrides: Partial<AIRecommendationResponse> = {}): AIRecommendationResponse {
  return {
    id: "rec-01",
    nursery_id: "org-01",
    branch_id: "branch-01",
    source_prediction_id: "prediction-01",
    priority: "high",
    summary: "Bench 3 - Fig #1 is at high survival risk -- check watering schedule.",
    explanation: "Survival risk 62/100 driven primarily by recent health status.",
    deep_link: "/plants/cccccccc-cccc-cccc-cccc-cccccccccc01",
    status: "new",
    model_version: "v1.0.0-weighted-risk-baseline",
    created_at: "2026-08-14T00:00:00Z",
    ...overrides,
  };
}

export function makeRecommendationPage(overrides: Partial<PageAIRecommendationResponse> = {}): PageAIRecommendationResponse {
  return {
    items: [makeRecommendation()],
    meta: { page: 1, page_size: 20, total_items: 1, total_pages: 1 },
    ...overrides,
  };
}

export function makeProposedAction(overrides: Partial<ProposedAction> = {}): ProposedAction {
  return {
    tool_name: "record_watering",
    tool_arguments: { plant_id: "cccccccc-cccc-cccc-cccc-cccccccccc01", volume_ml: 500 },
    summary: "Log a 500ml watering event for Bench 3 - Fig #1.",
    ...overrides,
  };
}

export function makeAssistantMessage(overrides: Partial<AssistantMessageResponse> = {}): AssistantMessageResponse {
  return {
    id: "message-01",
    conversation_id: "conversation-01",
    role: "assistant",
    content: "I can help with that -- want me to log a watering event?",
    proposed_action: null,
    action_status: null,
    model_name: "claude-assistant-baseline",
    input_tokens: 120,
    output_tokens: 40,
    cost_usd: "0.0012",
    created_at: "2026-08-14T00:00:00Z",
    ...overrides,
  };
}

export function makeAssistantConversation(overrides: Partial<AssistantConversationResponse> = {}): AssistantConversationResponse {
  return {
    id: "conversation-01",
    nursery_id: "org-01",
    user_id: "11111111-1111-1111-1111-111111111111",
    title: null,
    created_at: "2026-08-14T00:00:00Z",
    updated_at: "2026-08-14T00:00:00Z",
    ...overrides,
  };
}

export function makeAssistantConversationDetail(
  overrides: Partial<AssistantConversationDetailResponse> = {},
): AssistantConversationDetailResponse {
  return {
    conversation: makeAssistantConversation(),
    messages: [
      makeAssistantMessage({ id: "message-user-01", role: "user", content: "Does bench 3 fig need water?" }),
      makeAssistantMessage(),
    ],
    total_messages: 2,
    ...overrides,
  };
}
