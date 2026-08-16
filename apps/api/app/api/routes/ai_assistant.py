"""
Module 10 -- AI Assistant (LLD "Module: AI Assistant"): `POST /ai/assistant/
message`, `POST /ai/assistant/actions/{id}/confirm`, `GET /ai/assistant/
conversations/{id}`.

Permission gating per docs/ux/07-role-permission-matrix.md: `ai_assistant:
use` gates sending messages and reading conversations; `ai_assistant:
confirm_write` additionally gates confirming (not cancelling -- discarding
a proposal is strictly less capable than confirming one, so it's covered
by the same `ai_assistant:use` every role that can chat already has,
matching the matrix's "B (limited to health/watering)" row for roles that
can chat but only confirm a narrower set of actions -- enforced at the
tool-call layer by `AssistantToolRegistry`, not by gating the whole
confirm endpoint on a permission a read-only role would fail outright).

Ownership (a conversation belongs to the user who started it -- FR-9.4) is
enforced inside `AssistantConversationService`, not here (see that
service's own module docstring on why: a `NotFoundError` for
someone-else's conversation, never a 403 that would confirm the
conversation exists).
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import (
    PageParams,
    TenantContext,
    get_assistant_conversation_service,
    get_assistant_tool_registry,
    get_authorization_service,
    get_current_user,
    get_tenant_context,
    raise_if_denied,
    require_permission,
    request_context,
)
from app.ai.assistant.tool_registry import AssistantToolRegistry
from app.core.exceptions import ValidationError
from app.core.responses import ErrorResponse
from app.models.identity import User
from app.services.authorization_service import AuthorizationService
from app.schemas.ai import (
    AssistantConversationDetailResponse,
    AssistantConversationResponse,
    AssistantMessageResponse,
    ConfirmAssistantActionRequest,
    SendAssistantMessageRequest,
)
from app.services.assistant_conversation_service import AssistantConversationService

router = APIRouter()

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Authentication failed"},
    403: {"model": ErrorResponse, "description": "Missing ai_assistant:use / ai_assistant:confirm_write permission"},
    404: {"model": ErrorResponse, "description": "Conversation or message not found (or not owned by the caller)"},
}


def _require_org(tenant: TenantContext) -> uuid.UUID:
    if tenant.org_id is None:
        raise ValidationError("The user has no organization membership -- cannot use the AI Assistant.")
    return tenant.org_id


@router.post(
    "/ai/assistant/message", response_model=AssistantMessageResponse, status_code=status.HTTP_201_CREATED,
    responses={**_ERROR_RESPONSES, 503: {"model": ErrorResponse, "description": "The AI Assistant is temporarily unavailable"}},
    summary="Send a message to the AI Assistant (FR-9.1/9.2); omit conversation_id to start a new conversation",
)
async def send_assistant_message(
    body: SendAssistantMessageRequest, request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    conversation_service: AssistantConversationService = Depends(get_assistant_conversation_service),
    tool_registry: AssistantToolRegistry = Depends(get_assistant_tool_registry),
    _decision: Any = Depends(require_permission("ai_assistant:use")),
) -> AssistantMessageResponse:
    nursery_id = _require_org(tenant)
    message = await conversation_service.send_message(
        user=user, nursery_id=nursery_id, role_code=tenant.role_code, conversation_id=body.conversation_id,
        content=body.content, tool_registry=tool_registry, request_id=request_context(request).request_id,
    )
    return AssistantMessageResponse.model_validate(message)


@router.post(
    "/ai/assistant/actions/{message_id}/confirm", response_model=AssistantMessageResponse,
    responses={
        **_ERROR_RESPONSES,
        409: {"model": ErrorResponse, "description": "This action has already been confirmed or cancelled"},
        422: {"model": ErrorResponse, "description": "This message has no proposed action"},
    },
    summary="Confirm (or, with confirm=false, cancel) a proposed write action (FR-9.3)",
)
async def confirm_assistant_action(
    message_id: uuid.UUID, body: ConfirmAssistantActionRequest, request: Request,
    user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_tenant_context),
    conversation_service: AssistantConversationService = Depends(get_assistant_conversation_service),
    tool_registry: AssistantToolRegistry = Depends(get_assistant_tool_registry),
    authz: AuthorizationService = Depends(get_authorization_service),
    _decision: Any = Depends(require_permission("ai_assistant:use")),
) -> AssistantMessageResponse:
    """
    `body.conversation_id` carries what the LLD's `{id}` path segment
    alone can't (the LLD names the confirm route `POST /ai/assistant/
    actions/{id}/confirm` without specifying whether `{id}` is the
    conversation or the message -- `{id}`=`message_id` here since that's
    what uniquely identifies "the one proposed action", with
    `conversation_id` carried in the body for the ownership check
    `AssistantConversationService._get_owned_conversation` performs).
    `body.confirm=false` cancels instead -- see `ConfirmAssistantAction
    Request`'s own docstring for why this is one endpoint, not two.
    """
    nursery_id = _require_org(tenant)
    if body.confirm:
        # `ai_assistant:confirm_write` is a STRICTER permission than `ai_assistant:use` (the matrix's "B
        # (limited to health/watering)" row) -- checked here in addition to the route-level `ai_assistant:use`
        # dependency above, not instead of it, so a read-only-chat role gets a clean permission error on
        # confirm rather than silently falling through to `AssistantToolRegistry.execute_confirmed_action`
        # (which re-checks the SPECIFIC tool's own permission, e.g. `watering:write` -- this check is the
        # coarser "can this user confirm ANYTHING at all" gate the matrix describes as a separate row).
        decision = await authz.authorize(
            user=user, permission="ai_assistant:confirm_write", resource_type="ai_assistant_message",
            resource_id=message_id, target_nursery_id=nursery_id, context=request_context(request),
        )
        if not decision.allowed:
            raise raise_if_denied(decision)
        result_message = await conversation_service.confirm_action(
            user=user, nursery_id=nursery_id, conversation_id=body.conversation_id, message_id=message_id,
            tool_registry=tool_registry, request_id=request_context(request).request_id,
        )
    else:
        result_message = await conversation_service.cancel_action(
            user=user, nursery_id=nursery_id, conversation_id=body.conversation_id, message_id=message_id,
            request_id=request_context(request).request_id,
        )
    return AssistantMessageResponse.model_validate(result_message)


@router.get(
    "/ai/assistant/conversations/{conversation_id}", response_model=AssistantConversationDetailResponse,
    responses=_ERROR_RESPONSES,
    summary="Get a conversation's metadata and paginated message history (FR-9.4)",
)
async def get_assistant_conversation(
    conversation_id: uuid.UUID, page_params: PageParams = Depends(),
    user: User = Depends(get_current_user), tenant: TenantContext = Depends(get_tenant_context),
    conversation_service: AssistantConversationService = Depends(get_assistant_conversation_service),
    _decision: Any = Depends(require_permission("ai_assistant:use")),
) -> AssistantConversationDetailResponse:
    nursery_id = _require_org(tenant)
    conversation, messages, total = await conversation_service.get_conversation(
        user=user, nursery_id=nursery_id, conversation_id=conversation_id,
        offset=page_params.offset, limit=page_params.page_size,
    )
    return AssistantConversationDetailResponse(
        conversation=AssistantConversationResponse.model_validate(conversation),
        messages=[AssistantMessageResponse.model_validate(m) for m in messages],
        total_messages=total,
    )
