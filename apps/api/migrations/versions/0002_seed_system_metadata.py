"""Seed system metadata — roles, permissions, role_permissions, plant
categories, and units.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05

Per the Phase 5 seed-data rules: this migration seeds ONLY system metadata
that every customer Org needs identically on day one — the 6 system roles
and their permission grants (mechanically parsed from
docs/ux/07-role-permission-matrix.md by scripts/generate_seed_migration.py,
not hand-transcribed, so it cannot drift from the documented matrix), plus
the two reference master tables (PlantCategory, Unit) a brand-new Org's
Species/Inventory forms need populated dropdowns for immediately.

Explicitly NOT seeded here, per the Phase 5 rule (the application creates
this, not the migration): no Nursery/Branch/Employee rows, no Species,
Plants, Inventory, Customers, Sales, or any other business data. There is
also no data-carrying "statuses" table to seed — every lifecycle status in
this schema is a native PostgreSQL ENUM (created by 0001, not a seeded
lookup table), so "seed the statuses" is already satisfied by the schema
itself, not a data migration.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


# Lightweight table definitions for bulk_insert — deliberately NOT importing
# app.models here (a seed migration must stay valid forever, even after the
# ORM models evolve; coupling a migration to the live model class is a
# common source of migrations that silently break years later).
roles_table = sa.table(
    "roles",
    sa.column("id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("is_system_role", sa.Boolean()),
    sa.column("permission_ceiling_role_code", sa.String()),
)

permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("module", sa.String()),
    sa.column("action", sa.String()),
    sa.column("description", sa.String()),
)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", sa.UUID()),
    sa.column("permission_id", sa.UUID()),
    sa.column("scope", sa.String()),
)

plant_categories_table = sa.table(
    "plant_categories",
    sa.column("id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.String()),
)

units_table = sa.table(
    "units",
    sa.column("id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("unit_type", sa.String()),
)

ROLES = [
        {'id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'code': 'owner', 'name': 'Org Owner', 'is_system_role': True, 'permission_ceiling_role_code': 'org_admin'},
        {'id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'code': 'org_admin', 'name': 'Org Admin', 'is_system_role': True, 'permission_ceiling_role_code': 'org_admin'},
        {'id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'code': 'branch_manager', 'name': 'Branch Manager', 'is_system_role': True, 'permission_ceiling_role_code': 'org_admin'},
        {'id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'code': 'horticulturist', 'name': 'Horticulturist / Plant Care', 'is_system_role': True, 'permission_ceiling_role_code': 'org_admin'},
        {'id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'code': 'sales_staff', 'name': 'Sales Staff', 'is_system_role': True, 'permission_ceiling_role_code': 'org_admin'},
        {'id': '2756c55e-3bc4-4cee-941f-4d23bae473a5', 'code': 'platform_admin', 'name': 'Platform Admin (internal)', 'is_system_role': True, 'permission_ceiling_role_code': 'org_admin'},
]

PERMISSIONS = [
        {'id': '6db3aa06-03b3-4913-872e-26ef4740ff09', 'code': 'ai_assistant:confirm_write', 'module': 'ai_assistant', 'action': 'confirm_write', 'description': 'Confirm write access for the ai assistant module'},
        {'id': '9c33beb4-b747-441f-ad22-d938e8d0ae48', 'code': 'ai_assistant:use', 'module': 'ai_assistant', 'action': 'use', 'description': 'Use access for the ai assistant module'},
        {'id': '76b6ffe0-4711-4285-b8ba-a0870e6b6005', 'code': 'ai_predictions:read', 'module': 'ai_predictions', 'action': 'read', 'description': 'Read access for the ai predictions module'},
        {'id': '43a79259-0f1d-4452-af28-5139db2cfb84', 'code': 'ai_predictions:run', 'module': 'ai_predictions', 'action': 'run', 'description': 'Run access for the ai predictions module'},
        {'id': '3217ca0d-468d-4847-be27-600d29e9b9b7', 'code': 'audit:read', 'module': 'audit', 'action': 'read', 'description': 'Read access for the audit module'},
        {'id': '1db6a258-f46f-46d9-b6d4-cf4d6291efa0', 'code': 'branch:delete', 'module': 'branch', 'action': 'delete', 'description': 'Delete access for the branch module'},
        {'id': '5e3ae4d9-bb0a-429d-87ef-6f4d7a8bfbe3', 'code': 'branch:read', 'module': 'branch', 'action': 'read', 'description': 'Read access for the branch module'},
        {'id': '4cbf530c-0f42-4ab9-aa53-140ef23a0660', 'code': 'branch:write', 'module': 'branch', 'action': 'write', 'description': 'Write access for the branch module'},
        {'id': '2ae1cebd-24df-4f28-a959-b19e273ca83c', 'code': 'customers:read', 'module': 'customers', 'action': 'read', 'description': 'Read access for the customers module'},
        {'id': 'b040030f-2987-49b2-a1a0-89ffcb1baf96', 'code': 'customers:write', 'module': 'customers', 'action': 'write', 'description': 'Write access for the customers module'},
        {'id': '5e1cbb4a-e2df-454f-a710-32b6c52ef6f3', 'code': 'disease:approve', 'module': 'disease', 'action': 'approve', 'description': 'Approve access for the disease module'},
        {'id': 'b0cda730-535b-4ee3-a332-eac91df5435a', 'code': 'disease:read', 'module': 'disease', 'action': 'read', 'description': 'Read access for the disease module'},
        {'id': '2b3f3dac-9321-4781-a565-3f6144230b2f', 'code': 'disease:write', 'module': 'disease', 'action': 'write', 'description': 'Write access for the disease module'},
        {'id': 'dc15c824-d2d2-4b5c-a379-91e1ad948cb0', 'code': 'employees:delete', 'module': 'employees', 'action': 'delete', 'description': 'Delete access for the employees module'},
        {'id': 'f9ef12fc-481c-4709-9e67-b194225e44bf', 'code': 'employees:read', 'module': 'employees', 'action': 'read', 'description': 'Read access for the employees module'},
        {'id': 'c34f32b1-ef1f-4964-99e4-266a013b7e29', 'code': 'employees:write', 'module': 'employees', 'action': 'write', 'description': 'Write access for the employees module'},
        {'id': 'dee1677f-60a8-4d89-8c03-d680d16b1d07', 'code': 'environmental:read', 'module': 'environmental', 'action': 'read', 'description': 'Read access for the environmental module'},
        {'id': '937e5f72-30d1-4f93-ac90-69360db18458', 'code': 'environmental:write', 'module': 'environmental', 'action': 'write', 'description': 'Write access for the environmental module'},
        {'id': 'a840012f-c528-46e4-be9f-a01ecbab4405', 'code': 'growth:read', 'module': 'growth', 'action': 'read', 'description': 'Read access for the growth module'},
        {'id': '5ef9769b-82cc-493e-9eab-87c2b639eb66', 'code': 'growth:write', 'module': 'growth', 'action': 'write', 'description': 'Write access for the growth module'},
        {'id': '4e2fc997-978a-4c7d-ad32-307af1603f7e', 'code': 'health:read', 'module': 'health', 'action': 'read', 'description': 'Read access for the health module'},
        {'id': 'c1daf609-efc7-4ace-ada1-c005dcb6bdbd', 'code': 'health:write', 'module': 'health', 'action': 'write', 'description': 'Write access for the health module'},
        {'id': '90775086-1580-46c4-b4e8-832c129279a8', 'code': 'inventory:adjust', 'module': 'inventory', 'action': 'adjust', 'description': 'Adjust access for the inventory module'},
        {'id': 'f0464b13-7686-401e-a853-f005f66599b9', 'code': 'inventory:read', 'module': 'inventory', 'action': 'read', 'description': 'Read access for the inventory module'},
        {'id': '8dd41a67-128f-4868-85fb-058e2458040a', 'code': 'inventory:write', 'module': 'inventory', 'action': 'write', 'description': 'Write access for the inventory module'},
        {'id': '5774bbad-0836-4142-a571-898a4706bfc7', 'code': 'invoices:read', 'module': 'invoices', 'action': 'read', 'description': 'Read access for the invoices module'},
        {'id': '5b1bf37a-82d5-4aa1-8bf7-4da34314fea5', 'code': 'invoices:void', 'module': 'invoices', 'action': 'void', 'description': 'Void access for the invoices module'},
        {'id': '7c3739a2-74e1-401f-80b6-678244503584', 'code': 'invoices:write', 'module': 'invoices', 'action': 'write', 'description': 'Write access for the invoices module'},
        {'id': '5404bfe5-a0c4-40b5-b6bd-3da3a947aed7', 'code': 'notifications:manage_preferences', 'module': 'notifications', 'action': 'manage_preferences', 'description': 'Manage preferences access for the notifications module'},
        {'id': '997326fe-f8a2-42c0-947b-af6cd841c92d', 'code': 'notifications:read', 'module': 'notifications', 'action': 'read', 'description': 'Read access for the notifications module'},
        {'id': 'c9922566-0018-4177-98c3-cd7cf9fd385d', 'code': 'org:delete', 'module': 'org', 'action': 'delete', 'description': 'Delete access for the org module'},
        {'id': 'e7e8a445-7333-4fe9-822e-c70d2ec3c6f5', 'code': 'org:read', 'module': 'org', 'action': 'read', 'description': 'Read access for the org module'},
        {'id': 'f98668d5-bbe3-41d1-8a9a-52373f6eedd4', 'code': 'org:write', 'module': 'org', 'action': 'write', 'description': 'Write access for the org module'},
        {'id': '39a52e01-658b-4c70-b1f2-56388108c3fb', 'code': 'passport:generate', 'module': 'passport', 'action': 'generate', 'description': 'Generate access for the passport module'},
        {'id': '39eefd24-ef52-4536-a84e-fb50866569de', 'code': 'passport:read', 'module': 'passport', 'action': 'read', 'description': 'Read access for the passport module'},
        {'id': 'c61de33d-bed6-44c4-a874-3a8b3b637f49', 'code': 'plants:read', 'module': 'plants', 'action': 'read', 'description': 'Read access for the plants module'},
        {'id': '7911461f-5801-40d7-8371-74182efd9d94', 'code': 'plants:transfer', 'module': 'plants', 'action': 'transfer', 'description': 'Transfer access for the plants module'},
        {'id': 'b1c9d809-6494-4e56-8a0b-eeb1313bdc59', 'code': 'plants:write', 'module': 'plants', 'action': 'write', 'description': 'Write access for the plants module'},
        {'id': '52622aec-d6ab-49a8-ba5f-6e38ae38df43', 'code': 'purchase_orders:read', 'module': 'purchase_orders', 'action': 'read', 'description': 'Read access for the purchase orders module'},
        {'id': '6a04c641-5375-4608-99c5-ff6a2b61da32', 'code': 'purchase_orders:receive', 'module': 'purchase_orders', 'action': 'receive', 'description': 'Receive access for the purchase orders module'},
        {'id': '881cc63c-2bf9-4a3b-b710-854a4f5f9b74', 'code': 'purchase_orders:write', 'module': 'purchase_orders', 'action': 'write', 'description': 'Write access for the purchase orders module'},
        {'id': 'cd54476a-aa75-444f-8566-6eb2cc225070', 'code': 'reports:export', 'module': 'reports', 'action': 'export', 'description': 'Export access for the reports module'},
        {'id': '3fb4951e-e42c-4e73-8e09-2372614ab5b5', 'code': 'reports:read', 'module': 'reports', 'action': 'read', 'description': 'Read access for the reports module'},
        {'id': 'dc1f5f82-1b64-4c12-b1f3-d46b23173779', 'code': 'roles:manage', 'module': 'roles', 'action': 'manage', 'description': 'Manage access for the roles module'},
        {'id': '19ac423f-0988-46d5-a417-7382886ba803', 'code': 'sales:read', 'module': 'sales', 'action': 'read', 'description': 'Read access for the sales module'},
        {'id': 'ae292e25-6513-4d6d-b7f3-7f91c4982990', 'code': 'sales:void', 'module': 'sales', 'action': 'void', 'description': 'Void access for the sales module'},
        {'id': '8f1e748d-a94f-4a4f-81c6-f5e38b1da21c', 'code': 'sales:write', 'module': 'sales', 'action': 'write', 'description': 'Write access for the sales module'},
        {'id': '3efb0248-9b2d-4cca-8c46-dc2aec85f073', 'code': 'settings:billing', 'module': 'settings', 'action': 'billing', 'description': 'Billing access for the settings module'},
        {'id': '8416a38d-adcf-4359-876e-6a5b84608186', 'code': 'settings:branch', 'module': 'settings', 'action': 'branch', 'description': 'Branch access for the settings module'},
        {'id': 'dd1c7464-2b52-4b7e-b747-1b69e1c728b1', 'code': 'settings:org', 'module': 'settings', 'action': 'org', 'description': 'Org access for the settings module'},
        {'id': 'dbb89d6c-95ac-4258-a60e-f6a2380410dd', 'code': 'species:delete', 'module': 'species', 'action': 'delete', 'description': 'Delete access for the species module'},
        {'id': '1a78e51b-e2c7-4b98-b2af-7c3266e2b7ad', 'code': 'species:read', 'module': 'species', 'action': 'read', 'description': 'Read access for the species module'},
        {'id': '861be079-7804-4159-a457-d46a03ddfb54', 'code': 'species:write', 'module': 'species', 'action': 'write', 'description': 'Write access for the species module'},
        {'id': '052876a3-931d-45d3-b2f5-87fd15f653b4', 'code': 'suppliers:delete', 'module': 'suppliers', 'action': 'delete', 'description': 'Delete access for the suppliers module'},
        {'id': 'eea7bae8-33a5-4b56-b239-73cbcd2d07d0', 'code': 'suppliers:read', 'module': 'suppliers', 'action': 'read', 'description': 'Read access for the suppliers module'},
        {'id': 'ad9dcc30-c425-4b42-babc-e33ab163ea32', 'code': 'suppliers:write', 'module': 'suppliers', 'action': 'write', 'description': 'Write access for the suppliers module'},
        {'id': '66eeccd8-4c1b-4bd8-ba30-5a4f379fdebc', 'code': 'watering:read', 'module': 'watering', 'action': 'read', 'description': 'Read access for the watering module'},
        {'id': '0cf918d6-53b8-4cb9-b1fa-6626bcf3fb1f', 'code': 'watering:write', 'module': 'watering', 'action': 'write', 'description': 'Write access for the watering module'},
]

ROLE_PERMISSIONS = [
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'e7e8a445-7333-4fe9-822e-c70d2ec3c6f5', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'e7e8a445-7333-4fe9-822e-c70d2ec3c6f5', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'e7e8a445-7333-4fe9-822e-c70d2ec3c6f5', 'scope': 'R'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': 'e7e8a445-7333-4fe9-822e-c70d2ec3c6f5', 'scope': 'R'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': 'e7e8a445-7333-4fe9-822e-c70d2ec3c6f5', 'scope': 'R'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'f98668d5-bbe3-41d1-8a9a-52373f6eedd4', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'f98668d5-bbe3-41d1-8a9a-52373f6eedd4', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'c9922566-0018-4177-98c3-cd7cf9fd385d', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '5e3ae4d9-bb0a-429d-87ef-6f4d7a8bfbe3', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '5e3ae4d9-bb0a-429d-87ef-6f4d7a8bfbe3', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '5e3ae4d9-bb0a-429d-87ef-6f4d7a8bfbe3', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '5e3ae4d9-bb0a-429d-87ef-6f4d7a8bfbe3', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '5e3ae4d9-bb0a-429d-87ef-6f4d7a8bfbe3', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '4cbf530c-0f42-4ab9-aa53-140ef23a0660', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '4cbf530c-0f42-4ab9-aa53-140ef23a0660', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '1db6a258-f46f-46d9-b6d4-cf4d6291efa0', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '1db6a258-f46f-46d9-b6d4-cf4d6291efa0', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'f9ef12fc-481c-4709-9e67-b194225e44bf', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'f9ef12fc-481c-4709-9e67-b194225e44bf', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'f9ef12fc-481c-4709-9e67-b194225e44bf', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'c34f32b1-ef1f-4964-99e4-266a013b7e29', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'c34f32b1-ef1f-4964-99e4-266a013b7e29', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'c34f32b1-ef1f-4964-99e4-266a013b7e29', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'dc15c824-d2d2-4b5c-a379-91e1ad948cb0', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'dc15c824-d2d2-4b5c-a379-91e1ad948cb0', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'dc1f5f82-1b64-4c12-b1f3-d46b23173779', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'dc1f5f82-1b64-4c12-b1f3-d46b23173779', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '1a78e51b-e2c7-4b98-b2af-7c3266e2b7ad', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '1a78e51b-e2c7-4b98-b2af-7c3266e2b7ad', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '1a78e51b-e2c7-4b98-b2af-7c3266e2b7ad', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '1a78e51b-e2c7-4b98-b2af-7c3266e2b7ad', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '1a78e51b-e2c7-4b98-b2af-7c3266e2b7ad', 'scope': 'R'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '861be079-7804-4159-a457-d46a03ddfb54', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '861be079-7804-4159-a457-d46a03ddfb54', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '861be079-7804-4159-a457-d46a03ddfb54', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'dbb89d6c-95ac-4258-a60e-f6a2380410dd', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'dbb89d6c-95ac-4258-a60e-f6a2380410dd', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'c61de33d-bed6-44c4-a874-3a8b3b637f49', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'c61de33d-bed6-44c4-a874-3a8b3b637f49', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'c61de33d-bed6-44c4-a874-3a8b3b637f49', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': 'c61de33d-bed6-44c4-a874-3a8b3b637f49', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': 'c61de33d-bed6-44c4-a874-3a8b3b637f49', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'b1c9d809-6494-4e56-8a0b-eeb1313bdc59', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'b1c9d809-6494-4e56-8a0b-eeb1313bdc59', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'b1c9d809-6494-4e56-8a0b-eeb1313bdc59', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': 'b1c9d809-6494-4e56-8a0b-eeb1313bdc59', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '7911461f-5801-40d7-8371-74182efd9d94', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '7911461f-5801-40d7-8371-74182efd9d94', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '7911461f-5801-40d7-8371-74182efd9d94', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'a840012f-c528-46e4-be9f-a01ecbab4405', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'a840012f-c528-46e4-be9f-a01ecbab4405', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'a840012f-c528-46e4-be9f-a01ecbab4405', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': 'a840012f-c528-46e4-be9f-a01ecbab4405', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '5ef9769b-82cc-493e-9eab-87c2b639eb66', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '5ef9769b-82cc-493e-9eab-87c2b639eb66', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '5ef9769b-82cc-493e-9eab-87c2b639eb66', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '5ef9769b-82cc-493e-9eab-87c2b639eb66', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '4e2fc997-978a-4c7d-ad32-307af1603f7e', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '4e2fc997-978a-4c7d-ad32-307af1603f7e', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '4e2fc997-978a-4c7d-ad32-307af1603f7e', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '4e2fc997-978a-4c7d-ad32-307af1603f7e', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'c1daf609-efc7-4ace-ada1-c005dcb6bdbd', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'c1daf609-efc7-4ace-ada1-c005dcb6bdbd', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'c1daf609-efc7-4ace-ada1-c005dcb6bdbd', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': 'c1daf609-efc7-4ace-ada1-c005dcb6bdbd', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'b0cda730-535b-4ee3-a332-eac91df5435a', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'b0cda730-535b-4ee3-a332-eac91df5435a', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'b0cda730-535b-4ee3-a332-eac91df5435a', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': 'b0cda730-535b-4ee3-a332-eac91df5435a', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '2b3f3dac-9321-4781-a565-3f6144230b2f', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '2b3f3dac-9321-4781-a565-3f6144230b2f', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '2b3f3dac-9321-4781-a565-3f6144230b2f', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '2b3f3dac-9321-4781-a565-3f6144230b2f', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '5e1cbb4a-e2df-454f-a710-32b6c52ef6f3', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '5e1cbb4a-e2df-454f-a710-32b6c52ef6f3', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '5e1cbb4a-e2df-454f-a710-32b6c52ef6f3', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '5e1cbb4a-e2df-454f-a710-32b6c52ef6f3', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '76b6ffe0-4711-4285-b8ba-a0870e6b6005', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '76b6ffe0-4711-4285-b8ba-a0870e6b6005', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '76b6ffe0-4711-4285-b8ba-a0870e6b6005', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '76b6ffe0-4711-4285-b8ba-a0870e6b6005', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '43a79259-0f1d-4452-af28-5139db2cfb84', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '43a79259-0f1d-4452-af28-5139db2cfb84', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '43a79259-0f1d-4452-af28-5139db2cfb84', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '43a79259-0f1d-4452-af28-5139db2cfb84', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '9c33beb4-b747-441f-ad22-d938e8d0ae48', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '9c33beb4-b747-441f-ad22-d938e8d0ae48', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '9c33beb4-b747-441f-ad22-d938e8d0ae48', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '9c33beb4-b747-441f-ad22-d938e8d0ae48', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '9c33beb4-b747-441f-ad22-d938e8d0ae48', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '6db3aa06-03b3-4913-872e-26ef4740ff09', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '6db3aa06-03b3-4913-872e-26ef4740ff09', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '6db3aa06-03b3-4913-872e-26ef4740ff09', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '6db3aa06-03b3-4913-872e-26ef4740ff09', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'dee1677f-60a8-4d89-8c03-d680d16b1d07', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'dee1677f-60a8-4d89-8c03-d680d16b1d07', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'dee1677f-60a8-4d89-8c03-d680d16b1d07', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': 'dee1677f-60a8-4d89-8c03-d680d16b1d07', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '937e5f72-30d1-4f93-ac90-69360db18458', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '937e5f72-30d1-4f93-ac90-69360db18458', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '937e5f72-30d1-4f93-ac90-69360db18458', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '937e5f72-30d1-4f93-ac90-69360db18458', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '66eeccd8-4c1b-4bd8-ba30-5a4f379fdebc', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '66eeccd8-4c1b-4bd8-ba30-5a4f379fdebc', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '66eeccd8-4c1b-4bd8-ba30-5a4f379fdebc', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '66eeccd8-4c1b-4bd8-ba30-5a4f379fdebc', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '0cf918d6-53b8-4cb9-b1fa-6626bcf3fb1f', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '0cf918d6-53b8-4cb9-b1fa-6626bcf3fb1f', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '0cf918d6-53b8-4cb9-b1fa-6626bcf3fb1f', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '0cf918d6-53b8-4cb9-b1fa-6626bcf3fb1f', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'f0464b13-7686-401e-a853-f005f66599b9', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'f0464b13-7686-401e-a853-f005f66599b9', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'f0464b13-7686-401e-a853-f005f66599b9', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': 'f0464b13-7686-401e-a853-f005f66599b9', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': 'f0464b13-7686-401e-a853-f005f66599b9', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '8dd41a67-128f-4868-85fb-058e2458040a', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '8dd41a67-128f-4868-85fb-058e2458040a', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '8dd41a67-128f-4868-85fb-058e2458040a', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '90775086-1580-46c4-b4e8-832c129279a8', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '90775086-1580-46c4-b4e8-832c129279a8', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '90775086-1580-46c4-b4e8-832c129279a8', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '19ac423f-0988-46d5-a417-7382886ba803', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '19ac423f-0988-46d5-a417-7382886ba803', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '19ac423f-0988-46d5-a417-7382886ba803', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '19ac423f-0988-46d5-a417-7382886ba803', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '8f1e748d-a94f-4a4f-81c6-f5e38b1da21c', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '8f1e748d-a94f-4a4f-81c6-f5e38b1da21c', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '8f1e748d-a94f-4a4f-81c6-f5e38b1da21c', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '8f1e748d-a94f-4a4f-81c6-f5e38b1da21c', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'ae292e25-6513-4d6d-b7f3-7f91c4982990', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'ae292e25-6513-4d6d-b7f3-7f91c4982990', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'ae292e25-6513-4d6d-b7f3-7f91c4982990', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '2ae1cebd-24df-4f28-a959-b19e273ca83c', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '2ae1cebd-24df-4f28-a959-b19e273ca83c', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '2ae1cebd-24df-4f28-a959-b19e273ca83c', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '2ae1cebd-24df-4f28-a959-b19e273ca83c', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'b040030f-2987-49b2-a1a0-89ffcb1baf96', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'b040030f-2987-49b2-a1a0-89ffcb1baf96', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'b040030f-2987-49b2-a1a0-89ffcb1baf96', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': 'b040030f-2987-49b2-a1a0-89ffcb1baf96', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '5774bbad-0836-4142-a571-898a4706bfc7', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '5774bbad-0836-4142-a571-898a4706bfc7', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '5774bbad-0836-4142-a571-898a4706bfc7', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '5774bbad-0836-4142-a571-898a4706bfc7', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '7c3739a2-74e1-401f-80b6-678244503584', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '7c3739a2-74e1-401f-80b6-678244503584', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '7c3739a2-74e1-401f-80b6-678244503584', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '7c3739a2-74e1-401f-80b6-678244503584', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '5b1bf37a-82d5-4aa1-8bf7-4da34314fea5', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '5b1bf37a-82d5-4aa1-8bf7-4da34314fea5', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '5b1bf37a-82d5-4aa1-8bf7-4da34314fea5', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'eea7bae8-33a5-4b56-b239-73cbcd2d07d0', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'eea7bae8-33a5-4b56-b239-73cbcd2d07d0', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'eea7bae8-33a5-4b56-b239-73cbcd2d07d0', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'ad9dcc30-c425-4b42-babc-e33ab163ea32', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'ad9dcc30-c425-4b42-babc-e33ab163ea32', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'ad9dcc30-c425-4b42-babc-e33ab163ea32', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '052876a3-931d-45d3-b2f5-87fd15f653b4', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '052876a3-931d-45d3-b2f5-87fd15f653b4', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '52622aec-d6ab-49a8-ba5f-6e38ae38df43', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '52622aec-d6ab-49a8-ba5f-6e38ae38df43', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '52622aec-d6ab-49a8-ba5f-6e38ae38df43', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '881cc63c-2bf9-4a3b-b710-854a4f5f9b74', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '881cc63c-2bf9-4a3b-b710-854a4f5f9b74', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '881cc63c-2bf9-4a3b-b710-854a4f5f9b74', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '6a04c641-5375-4608-99c5-ff6a2b61da32', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '6a04c641-5375-4608-99c5-ff6a2b61da32', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '6a04c641-5375-4608-99c5-ff6a2b61da32', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '997326fe-f8a2-42c0-947b-af6cd841c92d', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '997326fe-f8a2-42c0-947b-af6cd841c92d', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '997326fe-f8a2-42c0-947b-af6cd841c92d', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '997326fe-f8a2-42c0-947b-af6cd841c92d', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '997326fe-f8a2-42c0-947b-af6cd841c92d', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '5404bfe5-a0c4-40b5-b6bd-3da3a947aed7', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '5404bfe5-a0c4-40b5-b6bd-3da3a947aed7', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '5404bfe5-a0c4-40b5-b6bd-3da3a947aed7', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '5404bfe5-a0c4-40b5-b6bd-3da3a947aed7', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '5404bfe5-a0c4-40b5-b6bd-3da3a947aed7', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '3fb4951e-e42c-4e73-8e09-2372614ab5b5', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '3fb4951e-e42c-4e73-8e09-2372614ab5b5', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '3fb4951e-e42c-4e73-8e09-2372614ab5b5', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'cd54476a-aa75-444f-8566-6eb2cc225070', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'cd54476a-aa75-444f-8566-6eb2cc225070', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': 'cd54476a-aa75-444f-8566-6eb2cc225070', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '39eefd24-ef52-4536-a84e-fb50866569de', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '39eefd24-ef52-4536-a84e-fb50866569de', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '39eefd24-ef52-4536-a84e-fb50866569de', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '39eefd24-ef52-4536-a84e-fb50866569de', 'scope': 'B'},
        {'role_id': '8aeb2be9-7abc-4e2a-8520-ec41602c0e41', 'permission_id': '39eefd24-ef52-4536-a84e-fb50866569de', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '39a52e01-658b-4c70-b1f2-56388108c3fb', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '39a52e01-658b-4c70-b1f2-56388108c3fb', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '39a52e01-658b-4c70-b1f2-56388108c3fb', 'scope': 'B'},
        {'role_id': 'c8a5ecf5-4e2d-46df-a39d-9d6fd2ee7c80', 'permission_id': '39a52e01-658b-4c70-b1f2-56388108c3fb', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '3217ca0d-468d-4847-be27-600d29e9b9b7', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '3217ca0d-468d-4847-be27-600d29e9b9b7', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': 'dd1c7464-2b52-4b7e-b747-1b69e1c728b1', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': 'dd1c7464-2b52-4b7e-b747-1b69e1c728b1', 'scope': 'F'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '8416a38d-adcf-4359-876e-6a5b84608186', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '8416a38d-adcf-4359-876e-6a5b84608186', 'scope': 'F'},
        {'role_id': 'bf81d3f8-e8d5-423f-b1f5-b760df60ba4e', 'permission_id': '8416a38d-adcf-4359-876e-6a5b84608186', 'scope': 'B'},
        {'role_id': '78aa029b-5b4c-4567-9151-c0e7a557aa60', 'permission_id': '3efb0248-9b2d-4cca-8c46-dc2aec85f073', 'scope': 'F'},
        {'role_id': 'e02a98c2-cecf-4e91-9ba0-a3a0959fda5f', 'permission_id': '3efb0248-9b2d-4cca-8c46-dc2aec85f073', 'scope': 'R'},
]

PLANT_CATEGORIES = [
        {'id': '06c1e227-6462-449e-b33c-6983e3597989', 'code': 'houseplant', 'name': 'Houseplant', 'description': 'Indoor foliage and flowering plants'},
        {'id': 'ecb5c3c5-0c92-4e78-aa11-e1050591ccd2', 'code': 'succulent_cactus', 'name': 'Succulent & Cactus', 'description': 'Drought-tolerant succulents and cacti'},
        {'id': 'f7370c5e-56ca-4c76-90d1-242fff777092', 'code': 'shrub', 'name': 'Shrub', 'description': 'Woody perennial shrubs'},
        {'id': 'b90529f5-0449-4627-8968-5711d397f8db', 'code': 'tree', 'name': 'Tree', 'description': 'Ornamental and shade trees'},
        {'id': '95d77aa8-1941-4b80-97d7-22ef15f0e9f5', 'code': 'annual_flower', 'name': 'Annual Flower', 'description': 'Single-season flowering annuals'},
        {'id': 'c7552f8d-01e2-425a-8f9b-dac99c2061ba', 'code': 'perennial_flower', 'name': 'Perennial Flower', 'description': 'Multi-season flowering perennials'},
        {'id': 'ce511a00-4aa1-4369-aa2c-e5293adf9558', 'code': 'herb', 'name': 'Herb', 'description': 'Culinary and medicinal herbs'},
        {'id': '88bb2be3-0434-4a7d-bb3f-d62b04c5f9ac', 'code': 'vegetable_start', 'name': 'Vegetable Start', 'description': 'Vegetable seedlings/starts'},
        {'id': '12de2437-b49c-4faa-a405-781155734b18', 'code': 'ornamental_grass', 'name': 'Ornamental Grass', 'description': 'Decorative grasses'},
        {'id': '19f5633b-1237-4622-92f5-858fcaf00e2c', 'code': 'vine_climber', 'name': 'Vine / Climber', 'description': 'Climbing and trailing plants'},
        {'id': '0299e424-b980-4145-9f1d-d2d11012fb65', 'code': 'fern', 'name': 'Fern', 'description': 'Ferns and other foliage plants'},
        {'id': 'f050651c-7687-4205-b5b6-aa46dd01e62b', 'code': 'bulb', 'name': 'Bulb', 'description': 'Bulbs, corms, and tubers'},
]

UNITS = [
        {'id': 'eec3d4bd-ab0c-4231-a442-0a7ac506c16d', 'code': 'each', 'name': 'Each', 'unit_type': 'count'},
        {'id': '62117edb-47f0-4464-b62c-2710a9c7a98d', 'code': 'flat', 'name': 'Flat', 'unit_type': 'count'},
        {'id': 'd63c7d06-7dd8-4190-aa8a-fac5d35bcfac', 'code': 'pot', 'name': 'Pot', 'unit_type': 'count'},
        {'id': '832b0891-542d-4a64-bb89-fc4f94e74cdb', 'code': 'tray', 'name': 'Tray', 'unit_type': 'count'},
        {'id': 'd332849f-74f7-4de5-b232-12978e9599d3', 'code': 'bundle', 'name': 'Bundle', 'unit_type': 'count'},
        {'id': '9c554cf3-5760-4ddb-bbf2-0e74a70f3742', 'code': 'box', 'name': 'Box', 'unit_type': 'count'},
        {'id': '4543aa89-0c22-4256-9294-d33384953897', 'code': 'kg', 'name': 'Kilogram', 'unit_type': 'weight'},
        {'id': 'f5e9fdd4-66f3-40f9-830e-7476c31361dc', 'code': 'g', 'name': 'Gram', 'unit_type': 'weight'},
        {'id': 'a10a6d82-e85d-4113-a473-d064a9d254ad', 'code': 'lb', 'name': 'Pound', 'unit_type': 'weight'},
        {'id': 'a541419c-1af8-4bb8-91d8-169a36df916f', 'code': 'liter', 'name': 'Liter', 'unit_type': 'volume'},
        {'id': '3c1cbc75-c048-4def-aa4c-e73b25552c52', 'code': 'gallon', 'name': 'Gallon', 'unit_type': 'volume'},
        {'id': 'a4910a25-047f-4641-b8be-5d1e21091af7', 'code': 'bag', 'name': 'Bag', 'unit_type': 'count'},
]


def upgrade() -> None:
    op.bulk_insert(roles_table, ROLES)
    op.bulk_insert(permissions_table, PERMISSIONS)
    op.bulk_insert(role_permissions_table, ROLE_PERMISSIONS)
    op.bulk_insert(plant_categories_table, PLANT_CATEGORIES)
    op.bulk_insert(units_table, UNITS)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions")
    op.execute("DELETE FROM permissions")
    op.execute("DELETE FROM roles WHERE is_system_role = true")
    op.execute("DELETE FROM plant_categories")
    op.execute("DELETE FROM units")
