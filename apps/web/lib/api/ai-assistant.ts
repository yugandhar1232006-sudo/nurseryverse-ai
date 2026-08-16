import { apiClient, unwrap } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

/**
 * Thin typed wrappers for Module 10's AI Assistant surface
 * (`ai_assistant.py`) -- send a message (starts or continues a
 * conversation), confirm/cancel a proposed write action, and read one
 * conversation's full message history.
 *
 * There is no `GET /ai/assistant/conversations` list route -- a caller
 * can only ever fetch a conversation it already knows the id of (via
 * `get_assistant_conversation`'s own docstring: ownership is enforced as
 * a `NotFoundError`, not a 403, for someone-else's conversation). This is
 * why `store/assistant-store.ts` persists the current `conversationId`
 * client-side: it is the *only* way this frontend can reopen "my last
 * conversation" after a page reload, since the backend has nothing to
 * list from. If that id ever 404s (conversation deleted, or genuinely
 * belongs to a different account that happens to share this browser),
 * the panel starts a fresh conversation rather than erroring -- see
 * `components/assistant/assistant-panel.tsx`.
 */

export type AssistantMessageResponse = components["schemas"]["AssistantMessageResponse"];
export type AssistantConversationResponse = components["schemas"]["AssistantConversationResponse"];
export type AssistantConversationDetailResponse = components["schemas"]["AssistantConversationDetailResponse"];
export type SendAssistantMessageRequest = components["schemas"]["SendAssistantMessageRequest"];
export type ConfirmAssistantActionRequest = components["schemas"]["ConfirmAssistantActionRequest"];

/**
 * `AssistantMessageResponse.proposed_action` is `dict[str, Any] | null`
 * on the backend (no sub-schema) -- this hand-written interface mirrors
 * the real, exact shape `AssistantConversationService.send_message`
 * always constructs it with (`{tool_name, tool_arguments, summary}`, read
 * directly from that service's source, not guessed), cast via
 * `message.proposed_action as unknown as ProposedAction | null` in
 * `components/assistant/assistant-panel.tsx`. `action_status` is
 * likewise a free-text backend column (`String(30)`, not a DB enum) but
 * only ever set to one of these three literal values by that same
 * service, per its own inline comment.
 */
export interface ProposedAction {
  tool_name: string;
  tool_arguments: Record<string, unknown>;
  summary: string;
}
export type AssistantActionStatus = "pending_confirmation" | "confirmed" | "cancelled";

/** FR-9.1/9.2 -- omit `conversation_id` to start a new conversation; provide one you own to continue it. */
export async function sendAssistantMessage(body: SendAssistantMessageRequest): Promise<AssistantMessageResponse> {
  return unwrap(() => apiClient.POST("/api/v1/ai/assistant/message", { body }));
}

/** FR-9.3 -- `confirm: true` executes the proposed action through its normal service-layer validation; `confirm: false` discards it with no side effect. */
export async function confirmAssistantAction(
  messageId: string,
  body: ConfirmAssistantActionRequest,
): Promise<AssistantMessageResponse> {
  return unwrap(() =>
    apiClient.POST("/api/v1/ai/assistant/actions/{message_id}/confirm", { params: { path: { message_id: messageId } }, body }),
  );
}

/** FR-9.4 -- a conversation's metadata plus its paginated message history, newest-page-first per the real route's PageParams. */
export async function getAssistantConversation(
  conversationId: string,
  params: { page?: number; page_size?: number } = {},
): Promise<AssistantConversationDetailResponse> {
  return unwrap(() =>
    apiClient.GET("/api/v1/ai/assistant/conversations/{conversation_id}", {
      params: { path: { conversation_id: conversationId }, query: params },
    }),
  );
}
