"""
Python Enums backing PostgreSQL native ENUM types.

Every lifecycle/status column in the schema uses a native Postgres ENUM
(not a free-text or unconstrained integer column) so an invalid status
value is a database-level impossibility, not just an application-level bug
— per docs/architecture/05-database-architecture.md §4 (Constraints).
Each enum's value set mirrors a state machine documented in Phase 2/3:
docs/ux/13-digital-twin-lifecycle.md for PlantStatus, and the lifecycle
notes embedded in docs/ux/03-screen-flow-diagrams.md / the LLD for the
others.
"""
from __future__ import annotations

import enum


class PlantStatus(str, enum.Enum):
    IN_PRODUCTION = "in_production"
    READY_FOR_SALE = "ready_for_sale"
    UNDER_TREATMENT = "under_treatment"
    SOLD = "sold"
    DECEASED = "deceased"


class DiseaseReportStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    TREATED = "treated"
    RESOLVED = "resolved"


class DiseaseReportSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TreatmentOutcome(str, enum.Enum):
    ONGOING = "ongoing"
    RECOVERED = "recovered"
    PLANT_LOST = "plant_lost"


class SaleStatus(str, enum.Enum):
    COMPLETED = "completed"
    VOIDED = "voided"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"


class PurchaseOrderStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"


class NurseryStatus(str, enum.Enum):
    """
    Added by Phase 6 Module 4 (Nursery & Organization Management). The
    tenant root (`Nursery`) had no lifecycle/soft-delete concept at all in
    Phase 5 — every other status column in the schema was already
    accounted for, but "Archive Nursery" surfaced this gap while building
    the actual archive endpoint. `branches` (and everything below it)
    carries `ondelete="RESTRICT"` back to `nurseries`, so a hard DELETE was
    never viable anyway; this makes the already-implied soft-delete
    explicit and queryable.
    """

    ACTIVE = "active"
    ARCHIVED = "archived"


class BranchStatus(str, enum.Enum):
    """
    `INACTIVE` already *is* the archived state for a Branch (see
    `Branch`'s own docstring: "Soft-delete only: status transitions to
    inactive, never a hard DELETE"). Module 4's "Archive Branch" reuses
    this transition rather than introducing a third value — a distinct
    ARCHIVED state was considered and rejected as unjustified scope creep
    against the already-approved architecture, since nothing in the
    product requirements distinguishes "temporarily inactive" from
    "permanently archived" for a Branch.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"


class EmployeeStatus(str, enum.Enum):
    ACTIVE = "active"
    INVITED = "invited"
    DEACTIVATED = "deactivated"


class NotificationCategory(str, enum.Enum):
    """
    The original eight (`DISEASE_CONFIRMED` through `PURCHASE_ORDER_RECEIVED`)
    are docs/ux/14-notification-workflow.md's own Trigger Catalog, seeded
    since Phase 5. The remaining thirteen were added by Phase 6 Module 11
    (Notifications) to cover its own required event catalog -- see
    docs/architecture/27-module11-notifications.md for the full mapping of
    each category to the real domain event (existing or newly added) that
    drives it, and for the two categories (`RESERVATION_EXPIRING`,
    `SYSTEM_ALERT`) that have no automatic scheduled trigger in this
    codebase (no Celery worker infrastructure exists anywhere through
    Module 10) and are instead reachable via an on-demand endpoint, the
    same disclosed pattern Module 10 used for `POST /ai/recommendations/refresh`.
    """

    DISEASE_CONFIRMED = "disease_confirmed"
    WATERING_OVERDUE = "watering_overdue"
    LOW_STOCK = "low_stock"
    AI_PREDICTION_READY = "ai_prediction_ready"
    INVOICE_OVERDUE = "invoice_overdue"
    EMPLOYEE_INVITE = "employee_invite"
    PLANT_TRANSFERRED = "plant_transferred"
    PURCHASE_ORDER_RECEIVED = "purchase_order_received"
    # --- Added by Phase 6 Module 11 (Notifications) ---
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    PLANT_REGISTERED = "plant_registered"
    PLANT_READY_FOR_SALE = "plant_ready_for_sale"
    PLANT_UNDER_TREATMENT = "plant_under_treatment"
    PLANT_SOLD = "plant_sold"
    RESERVATION_CREATED = "reservation_created"
    RESERVATION_EXPIRING = "reservation_expiring"
    INVOICE_GENERATED = "invoice_generated"
    PAYMENT_RECEIVED = "payment_received"
    INVENTORY_TRANSFER = "inventory_transfer"
    SYSTEM_ALERT = "system_alert"
    AI_RECOMMENDATION_READY = "ai_recommendation_ready"
    # --- Added by Phase 6 Module 12 (Reports & Analytics) ---
    REPORT_READY = "report_ready"


class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    # Added by Phase 6 Module 11 (Notifications).
    PUSH = "push"


class NotificationDeliveryStatus(str, enum.Enum):
    """
    Added by Phase 6 Module 11 (Notifications). One row per (notification,
    channel) delivery attempt -- `DEAD_LETTER` folds this module's required
    "dead-letter queue strategy" into this same status column (a delivery
    that exhausts `NOTIFICATION_MAX_RETRY_ATTEMPTS` transitions here) rather
    than a second, duplicate table, since a DLQ is queryable/reprocessable
    through the identical `notification_deliveries` rows either way -- see
    that table's own model docstring.
    """

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class NotificationFrequency(str, enum.Enum):
    """Added by Phase 6 Module 11 (Notifications). Backs `notification_preferences.frequency` -- the module's required "frequency controls"."""

    IMMEDIATE = "immediate"
    DAILY_DIGEST = "daily_digest"
    WEEKLY_DIGEST = "weekly_digest"


