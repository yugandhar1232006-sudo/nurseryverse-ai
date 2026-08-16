"""
Top-level API router. Health checks are mounted unprefixed (orchestrators
expect `/healthz`/`/readyz` at the root, not under `/api/v1`); every
business module's router is mounted under `settings.API_V1_PREFIX` as it's
built (Modules 2-15) -- this file gains one `api_router.include_router(...)`
line per completed module and nothing else, so the aggregate router is
always a complete, accurate map of what the API currently exposes.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    admin,
    ai_assistant,
    ai_predictions,
    audit,
    auth,
    branches,
    customers,
    digital_twin,
    disease_reports,
    employees,
    health,
    inventory,
    notifications,
    organizations,
    passport,
    plant_records,
    plant_varieties,
    plants,
    reports,
    sales,
    species,
)

root_router = APIRouter()
root_router.include_router(health.router)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(audit.router, prefix="/audit-log", tags=["audit"])
api_v1_router.include_router(organizations.router, prefix="/orgs", tags=["organizations"])
api_v1_router.include_router(branches.router, prefix="/branches", tags=["branches"])
api_v1_router.include_router(employees.router, prefix="/employees", tags=["employees"])
# species.router mounts its own absolute paths (/plant-categories, /species) -- no prefix.
api_v1_router.include_router(species.router, tags=["species"])
api_v1_router.include_router(plant_varieties.router, prefix="/plant-varieties", tags=["plant-varieties"])
# Module 6 (Plant Lifecycle Management).
api_v1_router.include_router(plants.router, prefix="/plants", tags=["plants"])
# plant_records.router's own paths already start with "/{plant_id}/..." -- mounted under the same /plants prefix.
api_v1_router.include_router(plant_records.router, prefix="/plants", tags=["plant-records"])
# disease_reports.router mounts its own absolute paths (/plants/{plant_id}/disease-reports, /disease-reports) -- no prefix.
api_v1_router.include_router(disease_reports.router, tags=["disease-reports"])
# Module 7 (Plant Digital Twin Engine). digital_twin.router mounts its own absolute paths
# (/plants/{id}/digital-twin/..., /digital-twins) -- no prefix, same pattern as disease_reports.router above.
api_v1_router.include_router(digital_twin.router, tags=["digital-twin"])
# Module 8 (Inventory & Stock Management). inventory.router mounts its own absolute paths
# (/inventory-locations, /inventory, /stock-reservations) -- no prefix, same pattern as digital_twin.router above.
api_v1_router.include_router(inventory.router, tags=["inventory"])
# Module 9 (Sales, CRM, Plant Passport & QR Intelligence). customers.router mounts its own
# absolute paths (/customers, /customers/{id}/...) -- no prefix, same pattern as above.
api_v1_router.include_router(customers.router, tags=["customers"])
# sales.router mounts its own absolute paths (/quotations, /sales-orders, /sales, /invoices,
# /returns, /refunds) -- no prefix, same pattern as digital_twin.router/inventory.router above.
api_v1_router.include_router(sales.router, tags=["sales"])
# passport.router (internal, authenticated) mounts its own absolute paths (/passports,
# /plants/{plant_id}/passports) -- no prefix, same pattern as above.
api_v1_router.include_router(passport.router, tags=["passport"])
# passport.public_router is Module 9's one unauthenticated surface (/public/passport/{token},
# /public/qr/{token}) -- still mounted under API_V1_PREFIX like every other business route (this
# codebase's one deliberate exception to that is health.router, for orchestrator liveness probes
# that conventionally expect a bare path); "no prefix" here means no *auth*, not no versioning.
api_v1_router.include_router(passport.public_router, tags=["passport-public"])
# Module 10 (AI Platform). ai_predictions.router mounts its own absolute paths (/ai/disease-detection/scan,
# /plants/{id}/ai-predictions, /ai/predictions/*, /ai/recommendations*) -- no prefix, same pattern as
# digital_twin.router/inventory.router/customers.router above.
api_v1_router.include_router(ai_predictions.router, tags=["ai-predictions"])
# ai_assistant.router mounts its own absolute paths (/ai/assistant/*) -- no prefix, same pattern as above.
api_v1_router.include_router(ai_assistant.router, tags=["ai-assistant"])
# Module 11 (Notifications & Communication). notifications.router mounts its own absolute paths
# (/notifications, /notifications/preferences, /notifications/templates, /notifications/system-alerts,
# /notifications/retry-due, /notifications/ws) -- no prefix, same pattern as digital_twin.router/
# inventory.router/ai_predictions.router above.
api_v1_router.include_router(notifications.router, tags=["notifications"])
# Module 12 (Reports & Analytics). reports.router mounts its own absolute paths
# (/dashboards/*, /analytics/*, /reports, /reports/*) -- no prefix, same pattern as
# digital_twin.router/inventory.router/notifications.router above.
api_v1_router.include_router(reports.router, tags=["reports"])
# Module 13 (Administration & System Management). admin.router mounts under /admin
# (roles/permissions, user administration, system config, feature flags, audit &
# security administration, system health, AI administration, data management).
# Section 3/4/5 (Employee/Nursery/Branch Administration) capabilities are served by
# the existing employees.router/organizations.router/branches.router above -- see
# admin.py's own module docstring.
api_v1_router.include_router(admin.router, prefix="/admin", tags=["admin"])
# Module 14 (Production Readiness) onward will add further routers here.
