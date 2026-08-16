"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import * as assistantApi from "@/lib/api/ai-assistant";
import { assistantKeys } from "@/lib/ai-assistant/queries";
import { useAssistantStore } from "@/store/assistant-store";
import { toast } from "@/lib/toast";

/**
 * FR-9.1/9.2 -- sends a message; if `conversationId` was `null` (no
 * conversation yet), the response's real `conversation_id` is written to
 * `useAssistantStore` on success so the *next* message in this session
 * continues the same conversation instead of silently starting a new one
 * every time -- this is the one place client state is derived from a
 * real server response, never invented ahead of it.
 */
export function useSendAssistantMessageMutation() {
  const queryClient = useQueryClient();
  const setConversationId = useAssistantStore((state) => state.setConversationId);

  return useMutation({
    mutationFn: (params: { conversationId: string | null; content: string }) =>
      assistantApi.sendAssistantMessage({ conversation_id: params.conversationId ?? undefined, content: params.content }),
    onSuccess: (message) => {
      setConversationId(message.conversation_id);
      void queryClient.invalidateQueries({ queryKey: assistantKeys.conversation(message.conversation_id) });
    },
    onError: (error) => toast.apiError(error),
  });
}

/** FR-9.3 -- `confirm: true` executes the proposed action for real through its native service path; `confirm: false` discards it. */
export function useConfirmAssistantActionMutation(conversationId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params: { messageId: string; confirm: boolean }) =>
      assistantApi.confirmAssistantAction(params.messageId, { conversation_id: conversationId, confirm: params.confirm }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: assistantKeys.conversation(conversationId) });
    },
    onError: (error) => toast.apiError(error),
  });
}
