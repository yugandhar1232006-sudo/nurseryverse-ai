# 7M -- AI Assistant

## Route Structure

No dedicated route. The AI Assistant is a persistent `Sheet` overlay in the application header,
triggered by the Sparkles icon in `TopNav`. The panel opens from the right side and overlays the
current page content without navigating away.

```
components/assistant/
  assistant-panel.tsx                Sheet overlay. Owns conversation lifecycle: empty state,
                                     message list, input field, Thinking... indicator.
  message-bubble.tsx                 Individual message: user or assistant. Assistant messages
                                     can contain proposed action cards.
  proposed-action-card.tsx           Confirm / Cancel UI for write-tool proposals. Shows action
                                     type, parameters, and a brief description. Confirm calls
                                     the confirm endpoint. Cancel dismisses the card.

lib/assistant/queries.ts             assistantKeys factory + useAssistantConversationQuery
lib/assistant/mutations.ts           useSendAssistantMessageMutation,
                                     useConfirmAssistantActionMutation
lib/assistant/store.ts               useAssistantStore (Zustand, persisted to localStorage)
```

## Components

- **AssistantPanel** -- the Sheet overlay. Renders the message list, input field, and send button.
  On first open with no conversation, shows an empty state with example prompts. Handles the
  conversation lifecycle: null conversationId -> first message creates a conversation -> subsequent
  messages continue it.
- **MessageBubble** -- renders a single message. User messages are right-aligned. Assistant messages
  are left-aligned and may contain one or more `ProposedActionCard` components if the assistant's
  response included tool calls that produced proposals.
