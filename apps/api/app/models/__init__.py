"""
Importing this package registers every model class on `Base.metadata` and
resolves every `relationship()` string reference. Alembic's `env.py` and
any validation/tooling script must `import app.models` (not an individual
submodule) before touching `Base.metadata` or calling
`sqlalchemy.orm.configure_mappers()` — otherwise only a subset of tables
would be visible and cross-module relationships (e.g. Plant -> Species,
DiseaseReport -> AIPrediction) would fail to resolve.

Bounded-context module map (mirrors docs/architecture/05-database-architecture.md §2):
"""
from app.db.base import Base  # noqa: F401

from app.models.identity import (  # noqa: F401
    Invite,
    InviteBranchScope,
    Permission,
    Role,
    RoleAssignment,
    RoleAssignmentBranchScope,
    RolePermission,
    User,
)
from app.models.auth import (  # noqa: F401
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    SecurityEvent,
)
from app.models.authorization import AuthorizationDenial  # noqa: F401
from app.models.organization import Branch, Employee, Nursery  # noqa: F401
from app.models.events import DomainEvent  # noqa: F401
from app.models.catalog import PlantCategory, PlantVariety, Species, Unit  # noqa: F401
from app.models.plants import Plant, PlantImage, PlantTransfer  # noqa: F401
from app.models.digital_twin_records import (  # noqa: F401
    EnvironmentalReading,
    FertilizerLog,
    GrowthTimeline,
    HealthHistory,
    WateringLog,
)
from app.models.disease import DiseaseReport, Treatment  # noqa: F401
from app.models.digital_twin import DigitalTwin, DigitalTwinVersion, EventDispatchLog  # noqa: F401
from app.models.ai import (  # noqa: F401
    AIAssistantConversation,
    AIAssistantMessage,
    AIPrediction,
    AIRecommendation,
    KnowledgeBaseChunk,
)
from app.models.inventory import (  # noqa: F401
    Inventory,
    InventoryLocation,
    StockMovement,
    StockReservation,
)
from app.models.commerce import (  # noqa: F401
    Customer,
    CustomerAddress,
    CustomerCommunication,
    CustomerContact,
    CustomerNote,
    CustomerTag,
    Invoice,
    InvoiceItem,
    InvoiceSale,
    OrderItem,
    Payment,
    Quotation,
    QuotationItem,
    Refund,
    Return,
    ReturnItem,
    Sale,
    SaleItem,
    SalesOrder,
)
from app.models.purchasing import PurchaseOrder, PurchaseOrderItem, Supplier  # noqa: F401
from app.models.notifications import (  # noqa: F401
    Notification,
    NotificationDelivery,
    NotificationPreference,
    NotificationTemplate,
)
from app.models.reports import Passport, QRScanEvent, Report, ScheduledReport  # noqa: F401
from app.models.attachments import Attachment  # noqa: F401
from app.models.platform import (  # noqa: F401
    AuditLog,
    OrgSettings,
    Subscription,
    UsageCounter,
)

__all__ = [
    "Base",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "RoleAssignment",
    "RoleAssignmentBranchScope",
    "Invite",
    "InviteBranchScope",
    "RefreshToken",
    "EmailVerificationToken",
    "PasswordResetToken",
    "SecurityEvent",
    "AuthorizationDenial",
    "Nursery",
    "Branch",
    "Employee",
    "DomainEvent",
    "PlantCategory",
    "Unit",
    "Species",
    "PlantVariety",
    "Plant",
    "PlantImage",
    "PlantTransfer",
    "GrowthTimeline",
    "HealthHistory",
    "EnvironmentalReading",
    "FertilizerLog",
    "WateringLog",
    "DiseaseReport",
    "Treatment",
    "DigitalTwin",
    "DigitalTwinVersion",
    "EventDispatchLog",
    "AIPrediction",
    "AIRecommendation",
    "AIAssistantConversation",
    "AIAssistantMessage",
    "KnowledgeBaseChunk",
    "Inventory",
    "InventoryLocation",
    "StockMovement",
    "StockReservation",
    "Customer",
    "CustomerContact",
    "CustomerAddress",
    "CustomerTag",
    "CustomerNote",
    "CustomerCommunication",
    "Sale",
    "SaleItem",
    "Invoice",
    "InvoiceItem",
    "InvoiceSale",
    "Payment",
    "Quotation",
    "QuotationItem",
    "SalesOrder",
    "OrderItem",
    "Return",
    "ReturnItem",
    "Refund",
    "Supplier",
    "PurchaseOrder",
    "PurchaseOrderItem",
    "Notification",
    "NotificationPreference",
    "NotificationTemplate",
    "NotificationDelivery",
    "Report",
    "ScheduledReport",
    "Passport",
    "QRScanEvent",
    "Attachment",
    "AuditLog",
    "OrgSettings",
    "Subscription",
    "UsageCounter",
]
