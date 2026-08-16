import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import AiCenterPage from "@/app/(app)/ai-center/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makePrediction, makePredictionPage, makeRecommendation, makeRecommendationPage, makeRevenueForecastResult } from "@/test/fixtures/ai";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7L's org-wide half -- `/ai-center`, the real implementation replacing
 * 7C's `ComingSoon` placeholder. Covers all three tabs (Survival Risk,
 * Revenue Forecast, Recommendations) plus the real permission-denied
 * fallback and the branch-scope requirement on the Refresh action.
 */
describe("AiCenterPage (7L)", () => {
  it("shows the real permission-denied fallback for a role without ai_predictions:read", async () => {
    signIn(["plants:read"]);
    renderWithProviders(<AiCenterPage />);

    expect(await screen.findByText(/permission/i)).toBeInTheDocument();
  });

  it("lists real ranked survival-risk predictions on the default tab", async () => {
    signIn(["plants:read", "ai_predictions:read"]);
    server.use(http.get(`${BASE}/api/v1/ai/predictions/survival-risk`, () => HttpResponse.json(makePredictionPage())));
    renderWithProviders(<AiCenterPage />);

    expect(await screen.findByText("high")).toBeInTheDocument();
    expect(screen.getByText("62/100")).toBeInTheDocument();
  });

  it("runs a real revenue forecast and renders the resulting chart data for a role with ai_predictions:run", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "ai_predictions:read", "ai_predictions:run"]);

    // Stateful handler: the GET list reflects whatever the POST run has
    // (or hasn't) produced so far -- a real forecast only becomes visible
    // in the list *after* a real POST created one, matching how the
    // actual backend's `ai_predictions` table behaves (nothing shows up
    // in history until something is actually persisted).
    let forecastRan = false;
    server.use(
      http.get(`${BASE}/api/v1/ai/predictions/revenue-forecast`, () =>
        HttpResponse.json(
          makePredictionPage({
            items: forecastRan
              ? [makePrediction({ prediction_type: "revenue_forecast", plant_id: null, result: makeRevenueForecastResult() as unknown as Record<string, never> })]
              : [],
          }),
        ),
      ),
      http.post(`${BASE}/api/v1/ai/predictions/revenue-forecast`, () => {
        forecastRan = true;
        return HttpResponse.json(
          makePrediction({ prediction_type: "revenue_forecast", plant_id: null, result: makeRevenueForecastResult() as unknown as Record<string, never> }),
        );
      }),
    );
    renderWithProviders(<AiCenterPage />);

    await user.click(await screen.findByRole("tab", { name: "Revenue Forecast" }));
    expect(await screen.findByText("No revenue forecast yet")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Run forecast" }));
    expect(await screen.findByText("14-day forecast")).toBeInTheDocument();
  });

  it("disables Refresh recommendations until a specific branch is selected, then runs the real mutation", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "ai_predictions:read", "ai_predictions:run"]);
    let refreshedBranchId: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/ai/recommendations`, () => HttpResponse.json(makeRecommendationPage())),
      http.post(`${BASE}/api/v1/ai/recommendations/refresh`, ({ request }) => {
        refreshedBranchId = new URL(request.url).searchParams.get("branch_id");
        return HttpResponse.json([makeRecommendation()]);
      }),
    );
    renderWithProviders(<AiCenterPage />);

    await user.click(await screen.findByRole("tab", { name: "Recommendations" }));
    expect(await screen.findByRole("button", { name: "Refresh recommendations" })).toBeDisabled();

    await user.click(screen.getByRole("combobox", { name: "Dashboard scope" }));
    await user.click(await screen.findByRole("option", { name: "Main Branch" }));

    const refreshButton = await screen.findByRole("button", { name: "Refresh recommendations" });
    expect(refreshButton).toBeEnabled();
    await user.click(refreshButton);

    await waitFor(() => expect(refreshedBranchId).toBe("44444444-4444-4444-4444-444444444444"));
  });
});