class AIPredictionType(str, enum.Enum):
    DISEASE_DETECTION = "disease_detection"
    GROWTH_PREDICTION = "growth_prediction"
    SURVIVAL_PREDICTION = "survival_prediction"
    WATER_RECOMMENDATION = "water_recommendation"
    REVENUE_FORECAST = "revenue_forecast"


class AIRecommendationStatus(str, enum.Enum):
    NEW = "new"
    DISMISSED = "dismissed"
    ACTED_UPON = "acted_upon"


class InventoryAdjustmentReason(str, enum.Enum):
    DAMAGE = "damage"
    CORRECTION = "correction"
    INTERNAL_USE = "internal_use"
    PURCHASE_ORDER_RECEIPT = "purchase_order_receipt"
    SALE = "sale"
    RETURN = "return"
    OTHER = "other"


class InventoryLocationType(str, enum.Enum):
    """
    Module 8. Sub-branch physical hierarchy only -- Nursery and Branch
    levels already exist as their own tables (organization.py); an
    InventoryLocation is always nested under a specific branch_id, never
    a standalone Nursery/Branch row duplicated as a location.
    """

    ZONE = "zone"
    GREENHOUSE = "greenhouse"
    OUTDOOR_AREA = "outdoor_area"
    RACK = "rack"
    BENCH = "bench"
    SECTION = "section"


class StockMovementType(str, enum.Enum):
    """Module 8. Every kind of change to a bulk Inventory line funnels through exactly one of these ten types -- one immutable ledger table, not ten."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"
    WASTE = "waste"
    DAMAGE = "damage"
    RESERVATION = "reservation"
    RELEASE = "release"
    SALE = "sale"
    ARCHIVE = "archive"


class StockReservationStatus(str, enum.Enum):
    ACTIVE = "active"
    RELEASED = "released"
    FULFILLED = "fulfilled"
    EXPIRED = "expired"


class CustomerType(str, enum.Enum):
    RETAIL = "retail"
    WHOLESALE = "wholesale"


class SubscriptionPlan(str, enum.Enum):
    STARTER = "starter"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    # --- Added by Phase 6 Module 12 (Reports & Analytics) ---
    JSON = "json"


class ReportType(str, enum.Enum):
    """
    The original six are the Phase 5 skeleton's own FR-18.2/18.3 set. The
    twelve added by Phase 6 Module 12 map one-to-one onto that module's
    kickoff spec's "REPORTS" list — see
    docs/architecture/28-module12-reports-analytics.md for the full
    type-to-data-source mapping. `PLANT_LOSS` (existing) and `PLANT`
    (new) are deliberately both kept: `PLANT_LOSS` is the pre-existing,
    narrowly-scoped "plants that died" report the LLD's Metrics Catalog
    names directly; `PLANT` is the broader plant-portfolio report the
    kickoff spec's "Plant Reports" line calls for. `AI_SUMMARY`
    (existing) is reused for "AI Prediction Reports" rather than adding a
    near-duplicate `AI_PREDICTION` type -- it already covers prediction
    accuracy + disease incidence per FR-18.3.
    """

    INVENTORY = "inventory"
    SALES = "sales"
    REVENUE = "revenue"
    PLANT_LOSS = "plant_loss"
    AI_SUMMARY = "ai_summary"
    PLANT_PASSPORT = "plant_passport"
    # --- Added by Phase 6 Module 12 (Reports & Analytics) ---
    PLANT = "plant"
    PROFIT = "profit"
    CUSTOMER = "customer"
    EMPLOYEE = "employee"
    BRANCH = "branch"
    DISEASE = "disease"
    GROWTH = "growth"
    WATER_USAGE = "water_usage"
    FERTILIZER = "fertilizer"
    NOTIFICATION = "notification"
    AUDIT = "audit"
    SECURITY = "security"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    # --- Added by Phase 6 Module 12 (Reports & Analytics) ---
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class ReportScheduleFrequency(str, enum.Enum):
    """Added by Phase 6 Module 12. Recurrence for `ScheduledReport` -- deliberately the same three-tier grain `NotificationFrequency`'s digest options already use, not a full cron expression (no scheduler infrastructure in this codebase needs finer granularity -- see `ScheduledReportService`'s own docstring)."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class SecurityEventType(str, enum.Enum):
    """
    Added by Phase 6 Module 2 (Authentication). Backs `security_events`
    (app/models/auth.py) — a global, non-tenant-scoped log of
    authentication/security activity, distinct from `audit_logs` (which
    requires a nursery_id and records *business-data* mutations). Login
    attempts happen before an org context exists (a user may not even
    resolve to a real account yet), so they cannot live in `audit_logs`.
    """

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    PASSWORD_CHANGED = "password_changed"
    EMAIL_VERIFICATION_SENT = "email_verification_sent"
    EMAIL_VERIFIED = "email_verified"
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    TOKEN_REFRESHED = "token_refreshed"
    TOKEN_REUSE_DETECTED = "token_reuse_detected"
    RATE_LIMITED = "rate_limited"
    # --- Added by Phase 6 Module 13 (Administration & System Management) ---
    # `ACCOUNT_LOCKED`/`ACCOUNT_UNLOCKED`/`LOGOUT_ALL`/`PASSWORD_RESET_REQUESTED`/
    # `EMAIL_VERIFICATION_SENT` above already exist and are reused as-is for
    # admin-initiated lock/unlock/force-logout/password-reset/email-verification
    # actions too (UserAdminService sets `event_metadata={"initiated_by": "admin",
    # "admin_user_id": ...}` to distinguish an admin action from a self-service
    # one on the same event type, rather than minting a near-duplicate enum value
    # for every action's "...but an admin did it" variant). Only these two states
    # have no existing self-service equivalent at all (a user cannot
    # activate/deactivate their own account) and so need a new value each.
    ACCOUNT_ACTIVATED_BY_ADMIN = "account_activated_by_admin"
    ACCOUNT_DEACTIVATED_BY_ADMIN = "account_deactivated_by_admin"


