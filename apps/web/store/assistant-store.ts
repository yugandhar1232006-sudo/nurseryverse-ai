import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Holds only the id of the AI Assistant conversation currently "open" in
 * this browser -- nothing else, and never message content itself (that
 * always comes fresh from `GET /ai/assistant/conversations/{id}` via
 * `lib/ai-assistant/queries.ts`, the same "TanStack Query owns server
 * data, Zustand owns client-only state" split every other store in this
 * app follows).
 *
 * This exists because Module 10's real API has no "list my conversations"
 * route (see lib/api/ai-assistant.ts's docstring) -- an id persisted here
 * is the *only* way this frontend can reopen the same conversation after
 * a page reload. It is not sensitive (just an id, not message content or
 * a credential), so persisting it to localStorage follows the same
 * precedent as store/branch-context-store.ts's `selectedBranchId`.
 *
 * If the persisted id ever turns out to belong to a different account
 * (browser shared across users) or a since-deleted conversation, the real
 * `GET .../conversations/{id}` call 404s -- `AssistantPanel` treats that
 * exactly like "no conversation yet" and clears this store, rather than
 * surfacing a confusing error for state the user never directly caused.
 */
interface AssistantState {
  conversationId: string | null;
}

interface AssistantActions {
  setConversationId: (conversationId: string | null) => void;
}

export const useAssistantStore = create<AssistantState & AssistantActions>()(
  persist(
    (set) => ({
      conversationId: null,
      setConversationId: (conversationId) => set({ conversationId }),
    }),
    { name: "nurseryverse-assistant" },
  ),
);
