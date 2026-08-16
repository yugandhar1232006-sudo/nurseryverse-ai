"use client";

import { useQuery } from "@tanstack/react-query";

import * as assistantApi from "@/lib/api/ai-assistant";

/** Query key factory for 7L's AI Assistant reads. */
export const assistantKeys = {
  all: ["ai-assistant"] as const,
  conversation: (conversationId: string) => [...assistantKeys.all, "conversation", conversationId] as const,
};

/**
 * FR-9.4 -- the current conversation's metadata + message history. Never
 * `enabled` for a `null` id, since there is no "get me any conversation"
 * fallback server-side (see lib/api/ai-assistant.ts's docstring) --
 * `AssistantPanel` starts a fresh conversation via the send-message
 * mutation instead of ever calling this with a guessed id.
 */
export function useAssistantConversationQuery(conversationId: string | null) {
  return useQuery({
    queryKey: assistantKeys.conversation(conversationId ?? "none"),
    queryFn: () => assistantApi.getAssistantConversation(conversationId as string, { page_size: 100 }),
    enabled: conversationId !== null,
    retry: false, // a 404 here means "not owned / no longer exists" -- retrying the same bad id serves no purpose (see AssistantPanel's onError handling).
  });
}
