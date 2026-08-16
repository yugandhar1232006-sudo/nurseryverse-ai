"""
`AssistantConversationService` -- the persistence + orchestration glue
behind FR-9's three documented endpoints (docs/architecture/02-low-level-
design.md's "Module: AI Assistant"): `POST /ai/assistant/message`,
`POST /ai/assistant/actions/{id}/confirm`, `GET /ai/assistant/
conversations/{id}`.

Owns: creating/loading `AIAssistantConversation` rows (FR-9.4, per-user
threads), persisting every `AIAssistantMessage` (user and assistant,
append-only per that model's own docstring), assembling the bounded
history window handed to `AssistantOrchestrator.run_turn()`, and -- the
FR-9.3 confirmation gate itself -- turning a human's yes/no on a pending
proposal into either a real service-layer write (via `AssistantTool
Registry.execute_confirmed_action`, never bespoke logic) or a documented
no-op (docs/ux/12-ai-workflow-diagrams.md §7: "H -- No --> J[Proposal
discarded, no side effect]").

AUTHORIZATION: unlike `AssistantToolRegistry` (which must authorize per
tool-call because a single conversation turn can touch many different
resources with different scopes), this service does NOT call
`AuthorizationService.authorize()` itself -- the top-level `ai_assistant:
use` / `ai_assistant:confirm_write` gate is enforced by the route layer's
`require_permission` dependency (app/api/deps.py), exactly like every
other service in this codebase (`SalesService`, `CustomerService`, etc.
never call `authorize()` internally either -- see those modules). What
this service DOES enforce itself is per-user conversation *ownership*
(FR-9.4: a conversation belongs to the user who started it, not to their
whole org) -- a `NotFoundError`, not a `PermissionDeniedError`, for a
conversation that exists but isn't the caller's, matching this codebase's
existing "don't leak existence of another tenant's/user's resource via a
403 vs. 404 distinction" convention (see Module 6/9's cross-tenant tests).

CANCEL: the LLD's "Public interfaces" line for this module lists only
`POST /ai/assistant/actions/{id}/confirm` (no separate cancel endpoint),
but docs/ux/12-ai-workflow-diagrams.md §7's own state diagram requires a
"No" branch ("Proposal discarded, no side effect"), and migration 0015's
`action_status` column already carries `cancelled` as a valid value
alongside `pending_confirmation`/`confirmed`. `cancel_action` exists here
to make that documented branch real; app/api/routes wires it through the
SAME `/confirm` endpoint via a `confirm: bool` request field (task #102),
so the actual API surface still matches the LLD's endpoint count exactly
-- "confirm=false" is a way of calling this endpoint, not a new one.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.ai.assistant.knowledge_retrieval import KnowledgeRetrievalService
from app.ai.assistant.orchestrator import AssistantOrchestrator
from app.ai.assistant.tool_registry import AssistantToolRegistry
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain_events import (
    AssistantActionCancelled,
    AssistantActionConfirmed,
    AssistantActionProposed,
    AssistantConversationStarted,
    AssistantMessageSent,
    DomainEventPublisher,
)
from app.models.ai import AIAssistantConversation, AIAssistantMessage
from app.models.identity import User
from app.repositories.interfaces import AIAssistantConversationRepository, AIAssistantMessageRepository

# How many of a conversation's most recent messages are replayed to the
# model on each turn. FR-9.4 requires the FULL history to be *retained*
# (it is -- every row stays in `ai_assistant_messages` forever, and
# `get_conversation` below returns the complete, paginated log) -- it does
# not require every past message to be re-sent to the LLM on every turn,
# which would make a long-running conversation's token cost (and latency)
# grow without bound. 50 messages is a generous window for the kind of
# short, task-focused exchanges this Assistant is designed for (FR-9.1's
# "answer questions about nursery operations" / FR-9.2's "live-data tool
# queries"), not a hard product requirement -- revisit if usage data says
# otherwise.
_HISTORY_WINDOW = 50


class AssistantConversationService:
    def __init__(
        self,
        *,
        conversation_repo: AIAssistantConversationRepository,
        message_repo: AIAssistantMessageRepository,
        orchestrator: AssistantOrchestrator,
        event_publisher: DomainEventPublisher,
        knowledge_retrieval: KnowledgeRetrievalService,
    ) -> None:
        self._conversations = conversation_repo
        self._messages = message_repo
        self._orchestrator = orchestrator
        self._events = event_publisher
        self._knowledge = knowledge_retrieval

    async def send_message(
        self,
        *,
        user: User,
        nursery_id: uuid.UUID,
        role_code: str | None,
        conversation_id: uuid.UUID | None,
        content: str,
        tool_registry: AssistantToolRegistry,
        request_id: str | None,
    ) -> AIAssistantMessage:
        """
        `tool_registry` is constructed fresh per-request by app/api/deps.py
        (see that class's own docstring on why) and passed in here rather
        than owned by this service, so this service never has to know
        which of the many service dependencies a given tool call needs --
        it only orchestrates conversation state.

        Returns the newly created ASSISTANT message (the user message is
        also persisted as a side effect, but the caller -- the API route
        -- only needs the assistant's reply to build its response).
        """
        if not content or not content.strip():
            raise ValidationError("Message content is required.")

        conversation = await self._get_or_create_conversation(
            user=user, nursery_id=nursery_id, conversation_id=conversation_id, request_id=request_id
        )

        user_message = AIAssistantMessage(conversation_id=conversation.id, role="user", content=content.strip())
        user_message = await self._messages.add(user_message)
        await self._events.publish(
            AssistantMessageSent(
                aggregate_id=conversation.id, nursery_id=nursery_id, actor_user_id=user.id,
                message_id=user_message.id, role="user",
            ),
            request_id=request_id,
        )

        history = await self._build_history(conversation.id)
        retrieved_chunks = await self._knowledge.retrieve(query=content.strip(), nursery_id=nursery_id)
        system_prompt = self._build_system_prompt(
            role_code=role_code, context_passages=[c.content for c in retrieved_chunks]
        )
        result = await self._orchestrator.run_turn(history=history, tools=tool_registry, system_prompt=system_prompt)

        proposed_action: dict[str, Any] | None = None
        action_status: str | None = None
        if result.proposed_action is not None:
            proposed_action = {
                "tool_name": result.proposed_action.tool_name,
                "tool_arguments": result.proposed_action.tool_arguments,
                "summary": result.proposed_action.summary,
            }
            action_status = "pending_confirmation"

        assistant_message = AIAssistantMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=result.content,
            proposed_action=proposed_action,
            action_status=action_status,
            model_name=result.model_name,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
        )
        assistant_message = await self._messages.add(assistant_message)

        await self._events.publish(
            AssistantMessageSent(
                aggregate_id=conversation.id, nursery_id=nursery_id, actor_user_id=user.id,
                message_id=assistant_message.id, role="assistant", model_name=result.model_name,
                input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                cost_usd=str(result.cost_usd),
            ),
            request_id=request_id,
        )
        if proposed_action is not None:
            await self._events.publish(
                AssistantActionProposed(
                    aggregate_id=conversation.id, nursery_id=nursery_id, actor_user_id=user.id,
                    message_id=assistant_message.id, tool_name=proposed_action["tool_name"],
                    tool_arguments=proposed_action["tool_arguments"],
                ),
                request_id=request_id,
            )

        return assistant_message

    async def confirm_action(
        self,
        *,
        user: User,
        nursery_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        tool_registry: AssistantToolRegistry,
        request_id: str | None,
    ) -> AIAssistantMessage:
        """
        FR-9.3's confirmation gate itself. Invokes `AssistantToolRegistry.
        execute_confirmed_action` -- the real service method, re-validated
        through its normal path -- then persists a NEW assistant message
        carrying the result (docs/ux/12-ai-workflow-diagrams.md §7:
        "Result confirmed in chat, entity updated"), separate from the
        original proposal message, whose own `action_status` is flipped to
        `confirmed` so it can never be confirmed a second time. Returns
        the new result message.
        """
        conversation, message, proposed = await self._load_pending_action(
            user=user, nursery_id=nursery_id, conversation_id=conversation_id, message_id=message_id
        )

        result_summary = await tool_registry.execute_confirmed_action(
            tool_name=proposed["tool_name"], tool_arguments=proposed["tool_arguments"]
        )

        message.action_status = "confirmed"
        await self._messages.update(message)

        confirmation_message = AIAssistantMessage(
            conversation_id=conversation.id, role="assistant", content=result_summary
        )
        confirmation_message = await self._messages.add(confirmation_message)

        await self._events.publish(
            AssistantActionConfirmed(
                aggregate_id=conversation.id, nursery_id=nursery_id, actor_user_id=user.id,
                message_id=message.id, tool_name=proposed["tool_name"], result_summary=result_summary,
            ),
            request_id=request_id,
        )
        await self._events.publish(
            AssistantMessageSent(
                aggregate_id=conversation.id, nursery_id=nursery_id, actor_user_id=user.id,
                message_id=confirmation_message.id, role="assistant",
            ),
            request_id=request_id,
        )

        return confirmation_message

    async def cancel_action(
        self,
        *,
        user: User,
        nursery_id: uuid.UUID,
        conversation_id: uuid.UUID,
        message_id: uuid.UUID,
        request_id: str | None,
    ) -> AIAssistantMessage:
        """The "No" branch -- proposal discarded, no side effect, no underlying service ever called. See module docstring on why this exists despite not having its own listed endpoint."""
        conversation, message, proposed = await self._load_pending_action(
            user=user, nursery_id=nursery_id, conversation_id=conversation_id, message_id=message_id
        )

        message.action_status = "cancelled"
        message = await self._messages.update(message)

        await self._events.publish(
            AssistantActionCancelled(
                aggregate_id=conversation.id, nursery_id=nursery_id, actor_user_id=user.id,
                message_id=message.id, tool_name=proposed["tool_name"],
            ),
            request_id=request_id,
        )

        return message

    async def get_conversation(
        self,
        *,
        user: User,
        nursery_id: uuid.UUID,
        conversation_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> tuple[AIAssistantConversation, list[AIAssistantMessage], int]:
        conversation = await self._get_owned_conversation(user=user, nursery_id=nursery_id, conversation_id=conversation_id)
        messages, total = await self._messages.list_for_conversation(conversation_id, offset=offset, limit=limit)
        return conversation, messages, total

    # ------------------------------------------------------------------

    async def _get_or_create_conversation(
        self, *, user: User, nursery_id: uuid.UUID, conversation_id: uuid.UUID | None, request_id: str | None
    ) -> AIAssistantConversation:
        if conversation_id is not None:
            return await self._get_owned_conversation(user=user, nursery_id=nursery_id, conversation_id=conversation_id)

        conversation = AIAssistantConversation(nursery_id=nursery_id, user_id=user.id)
        conversation = await self._conversations.add(conversation)
        await self._events.publish(
            AssistantConversationStarted(
                aggregate_id=conversation.id, nursery_id=nursery_id, actor_user_id=user.id, user_id=user.id
            ),
            request_id=request_id,
        )
        return conversation

    async def _get_owned_conversation(
        self, *, user: User, nursery_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> AIAssistantConversation:
        conversation = await self._conversations.get_by_id(conversation_id)
        if conversation is None or conversation.user_id != user.id or conversation.nursery_id != nursery_id:
            # Deliberately the same NotFoundError whether the conversation doesn't exist, belongs to another
            # user, or belongs to another tenant -- never leak which case it was (this codebase's established
            # cross-tenant/cross-user convention, restated from Module 6/9's cross-tenant tests).
            raise NotFoundError("Conversation not found.")
        return conversation

    async def _load_pending_action(
        self, *, user: User, nursery_id: uuid.UUID, conversation_id: uuid.UUID, message_id: uuid.UUID
    ) -> tuple[AIAssistantConversation, AIAssistantMessage, dict[str, Any]]:
        conversation = await self._get_owned_conversation(user=user, nursery_id=nursery_id, conversation_id=conversation_id)

        message = await self._messages.get_by_id(message_id)
        if message is None or message.conversation_id != conversation.id:
            raise NotFoundError("Message not found.")
        if message.role != "assistant" or message.proposed_action is None:
            raise ValidationError("This message has no proposed action to confirm or cancel.")
        if message.action_status != "pending_confirmation":
            raise ConflictError(f"This action is already '{message.action_status}' and cannot be confirmed or cancelled again.")

        return conversation, message, message.proposed_action

    async def _build_history(self, conversation_id: uuid.UUID) -> list[dict[str, Any]]:
        _, total = await self._messages.list_for_conversation(conversation_id, offset=0, limit=1)
        offset = max(0, total - _HISTORY_WINDOW)
        messages, _ = await self._messages.list_for_conversation(conversation_id, offset=offset, limit=_HISTORY_WINDOW)
        return [{"role": m.role, "content": m.content} for m in messages]

    def _build_system_prompt(self, *, role_code: str | None, context_passages: list[str]) -> str:
        """
        docs/architecture/06-ai-architecture.md §7: "system prompt
        establishes the assistant's role, tenant context (org name,
        current branch, user role), and hard constraints (never fabricate
        data, always cite the tool result a claim is based on, never
        execute a write without going through the confirmation flow)".
        Org name/current branch are deliberately omitted here (nursery-
        level tenant isolation is already enforced structurally by every
        tool call's own `AuthorizationService.authorize()` -- see
        `AssistantToolRegistry`'s docstring -- so the model doesn't need
        the org's display name to behave correctly; role is the one piece
        of tenant context that actually changes what the model should
        expect the user can and cannot confirm).
        """
        prompt = (
            "You are the NurseryVerse AI Assistant, a conversational interface for nursery staff "
            "(FR-9.1/FR-9.2). "
            + (f"The current user's role is '{role_code}'. " if role_code else "")
            + "Hard constraints: (1) never fabricate a fact about this organization's plants, "
            "inventory, sales, or AI predictions -- every such claim must come from a tool call you "
            "actually made in this conversation, and you should mention which data you used; (2) your "
            "'propose_*' tools only draft a proposal and NEVER take effect on their own -- a proposed "
            "action only happens if the user explicitly confirms it through the app's confirmation card, "
            "so never tell the user something has been recorded/saved/updated unless a tool result already "
            "told you it was; (3) if a tool call returns an authorization error, tell the user plainly that "
            "they don't have permission for that, don't retry with different arguments to work around it."
        )
        if context_passages:
            joined = "\n\n".join(f"- {p}" for p in context_passages)
            prompt += (
                "\n\nThe following reference material (curated horticultural knowledge and/or this "
                f"organization's own records) may help answer the question -- cite it by name if you use it, "
                f"and don't treat it as more authoritative than a direct tool-call result:\n{joined}"
            )
        return prompt
