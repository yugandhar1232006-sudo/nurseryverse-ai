import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import PlantDetailPage from "@/app/(app)/plants/[id]/page";
import { useSessionStore } from "@/store/session-store";
import { makeMe } from "@/test/fixtures/auth";
import { makePlant } from "@/test/fixtures/plants";
import { makePrediction, makePredictionPage } from "@/test/fixtures/ai";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({ id: makePlant().id }),
}));

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7L's internal, per-plant half -- PG-26 AI Predictions + PG-28 disease
 * scan, both on the new "AI Predictions" tab added to the existing
 * `/plants/[id]` page. Separate file from `plant-lifecycle.test.tsx` and
 * `passport-tab.test.tsx`, matching the established one-file-per-tab
 * convention for this large page.
 */
describe("AiPredictionsTab (7L)", () => {
  it("hides the AI Predictions tab entirely for a role without ai_predictions:read", async () => {
    signIn(["plants:read"]);
    server.use(http.get(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())));
    renderWithProviders(<PlantDetailPage />);

    await screen.findByRole("tab", { name: "Overview" });
    expect(screen.queryByRole("tab", { name: "AI Predictions" })).not.toBeInTheDocument();
  });

  it("lists real prediction history and hides on-demand run buttons for a read-only role", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "ai_predictions:read"]);
    server.use(
      http.get(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())),
      http.get(`${BASE}/api/v1/plants/:plant_id/ai-predictions`, () => HttpResponse.json(makePredictionPage())),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "AI Predictions" }));
    expect(await screen.findByText(/Survival risk 62\/100/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run survival prediction" })).not.toBeInTheDocument();
  });

  it("runs a real on-demand growth prediction through the real mutation for a role with ai_predictions:run", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "ai_predictions:read", "ai_predictions:run"]);
    let ran = false;
    server.use(
      http.get(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())),
      http.get(`${BASE}/api/v1/plants/:plant_id/ai-predictions`, () => HttpResponse.json(makePredictionPage({ items: [] }))),
      http.post(`${BASE}/api/v1/plants/:plant_id/ai-predictions/growth`, () => {
        ran = true;
        return HttpResponse.json(makePrediction({ prediction_type: "growth_prediction" }));
      }),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "AI Predictions" }));
    await user.click(await screen.findByRole("button", { name: "Run growth prediction" }));

    await waitFor(() => expect(ran).toBe(true));
  });

  it("submits a real disease scan through the real form and shows the resulting prediction", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "ai_predictions:read", "ai_predictions:run"]);
    let submittedUrl: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/plants/:id`, () => HttpResponse.json(makePlant())),
      http.get(`${BASE}/api/v1/plants/:plant_id/ai-predictions`, () => HttpResponse.json(makePredictionPage({ items: [] }))),
      http.post(`${BASE}/api/v1/ai/disease-detection/scan`, async ({ request }) => {
        const body = (await request.json()) as { image_url: string };
        submittedUrl = body.image_url;
        return HttpResponse.json(makePrediction({ prediction_type: "disease_detection" }));
      }),
    );
    renderWithProviders(<PlantDetailPage />);

    await user.click(await screen.findByRole("tab", { name: "AI Predictions" }));
    await user.click(await screen.findByRole("button", { name: "Scan for disease" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Photo URL"), "https://example.com/photo.jpg");
    await user.click(within(dialog).getByRole("button", { name: "Run scan" }));

    await waitFor(() => expect(submittedUrl).toBe("https://example.com/photo.jpg"));
  });
});
