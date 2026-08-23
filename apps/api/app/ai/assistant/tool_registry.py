"""
`AssistantToolRegistry` -- docs/architecture/02-low-level-design.md's
"Module: AI Assistant": "maps callable tools to existing service
methods -- never bespoke assistant-only logic." The LLM cannot call
arbitrary code, only this fixed, registered set of tools, each backed by
a real method a native page already calls.

SECURITY (the module's own requirement, restated in both
docs/architecture/02-low-level-design.md and docs/architecture/06-ai-
architecture.md §7): every tool call passes the REQUESTING USER'S actual
`RequestUser`/permission context through to the underlying service call,
never a privileged "assistant service account." Concretely: this class is
constructed fresh per conversation turn (app/api/deps.py's
`get_assistant_tool_registry`), carrying the real `User`/
`AuthorizationService`/`RequestContext` for *this* request, and every
tool method re-runs `AuthorizationService.authorize()` before touching
any data -- the exact same check the equivalent native route performs,
not a relaxed or bypassed one. A user whose role doesn't have
`inventory:read` gets the same `PermissionDeniedError` whether they ask
for it by clicking a page or by asking the Assistant.

Read tools (`get_*`) execute immediately and return real data for the
model to reason over. Write tools (`propose_*`) NEVER execute a mutation
themselves -- FR-9.3's mandatory confirmation gate means they only
validate authorization and shape a structured proposal; the actual
service call happens later, from `AssistantConversationService.
confirm_action`, invoking the exact same service method
(`WateringService.record_watering`/`HealthService.record_health`) the
native page would -- restated from that LLD section's own "no
assistant-specific validation bypass exists" note.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import NotFoundError
from app.models.identity import User
from app.repositories.interfaces import AIPredictionRepository, PlantRepository
from app.services.authorization_service import AuthorizationService, RequestContext
from app.services.inventory_service import InventoryService
from app.services.plant_records_service import HealthService, WateringService
from app.services.plant_service import PlantService
from app.services.sales_service import SalesReportingService

# Tools that only read data -- executed immediately, result handed straight back to the model.
READ_TOOLS = frozenset(
    {
        "list_plants",
        "get_plant_summary",
        "get_inventory_status",
        "get_sales_summary",
        "get_ai_predictions",
    }
)
# Tools that propose a write -- NEVER executed by this registry; see module docstring.
WRITE_TOOLS = frozenset({"propose_watering_log", "propose_health_observation"})
ALL_TOOL_NAMES = READ_TOOLS | WRITE_TOOLS


class AssistantToolRegistry:
    def __init__(
        self,
        *,
        user: User,
        org_id: uuid.UUID | None,
        authz: AuthorizationService,
        request_context: RequestContext,
        plant_repo: PlantRepository,
        plant_service: PlantService,
        inventory_service: InventoryService,
        sales_reporting_service: SalesReportingService,
        ai_prediction_repo: AIPredictionRepository,
        watering_service: WateringService,
        health_service: HealthService,
    ) -> None:
        """
        `org_id` is the caller's OWN resolved organization membership
        (`TenantContext.org_id` in app/api/deps.py terms) -- passed in
        already-resolved by the deps.py factory that constructs this
        registry per-request, the same `PermissionService.resolve_for_user`
        result every route's own `get_tenant_context` dependency already
        computes. Used only by the two org-level tools
        (`get_inventory_status`/`get_sales_summary`) that have no single
        resource to fetch-then-derive a tenant from the way
        `get_plant_summary`/`get_ai_predictions` do.
        """
        self._user = user
        self._org_id = org_id
        self._authz = authz
        self._context = request_context
        self._plants = plant_repo
        self._plant_service = plant_service
        self._inventory = inventory_service
        self._sales_reporting = sales_reporting_service
        self._ai_predictions = ai_prediction_repo
        self._watering = watering_service
        self._health = health_service
        self._dispatch: dict[
            str, Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]
        ] = {
            "list_plants": self._list_plants,
            "get_plant_summary": self._get_plant_summary,
            "get_inventory_status": self._get_inventory_status,
            "get_sales_summary": self._get_sales_summary,
            "get_ai_predictions": self._get_ai_predictions,
            "propose_watering_log": self._propose_watering_log,
            "propose_health_observation": self._propose_health_observation,
        }

    def tool_definitions(self) -> list[dict[str, Any]]:
        """Anthropic tool-use JSON schema for every registered tool -- passed to `AssistantOrchestrator`'s Claude API call."""
        return [
            {
                "name": "list_plants",
                "description": "List plants in the nursery. Returns a paginated list with plant id, label, species, status, branch, and zone. Use this to answer questions like 'what plants do we have?', 'list all herbs', 'show me plants ready for sale', etc.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search": {
                            "type": "string",
                            "description": "Optional search term to filter by common label, batch number, or QR token.",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["in_production", "ready_for_sale", "under_treatment", "sold", "deceased"],
                            "description": "Optional: filter by plant status.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of plants to return (default 20, max 50).",
                        },
                    },
                },
            },
            {
                "name": "get_plant_summary",
                "description": "Get a summary of one plant: species, status, branch, batch number, and current state. Use when the user asks about a specific plant by name or id.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "plant_id": {
                            "type": "string",
                            "format": "uuid",
                            "description": "The plant's UUID.",
                        }
                    },
                    "required": ["plant_id"],
                },
            },
            {
                "name": "get_inventory_status",
                "description": "Get current inventory levels (in stock, reserved, damaged, available) for a branch. Use for inventory-level questions.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "branch_id": {
                            "type": "string",
                            "format": "uuid",
                            "description": "The branch's UUID.",
                        }
                    },
                    "required": ["branch_id"],
                },
            },
            {
                "name": "get_sales_summary",
                "description": "Get sales totals (revenue, tax, discount, average sale value, count) for the org, optionally filtered to one branch.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "branch_id": {
                            "type": "string",
                            "format": "uuid",
                            "description": "Optional: restrict to one branch.",
                        }
                    },
                },
            },
            {
                "name": "get_ai_predictions",
                "description": "Get the most recent AI predictions (Growth/Survival/Water/Disease) recorded for a specific plant.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "plant_id": {
                            "type": "string",
                            "format": "uuid",
                            "description": "The plant's UUID.",
                        }
                    },
                    "required": ["plant_id"],
                },
            },
            {
                "name": "propose_watering_log",
                "description": "Propose recording a watering event for a plant. This does NOT record anything -- it only prepares a proposal the user must explicitly confirm before it takes effect.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "plant_id": {"type": "string", "format": "uuid"},
                        "volume_ml": {
                            "type": "number",
                            "description": "Optional volume watered, in mL.",
                        },
                        "notes": {"type": "string", "description": "Optional notes."},
                    },
                    "required": ["plant_id"],
                },
            },
            {
                "name": "propose_health_observation",
                "description": "Propose recording a health observation for a plant. This does NOT record anything -- it only prepares a proposal the user must explicitly confirm before it takes effect.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "plant_id": {"type": "string", "format": "uuid"},
                        "status_label": {
                            "type": "string",
                            "description": "e.g. 'healthy', 'stressed', 'recovering'.",
                        },
                        "health_score": {
                            "type": "number",
                            "description": "Optional 0-100 score.",
                        },
                        "notes": {"type": "string"},
                    },
                    "required": ["plant_id", "status_label"],
                },
            },
        ]

    async def invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handler = self._dispatch.get(tool_name)
        if handler is None:
            return {"error": f"Unknown tool '{tool_name}'."}
        return await handler(arguments)

    @staticmethod
    def _parse_uuid(value: str) -> uuid.UUID | None:
        """Parse a string as UUID, returning None on malformed input."""
        try:
            return uuid.UUID(value)
        except ValueError:
            return None

    @staticmethod
    def _require_uuid(
        args: dict[str, Any], key: str
    ) -> tuple[uuid.UUID | None, str | None]:
        """Extract a UUID from args[key]; returns (uuid, error_msg)."""
        if key not in args:
            return None, f"Missing required argument: {key}."
        parsed = AssistantToolRegistry._parse_uuid(str(args[key]))
        if parsed is None:
            return None, f"Invalid {key}: not a valid UUID."
        return parsed, None

    # ------------------------------------------------------------------
    # Read tools
    # ------------------------------------------------------------------

    async def _list_plants(self, args: dict[str, Any]) -> dict[str, Any]:
        if self._org_id is None:
            return {"error": "No organization context."}
        decision = await self._authz.authorize(
            user=self._user,
            permission="plants:read",
            resource_type="plant",
            target_nursery_id=self._org_id,
            context=self._context,
        )
        if not decision.allowed:
            return {"error": "You do not have permission to view plants."}
        from app.db.enums import PlantStatus

        status_filter = None
        if args.get("status"):
            try:
                status_filter = PlantStatus(args["status"])
            except ValueError:
                return {"error": f"Invalid status: {args['status']}"}
        limit = min(int(args.get("limit") or 20), 50)
        plants, total = await self._plants.list_for_nursery(
            self._org_id,
            offset=0,
            limit=limit,
            status=status_filter,
            search=args.get("search"),
        )
        return {
            "total": total,
            "plants": [
                {
                    "plant_id": str(p.id),
                    "common_label": p.common_label,
                    "status": p.status.value if p.status else None,
                    "branch_id": str(p.branch_id),
                    "zone": p.zone,
                    "batch_number": p.batch_number,
                    "planted_at": p.planted_at.isoformat() if p.planted_at else None,
                    "age_days": (datetime.now(timezone.utc).date() - p.planted_at.date()).days if p.planted_at else None,
                }
                for p in plants
            ],
        }

    async def _get_plant_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        plant_id, err = self._require_uuid(args, "plant_id")
        if err:
            return {"error": err}
        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            return {"error": "Plant not found."}
        decision = await self._authz.authorize(
            user=self._user,
            permission="plants:read",
            resource_type="plant",
            resource_id=plant.id,
            target_nursery_id=plant.nursery_id,
            target_branch_id=plant.branch_id,
            context=self._context,
        )
        if not decision.allowed:
            return {"error": "You do not have permission to view this plant."}
        return {
            "plant_id": str(plant.id),
            "common_label": plant.common_label,
            "batch_number": plant.batch_number,
            "status": plant.status.value if plant.status else None,
            "branch_id": str(plant.branch_id),
            "zone": plant.zone,
        }

    async def _get_inventory_status(self, args: dict[str, Any]) -> dict[str, Any]:
        if self._org_id is None:
            return {"error": "No organization context."}
        branch_id, err = self._require_uuid(args, "branch_id")
        if err:
            return {"error": err}
        decision = await self._authz.authorize(
            user=self._user,
            permission="inventory:read",
            resource_type="inventory",
            target_nursery_id=self._org_id,
            target_branch_id=branch_id,
            context=self._context,
        )
        if not decision.allowed:
            return {
                "error": "You do not have permission to view inventory for this branch."
            }
        return await self._inventory.inventory_summary(
            self._org_id, branch_id=branch_id
        )

    async def _get_sales_summary(self, args: dict[str, Any]) -> dict[str, Any]:
        if self._org_id is None:
            return {"error": "No organization context."}
        org_id = self._org_id
        branch_id = None
        if args.get("branch_id"):
            branch_id, err = self._require_uuid(args, "branch_id")
            if err:
                return {"error": err}
        decision = await self._authz.authorize(
            user=self._user,
            permission="sales:read",
            resource_type="sale",
            target_nursery_id=org_id,
            target_branch_id=branch_id,
            context=self._context,
        )
        if not decision.allowed:
            return {"error": "You do not have permission to view sales data."}
        filters: dict[str, Any] = {"branch_id": branch_id} if branch_id else {}
        return await self._sales_reporting.sales_report(org_id, **filters)

    async def _get_ai_predictions(self, args: dict[str, Any]) -> dict[str, Any]:
        plant_id, err = self._require_uuid(args, "plant_id")
        if err:
            return {"error": err}
        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            return {"error": "Plant not found."}
        decision = await self._authz.authorize(
            user=self._user,
            permission="ai_predictions:read",
            resource_type="ai_prediction",
            resource_id=plant.id,
            target_nursery_id=plant.nursery_id,
            target_branch_id=plant.branch_id,
            context=self._context,
        )
        if not decision.allowed:
            return {
                "error": "You do not have permission to view AI predictions for this plant."
            }
        rows, total = await self._ai_predictions.list_for_plant(
            plant_id, offset=0, limit=10
        )
        return {
            "total": total,
            "predictions": [
                {
                    "prediction_type": p.prediction_type.value,
                    "model_version": p.model_version,
                    "confidence": str(p.confidence)
                    if p.confidence is not None
                    else None,
                    "explanation": p.explanation,
                    "result": p.result,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in rows
            ],
        }

    # ------------------------------------------------------------------
    # Write tools -- proposals only, never executed here
    # ------------------------------------------------------------------

    async def _propose_watering_log(self, args: dict[str, Any]) -> dict[str, Any]:
        plant_id, err = self._require_uuid(args, "plant_id")
        if err:
            return {"error": err}
        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            return {"error": "Plant not found."}
        decision = await self._authz.authorize(
            user=self._user,
            permission="watering:write",
            resource_type="plant",
            resource_id=plant.id,
            target_nursery_id=plant.nursery_id,
            target_branch_id=plant.branch_id,
            context=self._context,
        )
        if not decision.allowed:
            return {
                "error": "You do not have permission to record watering for this plant."
            }
        return {
            "requires_confirmation": True,
            "tool_name": "propose_watering_log",
            "tool_arguments": {
                "plant_id": str(plant_id),
                "volume_ml": args.get("volume_ml"),
                "notes": args.get("notes"),
            },
            "summary": f"Record a watering event for plant {plant.common_label or plant_id}"
            + (f" ({args['volume_ml']} mL)" if args.get("volume_ml") else "")
            + ".",
        }

    async def _propose_health_observation(self, args: dict[str, Any]) -> dict[str, Any]:
        plant_id, err = self._require_uuid(args, "plant_id")
        if err:
            return {"error": err}
        plant = await self._plants.get_by_id(plant_id)
        if plant is None:
            return {"error": "Plant not found."}
        decision = await self._authz.authorize(
            user=self._user,
            permission="health:write",
            resource_type="plant",
            resource_id=plant.id,
            target_nursery_id=plant.nursery_id,
            target_branch_id=plant.branch_id,
            context=self._context,
        )
        if not decision.allowed:
            return {
                "error": "You do not have permission to record a health observation for this plant."
            }
        status_label = str(args["status_label"])
        return {
            "requires_confirmation": True,
            "tool_name": "propose_health_observation",
            "tool_arguments": {
                "plant_id": str(plant_id),
                "status_label": status_label,
                "health_score": args.get("health_score"),
                "notes": args.get("notes"),
            },
            "summary": f"Record a health observation ('{status_label}') for plant {plant.common_label or plant_id}.",
        }

    # ------------------------------------------------------------------

    async def execute_confirmed_action(
        self, *, tool_name: str, tool_arguments: dict[str, Any]
    ) -> str:
        """
        Called ONLY from `AssistantConversationService.confirm_action`,
        after a human has explicitly confirmed a previously proposed
        write -- invokes the real service method, re-validating through
        its normal path exactly as the native page would (no assistant-
        specific bypass). Returns a short, human-readable result summary
        (`AssistantActionConfirmed.result_summary`), not the raw service
        response.
        """
        if tool_name == "propose_watering_log":
            watering_entry = await self._watering.record_watering(
                plant_id=uuid.UUID(tool_arguments["plant_id"]),
                actor_user_id=self._user.id,
                volume_ml=tool_arguments.get("volume_ml"),
                notes=tool_arguments.get("notes"),
                request_id=self._context.request_id,
            )
            return f"Watering log recorded (id {watering_entry.id})."
        if tool_name == "propose_health_observation":
            health_entry = await self._health.record_health(
                plant_id=uuid.UUID(tool_arguments["plant_id"]),
                status_label=tool_arguments["status_label"],
                actor_user_id=self._user.id,
                health_score=tool_arguments.get("health_score"),
                notes=tool_arguments.get("notes"),
                request_id=self._context.request_id,
            )
            return f"Health observation recorded (id {health_entry.id})."
        raise NotFoundError(f"Unknown confirmable tool '{tool_name}'.")
