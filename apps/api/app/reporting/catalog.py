"""
The static "Report Catalog" (`GET /reports/catalog`) -- every `ReportType`
paired with the human-readable title/description the UI's report picker
shows. `ReportGenerationService` imports `REPORT_TYPE_TITLES` from here
too rather than each of its 18 provider methods hard-coding its own title
string a second time, so the catalog listing and the actual generated
report/file title can never drift apart.
"""
from __future__ import annotations

from app.db.enums import ReportType

REPORT_TYPE_TITLES: dict[ReportType, str] = {
    ReportType.PLANT: "Plant Report",
    ReportType.PLANT_LOSS: "Plant Loss Report",
    ReportType.INVENTORY: "Inventory Report",
    ReportType.SALES: "Sales Report",
    ReportType.REVENUE: "Revenue Report",
    ReportType.PROFIT: "Profit Report",
    ReportType.CUSTOMER: "Customer Report",
    ReportType.EMPLOYEE: "Employee Report",
    ReportType.BRANCH: "Branch Report",
    ReportType.DISEASE: "Disease Report",
    ReportType.GROWTH: "Growth Report",
    ReportType.WATER_USAGE: "Water Usage Report",
    ReportType.FERTILIZER: "Fertilizer Report",
    ReportType.NOTIFICATION: "Notification Report",
    ReportType.AUDIT: "Audit Report",
    ReportType.SECURITY: "Security Report",
    ReportType.PLANT_PASSPORT: "Plant Passport Report",
    ReportType.AI_SUMMARY: "AI Prediction Report",
}

REPORT_TYPE_DESCRIPTIONS: dict[ReportType, str] = {
    ReportType.PLANT: "Full plant portfolio -- status, species, zone, price, batch.",
    ReportType.PLANT_LOSS: "Plants that reached the deceased status, with cause and date.",
    ReportType.INVENTORY: "Bulk stock lines -- quantity on hand, reserved, damaged, value.",
    ReportType.SALES: "Individual completed and voided sale transactions.",
    ReportType.REVENUE: "Daily revenue and transaction-count rollup.",
    ReportType.PROFIT: "Per-sale estimated cost of goods sold and gross profit.",
    ReportType.CUSTOMER: "Customer directory with contact details and type.",
    ReportType.EMPLOYEE: "Employee roster with status, department, and position.",
    ReportType.BRANCH: "Every branch's location, contact, and status.",
    ReportType.DISEASE: "Disease reports -- condition, severity, status, AI-sourced flag.",
    ReportType.GROWTH: "Growth timeline entries -- height, spread, growth stage.",
    ReportType.WATER_USAGE: "Watering log entries -- volume, method, zone/plant.",
    ReportType.FERTILIZER: "Fertilizer application entries -- product, quantity, NPK ratio.",
    ReportType.NOTIFICATION: "Notifications sent to this org's users.",
    ReportType.AUDIT: "Immutable business-mutation audit trail.",
    ReportType.SECURITY: "Authentication/security events for this org's employees.",
    ReportType.PLANT_PASSPORT: "Generated Plant Passport records, versioned per plant.",
    ReportType.AI_SUMMARY: "AI prediction history -- type, model version, confidence.",
}
