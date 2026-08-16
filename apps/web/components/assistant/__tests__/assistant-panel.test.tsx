import { beforeEach, describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { useSessionStore } from "@/store/session-store";
import { useAssistantStore } from "@/store/assistant-store";
import { useUiStore } from "@/store/ui-store";
import { makeMe } from "@/test/fixtures/auth";
import { makeAssistantConversationDetail, makeAssistantMessage, makeProposedAction } from "@/test/fixtures/ai";
import { renderWithProviders } from "@/test/utils";
import { server } from "@/test/msw/server";

const BASE = "http://localhost:8000";

function signIn(permissions: string[]) {
  useSessionStore.setState({ status: "authenticated", user: makeMe({ permissions }), accessToken: "access-token-1" });
}

/**
 * 7L's AI Assistant header overlay -- FR-9.1-9.4. Resets both
 * `useAssistantStore` (the persisted `conversationId`) and `useUiStore`'s
 * `assistantPanelOpen` before each test, since both are real
 * `zustand/middleware`'s `persist`-backed stores that would otherwise
 * leak state across tests in this same file (a real risk unique to this
 * component -- no other 7L/7K test file uses a custom persisted store).
 */
describe("AssistantPanel (7L)", () => {
  beforeEach(() => {
    useAssistantStore.setState({ conversationId: null });
    useUiStore.setState({ assistantPanelOpen: false });
  });

  it("shows the real empty state before any conversation exists, and starts a real conversation on first send", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "ai_assistant:use"]);
    let sentContent: string | null = null;
    server.use(
      http.post(`${BASE}/api/v1/ai/assistant/message`, async ({ request }) => {
        const body = (await request.json()) as { content: string; conversation_id?: string };
        sentContent = body.content;
        return HttpResponse.json(makeAssistantMessage());
      }),
      http.get(`${BASE}/api/v1/ai/assistant/conversations/:conversation_id`, () => HttpResponse.json(makeAssistantConversationDetail())),
    );
    renderWithProviders(<AssistantPanel />);

    await user.click(screen.getByRole("button", { name: "AI Assistant" }));
    expect(await screen.findByText("Ask me anything about your nursery")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Type a message…"), "Does bench 3 fig need water?");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(sentContent).toBe("Does bench 3 fig need water?"));
    expect(await screen.findByText("I can help with that -- want me to log a watering event?")).toBeInTheDocument();
    expect(useAssistantStore.getState().conversationId).toBe("conversation-01");
  });

  it("shows a real proposed-action confirm card and confirms it through the real mutation", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "ai_assistant:use", "ai_assistant:confirm_write"]);
    useAssistantStore.setState({ conversationId: "conversation-01" });
    let confirmed: { confirm: boolean; conversation_id: string } | null = null;
    server.use(
      http.get(`${BASE}/api/v1/ai/assistant/conversations/:conversation_id`, () =>
        HttpResponse.json(
          makeAssistantConversationDetail({
            messages: [
              makeAssistantMessage({
                proposed_action: makeProposedAction() as unknown as Record<string, never>,
                action_status: "pending_confirmation",
              }),
            ],
          }),
        ),
      ),
      http.post(`${BASE}/api/v1/ai/assistant/actions/:message_id/confirm`, async ({ request }) => {
        confirmed = (await request.json()) as { confirm: boolean; conversation_id: string };
        return HttpResponse.json(makeAssistantMessage({ action_status: "confirmed" }));
      }),
    );
    renderWithProviders(<AssistantPanel />);

    await user.click(screen.getByRole("button", { name: "AI Assistant" }));
    expect(await screen.findByText("Log a 500ml watering event for Bench 3 - Fig #1.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Confirm" }));

    await waitFor(() => expect(confirmed).toEqual({ confirm: true, conversation_id: "conversation-01" }));
  });

  it("hides the Confirm/Cancel controls for a role without ai_assistant:confirm_write", async () => {
    const user = userEvent.setup();
    signIn(["plants:read", "ai_assistant:use"]);
    useAssistantStore.setState({ conversationId: "conversation-01" });
    server.use(
      http.get(`${BASE}/api/v1/ai/assistant/conversations/:conversation_id`, () =>
        HttpResponse.json(
          makeAssistantConversationDetail({
            messages: [
              makeAssistantMessage({
                proposed_action: makeProposedAction() as unknown as Record<string, never>,
                action_status: "pending_confirmation",
              }),
            ],
          }),
        ),
      ),
    );
    renderWithProviders(<AssistantPanel />);

    await user.click(screen.getByRole("button", { name: "AI Assistant" }));
    expect(await screen.findByText("Log a 500ml watering event for Bench 3 - Fig #1.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
    expect(screen.getByText("You don't have permission to confirm this action.")).toBeInTheDocument();
  });

  it("clears a stale conversation id and falls back to the empty state on a real 404, rather than showing a raw error", async () => {
    signIn(["plants:read", "ai_assistant:use"]);
    useAssistantStore.setState({ conversationId: "stale-conversation" });
    server.use(
      http.get(`${BASE}/api/v1/ai/assistant/conversations/:conversation_id`, () =>
        HttpResponse.json({ error: { code: "not_found", message: "Conversation not found." } }, { status: 404 }),
      ),
    );
    renderWithProviders(<AssistantPanel />);

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "AI Assistant" }));

    await waitFor(() => expect(useAssistantStore.getState().conversationId).toBeNull());
    expect(await screen.findByText("Ask me anything about your nursery")).toBeInTheDocument();
  });
});