class AuthorizationDenialReason(str, enum.Enum):
    """
    Added by Phase 6 Module 3 (Authorization). Backs `authorization_denials`
    (app/models/authorization.py) — every authorization *failure* is
    recorded with a specific, structured reason, per the module's
    "every authorization decision must be explainable" and "every
    authorization failure must generate ... Reason" requirements.
    """

    MISSING_PERMISSION = "missing_permission"
    CROSS_TENANT_ORG = "cross_tenant_org"
    CROSS_TENANT_BRANCH = "cross_tenant_branch"
    NOT_OWNER = "not_owner"
    ACCOUNT_INACTIVE = "account_inactive"
    NO_ORG_CONTEXT = "no_org_context"


class EventDispatchStatus(str, enum.Enum):
    """
    Added by Phase 6 Module 7 (Plant Digital Twin Engine). Backs
    `event_dispatch_log` (app/models/digital_twin.py) — one row per
    (event, handler) dispatch attempt, the mechanism that makes the
    event-driven Digital Twin projector idempotent (a `SUCCEEDED` row for
    the same event_id+handler_name pair means "already applied, skip") and
    auditable (every attempt, including failures, is a persisted record
    with a timestamp and error detail) without needing a real message
    broker in this sandbox — see that migration's docstring.
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CustomerAddressType(str, enum.Enum):
    """Added by Phase 6 Module 9 (Sales & CRM). Backs `customer_addresses`."""

    BILLING = "billing"
    SHIPPING = "shipping"
    OTHER = "other"


class CommunicationChannel(str, enum.Enum):
    """Added by Phase 6 Module 9. Backs `customer_communications`."""

    EMAIL = "email"
    PHONE = "phone"
    SMS = "sms"
    IN_PERSON = "in_person"
    OTHER = "other"


class CommunicationDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class QuotationStatus(str, enum.Enum):
    """
    Added by Phase 6 Module 9. A Quotation is a non-binding, pre-sale
    document; DRAFT/SENT are editable, ACCEPTED/REJECTED/EXPIRED are
    terminal, CONVERTED means a SalesOrder has been created from it
    (tracked via `sales_orders.quotation_id`, not a back-reference here —
    see migration 0013's docstring for why).
    """

    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONVERTED = "converted"


class SalesOrderStatus(str, enum.Enum):
    """
    Added by Phase 6 Module 9. Backs `sales_orders.order_status` — the
    order-lifecycle state machine that sits *before* a Sale (the existing,
    immutable Phase-5 "completed transaction" record) is created.
    DRAFT -> CONFIRMED -> PROCESSING -> FULFILLED, or -> CANCELLED from
    any non-terminal state.
    """

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class OrderPaymentStatus(str, enum.Enum):
    """Added by Phase 6 Module 9. Backs `sales_orders.payment_status`."""

    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    REFUNDED = "refunded"


class PaymentMethod(str, enum.Enum):
    """
    Added by Phase 6 Module 9. The module's required tender types. The
    pre-existing `payments.method` column (Phase 5) is a free-text
    String(50), not a native enum — left as-is (changing an existing
    column's type is out of this module's scope and not worth the
    migration risk for a display-only field); this enum is instead used
    to validate the *value* written into that column at the schema layer,
    and is a real native Postgres enum for the brand-new `refunds.method`
    column, which has no legacy free-text data to be compatible with.
    """

    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class ReturnStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class ReturnItemCondition(str, enum.Enum):
    RESALABLE = "resalable"
    DAMAGED = "damaged"
    DISPOSED = "disposed"


class RefundStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