- **ProposedActionCard** -- a card within an assistant message. Shows the proposed action type
  (e.g., "Log Watering", "Record Health Observation"), the parameters the assistant extracted, and
  Confirm / Cancel buttons. Confirm calls `POST /ai/assistant/actions/{id}/confirm`. Cancel
  dismisses the card in the UI (no server call needed -- it's a client-side dismiss).

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | /ai/assistant/message | Send a user message. Returns assistant response (may include proposed actions). |
| POST | /ai/assistant/actions/{id}/confirm | Confirm a proposed write action. Executes the tool on the backend. |
| GET | /ai/assistant/conversations/{id} | Fetch conversation history (message list). |

No conversation list endpoint exists by design. The assistant does not expose a history browser --
each user has at most one active conversation at a time, identified by the `conversationId` in
the Zustand store.

## Query Keys & Mutations

Query key factory (`assistantKeys`):

- `assistantKeys.conversation(id)` -- conversation message history. Uses `retry: false` -- a 404
  response (stale conversationId from a previous session) is handled by clearing the stored
  conversationId and resetting to the empty state, not by retrying.

Mutations:

- **useSendAssistantMessageMutation** -- `POST /ai/assistant/message`. On first send (when
  `conversationId` is null), the response includes the new `conversationId`, which is saved to the
  Zustand store. Subsequent sends include the `conversationId` in the request body. Invalidates
  `assistantKeys.conversation(id)` on success.
- **useConfirmAssistantActionMutation** -- `POST /ai/assistant/actions/{id}/confirm`. No query
  invalidation needed -- the confirmed action result is appended to the conversation via the
  next message exchange.

## Client State

Two Zustand stores:

- **useAssistantStore** (persisted to localStorage):
  - `conversationId: string | null` -- the active conversation. Persisted so refreshing the page
    resumes the same conversation.
  - Seeded from the REST conversation endpoint on panel open, then kept in sync by message
    exchanges.
  - Not org-level: this store is per-user, not per-organization. Switching orgs does not reset
    the conversation.

- **useUiStore** (not persisted):
  - `isAssistantOpen: boolean` -- whether the Sheet panel is open. Shared between the Sparkles
    button in TopNav and the panel itself, matching the same shared-UI-state pattern used by
    NotificationCenter in 7K.

## Validation

`sendAssistantMessageSchema` (Zod):

- `message`: string, 1-4000 characters. No HTML stripping or sanitization at the schema level --
  the backend handles sanitization before sending to the LLM provider.

## Permission Gates

Two permissions, layered:

- **`ai_assistant:use`** -- required to send messages, read responses, and cancel proposed actions.
  This is the base permission for all assistant interaction. The Sparkles icon in TopNav is gated
  on this permission.
- **`ai_assistant:confirm_write`** -- required to confirm a proposed write action. This is a
  stricter permission than `ai_assistant:use`. Cancel only needs `ai_assistant:use`. The confirm
  button inside `ProposedActionCard` is individually gated on `ai_assistant:confirm_write`.

Tool-level permissions are checked per action on the backend, not in the frontend. The frontend
does not know which tools a user has permission to confirm -- it sends the confirm request and
handles a 403 response if the user lacks the tool-specific permission.

## Conversation Lifecycle

```
null conversationId
    |
    v
User sends first message -> POST /ai/assistant/message (no conversationId)
    |
    v
Response includes conversationId -> saved to localStorage
    |
    v
Subsequent messages -> POST /ai/assistant/message (with conversationId)
    |
    v
Assistant response includes proposed actions -> ProposedActionCard renders
    |
    v
User clicks Confirm -> POST /ai/assistant/actions/{id}/confirm
    |
    v
Action result appended to conversation -> continue chatting
    |
    v
[Page refresh] -> conversationId loaded from localStorage
    |
    v
Panel opens -> GET /ai/assistant/conversations/{id}
    |
    v
If 404 (stale ID) -> clear conversationId, reset to empty state
```

## Tool Registry

The assistant has 6 registered tools, split into two categories:

### Read Tools (execute immediately)

4 tools that fetch data and return it directly to the assistant for inclusion in its response:

- `get_plant_summary` -- plant health and status overview
- `get_inventory_status` -- current inventory levels
- `get_sales_summary` -- sales performance data
- `get_ai_predictions` -- recent AI prediction results

Read tools execute on the backend when the assistant invokes them. The results are returned to the
LLM, which incorporates them into its natural language response. No human confirmation is needed.

### Write Tools (produce proposals, never auto-execute)

2 tools that propose data modifications requiring human confirmation:

- `propose_watering_log` -- proposes creating a watering log entry
- `propose_health_observation` -- proposes recording a plant health observation

Write tools **never execute automatically**. When the assistant invokes a write tool, the backend
returns a proposal object (action ID, type, parameters) instead of executing the action. The
proposal is rendered as a `ProposedActionCard` in the UI. The user must explicitly click Confirm
to execute it. This is the core safety mechanism: the assistant can suggest actions but cannot
take them without human approval.

## Patterns

- **Per-user ownership**: conversations belong to individual users, not organizations. Switching
  orgs does not create a new conversation or reset the existing one.
- **Domain events at every step**: message sent, message received, action proposed, action confirmed,
  action cancelled, conversation recovered from stale ID. All events are emitted for observability.
- **Max 50 history messages to LLM**: the conversation history sent to the LLM is capped at 50
  messages (most recent first). Older messages are dropped from the LLM context but remain in the
  conversation record. This prevents context window overflow while keeping recent context intact.
- **Cost tracking**: each message exchange logs token usage and estimated cost. Displayed in the
  conversation for transparency.
- **Single provider**: Anthropic Claude only. No multi-provider abstraction. The backend is
  hardcoded to call the Anthropic API.
- **Non-streaming with Thinking... indicator**: responses arrive as a complete block, not streamed
  token-by-token. A "Thinking..." animated indicator shows while the backend waits for the LLM
  response. No SSE or streaming infrastructure.

## Known Limitations

- **No conversation list**: there is no UI to browse past conversations. Each user has one active
  conversation at a time. The conversation list endpoint does not exist (deliberate scope decision).
- **RAG ingestion not built**: the `knowledge_base_chunks` table exists in the schema but is
  empty. The assistant has no knowledge base to search. All responses come from the LLM's training
  data plus the 4 read tools' real-time data fetches. RAG ingestion is a planned future feature.
- **Single provider (Anthropic Claude)**: no fallback to other LLM providers. If the Anthropic API
  is down, the assistant is unavailable. No provider selection UI.
- **No streaming**: responses arrive as complete blocks. The "Thinking..." indicator is a simple
  animation, not a real progress indicator. Users see nothing until the full response is ready.
- **Max tool iterations cap**: the LLM can chain tool calls (read a summary, then use it to decide
  what to propose), but there is a hard cap on iterations to prevent infinite loops. The cap is
  enforced on the backend, not visible in the frontend.

## Test Coverage

- **Vitest/RTL** (4 tests):
  1. Empty state + first message: panel opens, empty state shows example prompts, user sends a
     message, conversationId is set, assistant response renders.
  2. Proposed action confirm: assistant response includes a write-tool proposal, confirm button
     triggers the confirm mutation, action result appears in the conversation.
  3. Permission gating: user without `ai_assistant:use` does not see the Sparkles icon; user with
     `ai_assistant:use` but not `ai_assistant:confirm_write` sees a disabled confirm button.
  4. Stale conversation recovery: localStorage has a conversationId, the conversation endpoint
     returns 404, panel resets to empty state without errors.
     All passing against MSW-mocked responses.
