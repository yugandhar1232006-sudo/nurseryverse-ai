"""Initial schema — all 50 tables, ENUM types, constraints, and indexes.

Revision ID: 0001
Revises:
Create Date: 2026-08-05

Generated mechanically from app.models (Base.metadata) via Alembic's own
autogenerate rendering (alembic.autogenerate.render.render_op_text against
each table in Base.metadata.sorted_tables — a topologically FK-safe order),
not hand-typed — this guarantees the migration matches the ORM models
exactly. See scripts/generate_initial_migration.py for the generator.

Table count moved from 49 to 50 (Production Database Readiness Review,
docs/architecture/17-production-database-readiness-review.md §5): added
`knowledge_base_chunks` to give the AI Assistant's RAG grounding path an
actual pgvector-backed table, since the `vector` extension was enabled
from the start but nothing used it.

Every standalone `Index(...)` declared in a model's `__table_args__` (40
across the schema) is rendered here as an explicit `op.create_index(...)`
call immediately after its table, generated the same mechanical way as
the tables themselves — the earlier generator only captured
`CreateTableOp`, which does not include standalone indexes; see the
readiness review §1/§2 and scripts/generate_initial_migration.py for the
fix.

Extensions (pgcrypto for gen_random_uuid(), pg_trgm for fuzzy search,
pgvector for AI Assistant RAG embeddings) are created first, since column
defaults and indexes depend on them
(docs/architecture/05-database-architecture.md §5, §9;
docs/architecture/06-ai-architecture.md §8).
"""
from collections.abc import Sequence

import pgvector.sqlalchemy  # noqa: F401 -- referenced via its full dotted path below (mechanical render)
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # --- Extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- Tables + standalone indexes (FK-dependency-safe order) ---
    op.create_table('nurseries',
sa.Column('name', sa.String(length=255), nullable=False),
sa.Column('logo_url', sa.String(length=500), nullable=True),
sa.Column('contact_email', sa.String(length=320), nullable=False),
sa.Column('contact_phone', sa.String(length=50), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.PrimaryKeyConstraint('id', name=op.f('pk_nurseries'))
)

    op.create_table('permissions',
sa.Column('code', sa.String(length=100), nullable=False),
sa.Column('module', sa.String(length=50), nullable=False),
sa.Column('action', sa.String(length=50), nullable=False),
sa.Column('description', sa.String(length=255), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.PrimaryKeyConstraint('id', name=op.f('pk_permissions')),
sa.UniqueConstraint('code', name='uq_permissions_code')
)

    op.create_table('plant_categories',
sa.Column('code', sa.String(length=50), nullable=False),
sa.Column('name', sa.String(length=100), nullable=False),
sa.Column('description', sa.String(length=500), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.PrimaryKeyConstraint('id', name=op.f('pk_plant_categories')),
sa.UniqueConstraint('code', name='uq_plant_categories_code')
)

    op.create_table('units',
sa.Column('code', sa.String(length=20), nullable=False),
sa.Column('name', sa.String(length=50), nullable=False),
sa.Column('unit_type', sa.String(length=20), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.PrimaryKeyConstraint('id', name=op.f('pk_units')),
sa.UniqueConstraint('code', name='uq_units_code')
)

    op.create_table('users',
sa.Column('email', sa.String(length=320), nullable=False),
sa.Column('password_hash', sa.String(length=255), nullable=False),
sa.Column('full_name', sa.String(length=255), nullable=False),
sa.Column('is_active', sa.Boolean(), nullable=False),
sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
sa.UniqueConstraint('email', name='uq_users_email')
)

    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)

    op.create_table('ai_assistant_conversations',
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('user_id', sa.UUID(), nullable=False),
sa.Column('title', sa.String(length=255), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_ai_assistant_conversations_nursery_id_nurseries'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ai_assistant_conversations_user_id_users'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_assistant_conversations'))
)

    op.create_index('ix_ai_assistant_conversations_user_id', 'ai_assistant_conversations', ['user_id'], unique=False)

    op.create_table('attachments',
sa.Column('entity_type', sa.String(length=50), nullable=False),
sa.Column('entity_id', sa.UUID(), nullable=False),
sa.Column('file_name', sa.String(length=255), nullable=False),
sa.Column('file_url', sa.String(length=1000), nullable=False),
sa.Column('content_type', sa.String(length=100), nullable=True),
sa.Column('file_size_bytes', sa.Integer(), nullable=True),
sa.Column('uploaded_by_user_id', sa.UUID(), nullable=False),
sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_attachments_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], name=op.f('fk_attachments_uploaded_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_attachments'))
)

    op.create_index('ix_attachments_entity_type_entity_id', 'attachments', ['entity_type', 'entity_id'], unique=False)

    op.create_table('audit_logs',
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('actor_user_id', sa.UUID(), nullable=True),
sa.Column('action', sa.String(length=100), nullable=False),
sa.Column('entity_type', sa.String(length=100), nullable=False),
sa.Column('entity_id', sa.UUID(), nullable=True),
sa.Column('diff', sa.JSON(), nullable=True),
sa.Column('request_id', sa.String(length=64), nullable=True),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name=op.f('fk_audit_logs_actor_user_id_users'), ondelete='SET NULL'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_audit_logs_nursery_id_nurseries'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
)

    op.create_index('ix_audit_logs_actor_id', 'audit_logs', ['actor_user_id'], unique=False)

    op.create_index('ix_audit_logs_nursery_created_at', 'audit_logs', ['nursery_id', 'created_at'], unique=False)

    op.create_table('branches',
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('name', sa.String(length=255), nullable=False),
sa.Column('address_line1', sa.String(length=255), nullable=False),
sa.Column('address_line2', sa.String(length=255), nullable=True),
sa.Column('city', sa.String(length=120), nullable=False),
sa.Column('region', sa.String(length=120), nullable=True),
sa.Column('postal_code', sa.String(length=20), nullable=True),
sa.Column('country', sa.String(length=2), nullable=False),
sa.Column('timezone', sa.String(length=64), nullable=False),
sa.Column('status', sa.Enum('ACTIVE', 'INACTIVE', name='branch_status'), nullable=False),
sa.Column('default_low_stock_threshold', sa.Integer(), nullable=False),
sa.Column('default_watering_overdue_hours', sa.Integer(), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_branches_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_branches')),
sa.UniqueConstraint('nursery_id', 'name', name='uq_branches_nursery_name')
)

    op.create_table('employees',
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('user_id', sa.UUID(), nullable=False),
sa.Column('status', sa.Enum('ACTIVE', 'INVITED', 'DEACTIVATED', name='employee_status'), nullable=False),
sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_employees_nursery_id_nurseries'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_employees_user_id_users'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_employees')),
sa.UniqueConstraint('nursery_id', 'user_id', name='uq_employees_nursery_user')
)

    op.create_table('knowledge_base_chunks',
sa.Column('nursery_id', sa.UUID(), nullable=True),
sa.Column('source_type', sa.String(length=30), nullable=False),
sa.Column('source_ref', sa.String(length=255), nullable=True),
sa.Column('title', sa.String(length=255), nullable=True),
sa.Column('content', sa.Text(), nullable=False),
sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=False),
sa.Column('embedding_model_version', sa.String(length=50), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_knowledge_base_chunks_nursery_id_nurseries'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_knowledge_base_chunks'))
)

    op.create_index('ix_knowledge_base_chunks_embedding_hnsw', 'knowledge_base_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})

    op.create_index('ix_knowledge_base_chunks_nursery_source', 'knowledge_base_chunks', ['nursery_id', 'source_type'], unique=False)

    op.create_table('notification_preferences',
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('user_id', sa.UUID(), nullable=False),
sa.Column('category', sa.Enum('DISEASE_CONFIRMED', 'WATERING_OVERDUE', 'LOW_STOCK', 'AI_PREDICTION_READY', 'INVOICE_OVERDUE', 'EMPLOYEE_INVITE', 'PLANT_TRANSFERRED', 'PURCHASE_ORDER_RECEIVED', name='notification_category'), nullable=False),
sa.Column('channel', sa.Enum('IN_APP', 'EMAIL', 'SMS', name='notification_channel'), nullable=False),
sa.Column('enabled', sa.Boolean(), nullable=False),
sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notification_preferences_user_id_users'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_preferences')),
sa.UniqueConstraint('user_id', 'category', 'channel', name='uq_notification_preferences_user_cat_channel')
)

    op.create_table('notifications',
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('recipient_user_id', sa.UUID(), nullable=False),
sa.Column('category', sa.Enum('DISEASE_CONFIRMED', 'WATERING_OVERDUE', 'LOW_STOCK', 'AI_PREDICTION_READY', 'INVOICE_OVERDUE', 'EMPLOYEE_INVITE', 'PLANT_TRANSFERRED', 'PURCHASE_ORDER_RECEIVED', name='notification_category'), nullable=False),
sa.Column('message', sa.String(length=500), nullable=False),
sa.Column('deep_link', sa.String(length=500), nullable=True),
sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_notifications_nursery_id_nurseries'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], name=op.f('fk_notifications_recipient_user_id_users'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
)

    op.create_index('ix_notifications_recipient_read', 'notifications', ['recipient_user_id', 'read_at'], unique=False)

    op.create_table('org_settings',
sa.Column('sms_enabled', sa.Boolean(), nullable=False),
sa.Column('sms_provider_config', sa.JSON(), nullable=True),
sa.Column('email_sender_identity', sa.String(length=255), nullable=True),
sa.Column('branding_primary_color', sa.String(length=7), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_org_settings_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_org_settings')),
sa.UniqueConstraint('nursery_id', name='uq_org_settings_nursery')
)

    op.create_table('roles',
sa.Column('nursery_id', sa.UUID(), nullable=True),
sa.Column('code', sa.String(length=50), nullable=False),
sa.Column('name', sa.String(length=100), nullable=False),
sa.Column('is_system_role', sa.Boolean(), nullable=False),
sa.Column('permission_ceiling_role_code', sa.String(length=50), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_roles_nursery_id_nurseries'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
sa.UniqueConstraint('nursery_id', 'code', name='uq_roles_nursery_code')
)

    op.create_table('species',
sa.Column('category_id', sa.UUID(), nullable=False),
sa.Column('common_name', sa.String(length=255), nullable=False),
sa.Column('botanical_name', sa.String(length=255), nullable=False),
sa.Column('light_requirement', sa.String(length=50), nullable=True),
sa.Column('water_baseline_ml_per_week', sa.Integer(), nullable=True),
sa.Column('soil_type', sa.String(length=100), nullable=True),
sa.Column('temperature_min_celsius', sa.Numeric(precision=5, scale=2), nullable=True),
sa.Column('temperature_max_celsius', sa.Numeric(precision=5, scale=2), nullable=True),
sa.Column('growth_curve_baseline', sa.JSON(), nullable=True),
sa.Column('disease_susceptibility', sa.JSON(), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['category_id'], ['plant_categories.id'], name=op.f('fk_species_category_id_plant_categories'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_species_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_species')),
sa.UniqueConstraint('nursery_id', 'botanical_name', name='uq_species_nursery_botanical')
)

    op.create_table('subscriptions',
sa.Column('plan', sa.Enum('STARTER', 'GROWTH', 'ENTERPRISE', name='subscription_plan'), nullable=False),
sa.Column('status', sa.Enum('ACTIVE', 'PAST_DUE', 'CANCELED', name='subscription_status'), nullable=False),
sa.Column('branch_limit', sa.Integer(), nullable=False),
sa.Column('seat_limit', sa.Integer(), nullable=True),
sa.Column('ai_credit_monthly_limit', sa.Integer(), nullable=True),
sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_subscriptions_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_subscriptions')),
sa.UniqueConstraint('nursery_id', name='uq_subscriptions_nursery')
)

    op.create_table('usage_counters',
sa.Column('metric', sa.String(length=50), nullable=False),
sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
sa.Column('count', sa.Integer(), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_usage_counters_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_usage_counters')),
sa.UniqueConstraint('nursery_id', 'metric', 'period_start', name='uq_usage_counters_nursery_metric_period')
)

    op.create_table('ai_assistant_messages',
sa.Column('conversation_id', sa.UUID(), nullable=False),
sa.Column('role', sa.String(length=20), nullable=False),
sa.Column('content', sa.Text(), nullable=False),
sa.Column('proposed_action', sa.JSON(), nullable=True),
sa.Column('action_status', sa.String(length=30), nullable=True),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['conversation_id'], ['ai_assistant_conversations.id'], name=op.f('fk_ai_assistant_messages_conversation_id_ai_assistant_conversations'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_assistant_messages'))
)

    op.create_index('ix_ai_assistant_messages_conversation_id', 'ai_assistant_messages', ['conversation_id'], unique=False)

    op.create_table('customers',
sa.Column('name', sa.String(length=255), nullable=False),
sa.Column('email', sa.String(length=320), nullable=True),
sa.Column('phone', sa.String(length=50), nullable=True),
sa.Column('customer_type', sa.Enum('RETAIL', 'WHOLESALE', name='customer_type'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_customers_branch_id_branches'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_customers_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_customers'))
)

    op.create_index('ix_customers_nursery_name', 'customers', ['nursery_id', 'name'], unique=False)

    op.create_table('inventory',
sa.Column('species_id', sa.UUID(), nullable=True),
sa.Column('category_id', sa.UUID(), nullable=False),
sa.Column('unit_id', sa.UUID(), nullable=False),
sa.Column('name', sa.String(length=255), nullable=False),
sa.Column('quantity', sa.Integer(), nullable=False),
sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=True),
sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=True),
sa.Column('low_stock_threshold', sa.Integer(), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.CheckConstraint('quantity >= 0', name=op.f('ck_inventory_quantity_non_negative')),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_inventory_branch_id_branches'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['category_id'], ['plant_categories.id'], name=op.f('fk_inventory_category_id_plant_categories'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_inventory_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['species_id'], ['species.id'], name=op.f('fk_inventory_species_id_species'), ondelete='SET NULL'),
sa.ForeignKeyConstraint(['unit_id'], ['units.id'], name=op.f('fk_inventory_unit_id_units'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory')),
sa.UniqueConstraint('branch_id', 'name', name='uq_inventory_branch_name')
)

    op.create_index('ix_inventory_nursery_branch', 'inventory', ['nursery_id', 'branch_id'], unique=False)

    op.create_table('invites',
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('invited_by_user_id', sa.UUID(), nullable=False),
sa.Column('email', sa.String(length=320), nullable=False),
sa.Column('role_id', sa.UUID(), nullable=False),
sa.Column('token', sa.String(length=128), nullable=False),
sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], name=op.f('fk_invites_invited_by_user_id_users')),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_invites_nursery_id_nurseries'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_invites_role_id_roles')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_invites')),
sa.UniqueConstraint('token', name='uq_invites_token')
)

    op.create_table('plant_varieties',
sa.Column('species_id', sa.UUID(), nullable=False),
sa.Column('name', sa.String(length=255), nullable=False),
sa.Column('description', sa.String(length=500), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_plant_varieties_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['species_id'], ['species.id'], name=op.f('fk_plant_varieties_species_id_species'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_plant_varieties')),
sa.UniqueConstraint('species_id', 'name', name='uq_plant_varieties_species_name')
)

    op.create_table('reports',
sa.Column('branch_id', sa.UUID(), nullable=True),
sa.Column('report_type', sa.Enum('INVENTORY', 'SALES', 'REVENUE', 'PLANT_LOSS', 'AI_SUMMARY', 'PLANT_PASSPORT', name='report_type'), nullable=False),
sa.Column('format', sa.Enum('PDF', 'EXCEL', 'CSV', name='report_format'), nullable=False),
sa.Column('status', sa.Enum('PENDING', 'COMPLETE', 'FAILED', name='report_status'), nullable=False),
sa.Column('filters', sa.JSON(), nullable=True),
sa.Column('file_url', sa.String(length=1000), nullable=True),
sa.Column('requested_by_user_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_reports_branch_id_branches'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_reports_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], name=op.f('fk_reports_requested_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_reports'))
)

    op.create_index('ix_reports_nursery_created_at', 'reports', ['nursery_id', 'created_at'], unique=False)

    op.create_table('role_assignments',
sa.Column('user_id', sa.UUID(), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('role_id', sa.UUID(), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_role_assignments_nursery_id_nurseries'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_role_assignments_role_id_roles'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_role_assignments_user_id_users'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_role_assignments')),
sa.UniqueConstraint('user_id', 'nursery_id', name='uq_role_assignments_user_nursery')
)

    op.create_table('role_permissions',
sa.Column('role_id', sa.UUID(), nullable=False),
sa.Column('permission_id', sa.UUID(), nullable=False),
sa.Column('scope', sa.String(length=1), nullable=False),
sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], name=op.f('fk_role_permissions_permission_id_permissions'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_role_permissions_role_id_roles'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('role_id', 'permission_id', name=op.f('pk_role_permissions'))
)

    op.create_table('suppliers',
sa.Column('name', sa.String(length=255), nullable=False),
sa.Column('contact_name', sa.String(length=255), nullable=True),
sa.Column('email', sa.String(length=320), nullable=True),
sa.Column('phone', sa.String(length=50), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_suppliers_branch_id_branches'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_suppliers_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_suppliers')),
sa.UniqueConstraint('branch_id', 'name', name='uq_suppliers_branch_name')
)

    op.create_table('invoices',
sa.Column('customer_id', sa.UUID(), nullable=False),
sa.Column('invoice_number', sa.String(length=50), nullable=False),
sa.Column('status', sa.Enum('DRAFT', 'SENT', 'PAID', 'OVERDUE', 'VOID', name='invoice_status'), nullable=False),
sa.Column('terms', sa.String(length=50), nullable=True),
sa.Column('po_reference', sa.String(length=100), nullable=True),
sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('void_reason', sa.Text(), nullable=True),
sa.Column('pdf_url', sa.String(length=1000), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_invoices_branch_id_branches'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('fk_invoices_customer_id_customers'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_invoices_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_invoices')),
sa.UniqueConstraint('nursery_id', 'invoice_number', name='uq_invoices_nursery_number')
)

    op.create_index('ix_invoices_branch_status', 'invoices', ['branch_id', 'status'], unique=False)

    op.create_table('plants',
sa.Column('species_id', sa.UUID(), nullable=False),
sa.Column('variety_id', sa.UUID(), nullable=True),
sa.Column('common_label', sa.String(length=255), nullable=True),
sa.Column('zone', sa.String(length=100), nullable=True),
sa.Column('status', sa.Enum('IN_PRODUCTION', 'READY_FOR_SALE', 'UNDER_TREATMENT', 'SOLD', 'DECEASED', name='plant_status'), nullable=False),
sa.Column('qr_code_token', sa.String(length=64), nullable=False),
sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=True),
sa.Column('planted_at', sa.DateTime(timezone=True), nullable=False),
sa.Column('sold_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('deceased_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('deceased_reason', sa.Text(), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_plants_branch_id_branches'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_plants_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['species_id'], ['species.id'], name=op.f('fk_plants_species_id_species'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['variety_id'], ['plant_varieties.id'], name=op.f('fk_plants_variety_id_plant_varieties'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_plants')),
sa.UniqueConstraint('qr_code_token', name='uq_plants_qr_code_token')
)

    op.create_index('ix_plants_nursery_branch', 'plants', ['nursery_id', 'branch_id'], unique=False)

    op.create_index('ix_plants_species_id', 'plants', ['species_id'], unique=False)

    op.create_index('ix_plants_status', 'plants', ['status'], unique=False)

    op.create_table('purchase_orders',
sa.Column('supplier_id', sa.UUID(), nullable=False),
sa.Column('po_number', sa.String(length=50), nullable=False),
sa.Column('status', sa.Enum('DRAFT', 'SENT', 'PARTIALLY_RECEIVED', 'RECEIVED', name='purchase_order_status'), nullable=False),
sa.Column('total_cost', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_purchase_orders_branch_id_branches'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_purchase_orders_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], name=op.f('fk_purchase_orders_supplier_id_suppliers'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_purchase_orders')),
sa.UniqueConstraint('nursery_id', 'po_number', name='uq_purchase_orders_nursery_number')
)

    op.create_index('ix_purchase_orders_branch_status', 'purchase_orders', ['branch_id', 'status'], unique=False)

    op.create_table('role_assignment_branch_scopes',
sa.Column('role_assignment_id', sa.UUID(), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_role_assignment_branch_scopes_branch_id_branches'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['role_assignment_id'], ['role_assignments.id'], name=op.f('fk_role_assignment_branch_scopes_role_assignment_id_role_assignments'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('role_assignment_id', 'branch_id', name=op.f('pk_role_assignment_branch_scopes'))
)

    op.create_table('sales',
sa.Column('customer_id', sa.UUID(), nullable=True),
sa.Column('status', sa.Enum('COMPLETED', 'VOIDED', name='sale_status'), nullable=False),
sa.Column('subtotal_amount', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('discount_amount', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('payment_method', sa.String(length=50), nullable=True),
sa.Column('sold_by_user_id', sa.UUID(), nullable=False),
sa.Column('void_reason', sa.Text(), nullable=True),
sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('idempotency_key', sa.String(length=128), nullable=True),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.CheckConstraint('total_amount >= 0', name=op.f('ck_sales_total_amount_non_negative')),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_sales_branch_id_branches'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], name=op.f('fk_sales_customer_id_customers'), ondelete='SET NULL'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_sales_nursery_id_nurseries'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['sold_by_user_id'], ['users.id'], name=op.f('fk_sales_sold_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_sales')),
sa.UniqueConstraint('branch_id', 'idempotency_key', name='uq_sales_branch_idempotency_key')
)

    op.create_index('ix_sales_branch_created_at', 'sales', ['branch_id', 'created_at'], unique=False)

    op.create_table('ai_predictions',
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=True),
sa.Column('plant_id', sa.UUID(), nullable=True),
sa.Column('prediction_type', sa.Enum('DISEASE_DETECTION', 'GROWTH_PREDICTION', 'SURVIVAL_PREDICTION', 'WATER_RECOMMENDATION', 'REVENUE_FORECAST', name='ai_prediction_type'), nullable=False),
sa.Column('model_version', sa.String(length=50), nullable=False),
sa.Column('result', sa.JSON(), nullable=False),
sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=True),
sa.Column('explanation', sa.Text(), nullable=True),
sa.Column('inputs_summary', sa.JSON(), nullable=True),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_ai_predictions_branch_id_branches'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_ai_predictions_nursery_id_nurseries'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_ai_predictions_plant_id_plants'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_predictions'))
)

    op.create_index('ix_ai_predictions_nursery_branch', 'ai_predictions', ['nursery_id', 'branch_id'], unique=False)

    op.create_index('ix_ai_predictions_plant_type_created', 'ai_predictions', ['plant_id', 'prediction_type', 'created_at'], unique=False)

    op.create_table('environmental_readings',
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('plant_id', sa.UUID(), nullable=True),
sa.Column('zone', sa.String(length=100), nullable=True),
sa.Column('temperature_celsius', sa.Numeric(precision=5, scale=2), nullable=True),
sa.Column('humidity_percent', sa.Numeric(precision=5, scale=2), nullable=True),
sa.Column('soil_moisture_percent', sa.Numeric(precision=5, scale=2), nullable=True),
sa.Column('light_lux', sa.Numeric(precision=10, scale=2), nullable=True),
sa.Column('source', sa.String(length=20), nullable=False),
sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_environmental_readings_branch_id_branches'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_environmental_readings_plant_id_plants'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_environmental_readings'))
)

    op.create_index('ix_environmental_readings_branch_recorded_at', 'environmental_readings', ['branch_id', 'recorded_at'], unique=False)

    op.create_index('ix_environmental_readings_plant_id', 'environmental_readings', ['plant_id'], unique=False)

    op.create_table('fertilizer_logs',
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('plant_id', sa.UUID(), nullable=True),
sa.Column('zone', sa.String(length=100), nullable=True),
sa.Column('product_name', sa.String(length=255), nullable=False),
sa.Column('quantity_ml', sa.Numeric(precision=8, scale=2), nullable=True),
sa.Column('npk_ratio', sa.String(length=20), nullable=True),
sa.Column('notes', sa.Text(), nullable=True),
sa.Column('recorded_by_user_id', sa.UUID(), nullable=False),
sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_fertilizer_logs_branch_id_branches'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_fertilizer_logs_plant_id_plants'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id'], name=op.f('fk_fertilizer_logs_recorded_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_fertilizer_logs'))
)

    op.create_index('ix_fertilizer_logs_branch_zone', 'fertilizer_logs', ['branch_id', 'zone'], unique=False)

    op.create_index('ix_fertilizer_logs_plant_id_recorded_at', 'fertilizer_logs', ['plant_id', 'recorded_at'], unique=False)

    op.create_table('growth_timeline',
sa.Column('plant_id', sa.UUID(), nullable=False),
sa.Column('height_cm', sa.Numeric(precision=6, scale=2), nullable=True),
sa.Column('spread_cm', sa.Numeric(precision=6, scale=2), nullable=True),
sa.Column('growth_stage', sa.String(length=50), nullable=True),
sa.Column('photo_url', sa.String(length=1000), nullable=True),
sa.Column('notes', sa.Text(), nullable=True),
sa.Column('recorded_by_user_id', sa.UUID(), nullable=False),
sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_growth_timeline_plant_id_plants'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id'], name=op.f('fk_growth_timeline_recorded_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_growth_timeline'))
)

    op.create_index('ix_growth_timeline_plant_id_recorded_at', 'growth_timeline', ['plant_id', 'recorded_at'], unique=False)

    op.create_table('health_history',
sa.Column('plant_id', sa.UUID(), nullable=False),
sa.Column('status_label', sa.String(length=50), nullable=False),
sa.Column('notes', sa.Text(), nullable=True),
sa.Column('photo_url', sa.String(length=1000), nullable=True),
sa.Column('recorded_by_user_id', sa.UUID(), nullable=False),
sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_health_history_plant_id_plants'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id'], name=op.f('fk_health_history_recorded_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_health_history'))
)

    op.create_index('ix_health_history_plant_id_recorded_at', 'health_history', ['plant_id', 'recorded_at'], unique=False)

    op.create_table('inventory_adjustments',
sa.Column('inventory_id', sa.UUID(), nullable=False),
sa.Column('quantity_delta', sa.Integer(), nullable=False),
sa.Column('quantity_after', sa.Integer(), nullable=False),
sa.Column('reason', sa.Enum('DAMAGE', 'CORRECTION', 'INTERNAL_USE', 'PURCHASE_ORDER_RECEIPT', 'SALE', 'OTHER', name='inventory_adjustment_reason'), nullable=False),
sa.Column('reference_sale_id', sa.UUID(), nullable=True),
sa.Column('reference_purchase_order_id', sa.UUID(), nullable=True),
sa.Column('note', sa.Text(), nullable=True),
sa.Column('adjusted_by_user_id', sa.UUID(), nullable=True),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['adjusted_by_user_id'], ['users.id'], name=op.f('fk_inventory_adjustments_adjusted_by_user_id_users')),
sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], name=op.f('fk_inventory_adjustments_inventory_id_inventory'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['reference_purchase_order_id'], ['purchase_orders.id'], name=op.f('fk_inventory_adjustments_reference_purchase_order_id_purchase_orders'), ondelete='SET NULL'),
sa.ForeignKeyConstraint(['reference_sale_id'], ['sales.id'], name=op.f('fk_inventory_adjustments_reference_sale_id_sales'), ondelete='SET NULL'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory_adjustments'))
)

    op.create_index('ix_inventory_adjustments_inventory_id', 'inventory_adjustments', ['inventory_id'], unique=False)

    op.create_table('invoice_items',
sa.Column('invoice_id', sa.UUID(), nullable=False),
sa.Column('description', sa.String(length=500), nullable=False),
sa.Column('quantity', sa.Integer(), nullable=False),
sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('line_total', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_invoice_items_invoice_id_invoices'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_invoice_items'))
)

    op.create_index('ix_invoice_items_invoice_id', 'invoice_items', ['invoice_id'], unique=False)

    op.create_table('invoice_sales',
sa.Column('invoice_id', sa.UUID(), nullable=False),
sa.Column('sale_id', sa.UUID(), nullable=False),
sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_invoice_sales_invoice_id_invoices'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], name=op.f('fk_invoice_sales_sale_id_sales'), ondelete='RESTRICT'),
sa.PrimaryKeyConstraint('invoice_id', 'sale_id', name=op.f('pk_invoice_sales'))
)

    op.create_table('passports',
sa.Column('plant_id', sa.UUID(), nullable=False),
sa.Column('version', sa.Integer(), nullable=False),
sa.Column('public_token', sa.String(length=128), nullable=False),
sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('content_snapshot', sa.JSON(), nullable=False),
sa.Column('pdf_url', sa.String(length=1000), nullable=True),
sa.Column('generated_by_user_id', sa.UUID(), nullable=False),
sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['generated_by_user_id'], ['users.id'], name=op.f('fk_passports_generated_by_user_id_users')),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_passports_plant_id_plants'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_passports')),
sa.UniqueConstraint('public_token', name='uq_passports_public_token')
)

    op.create_index('ix_passports_plant_id_version', 'passports', ['plant_id', 'version'], unique=False)

    op.create_table('payments',
sa.Column('invoice_id', sa.UUID(), nullable=False),
sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('method', sa.String(length=50), nullable=False),
sa.Column('reference', sa.String(length=100), nullable=True),
sa.Column('received_by_user_id', sa.UUID(), nullable=False),
sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_payments_invoice_id_invoices'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['received_by_user_id'], ['users.id'], name=op.f('fk_payments_received_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_payments'))
)

    op.create_index('ix_payments_invoice_id', 'payments', ['invoice_id'], unique=False)

    op.create_table('plant_images',
sa.Column('plant_id', sa.UUID(), nullable=False),
sa.Column('url', sa.String(length=1000), nullable=False),
sa.Column('thumbnail_url', sa.String(length=1000), nullable=True),
sa.Column('caption', sa.String(length=255), nullable=True),
sa.Column('captured_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('uploaded_by_user_id', sa.UUID(), nullable=True),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_plant_images_plant_id_plants'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], name=op.f('fk_plant_images_uploaded_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_plant_images'))
)

    op.create_index('ix_plant_images_plant_id', 'plant_images', ['plant_id'], unique=False)

    op.create_table('plant_transfers',
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('plant_id', sa.UUID(), nullable=False),
sa.Column('from_branch_id', sa.UUID(), nullable=False),
sa.Column('to_branch_id', sa.UUID(), nullable=False),
sa.Column('note', sa.Text(), nullable=True),
sa.Column('transferred_by_user_id', sa.UUID(), nullable=False),
sa.Column('transferred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['from_branch_id'], ['branches.id'], name=op.f('fk_plant_transfers_from_branch_id_branches'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_plant_transfers_nursery_id_nurseries'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_plant_transfers_plant_id_plants'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['to_branch_id'], ['branches.id'], name=op.f('fk_plant_transfers_to_branch_id_branches'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['transferred_by_user_id'], ['users.id'], name=op.f('fk_plant_transfers_transferred_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_plant_transfers'))
)

    op.create_index('ix_plant_transfers_plant_id', 'plant_transfers', ['plant_id'], unique=False)

    op.create_table('purchase_order_items',
sa.Column('purchase_order_id', sa.UUID(), nullable=False),
sa.Column('inventory_id', sa.UUID(), nullable=False),
sa.Column('ordered_quantity', sa.Integer(), nullable=False),
sa.Column('received_quantity', sa.Integer(), nullable=False),
sa.Column('unit_cost', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.CheckConstraint('received_quantity <= ordered_quantity', name=op.f('ck_purchase_order_items_received_not_exceeding_ordered')),
sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], name=op.f('fk_purchase_order_items_inventory_id_inventory'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], name=op.f('fk_purchase_order_items_purchase_order_id_purchase_orders'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_purchase_order_items'))
)

    op.create_index('ix_purchase_order_items_po_id', 'purchase_order_items', ['purchase_order_id'], unique=False)

    op.create_table('sale_items',
sa.Column('sale_id', sa.UUID(), nullable=False),
sa.Column('plant_id', sa.UUID(), nullable=True),
sa.Column('inventory_id', sa.UUID(), nullable=True),
sa.Column('quantity', sa.Integer(), nullable=False),
sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('line_total', sa.Numeric(precision=10, scale=2), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.CheckConstraint('(plant_id IS NOT NULL AND inventory_id IS NULL) OR (plant_id IS NULL AND inventory_id IS NOT NULL)', name=op.f('ck_sale_items_exactly_one_of_plant_or_inventory')),
sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], name=op.f('fk_sale_items_inventory_id_inventory'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_sale_items_plant_id_plants'), ondelete='RESTRICT'),
sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], name=op.f('fk_sale_items_sale_id_sales'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_sale_items'))
)

    op.create_index('ix_sale_items_sale_id', 'sale_items', ['sale_id'], unique=False)

    op.create_table('watering_logs',
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('plant_id', sa.UUID(), nullable=True),
sa.Column('zone', sa.String(length=100), nullable=True),
sa.Column('volume_ml', sa.Numeric(precision=8, scale=2), nullable=True),
sa.Column('notes', sa.Text(), nullable=True),
sa.Column('recorded_by_user_id', sa.UUID(), nullable=False),
sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_watering_logs_branch_id_branches'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_watering_logs_plant_id_plants'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id'], name=op.f('fk_watering_logs_recorded_by_user_id_users')),
sa.PrimaryKeyConstraint('id', name=op.f('pk_watering_logs'))
)

    op.create_index('ix_watering_logs_branch_zone', 'watering_logs', ['branch_id', 'zone'], unique=False)

    op.create_index('ix_watering_logs_plant_id_recorded_at', 'watering_logs', ['plant_id', 'recorded_at'], unique=False)

    op.create_table('ai_recommendations',
sa.Column('nursery_id', sa.UUID(), nullable=False),
sa.Column('branch_id', sa.UUID(), nullable=False),
sa.Column('source_prediction_id', sa.UUID(), nullable=True),
sa.Column('priority', sa.String(length=20), nullable=False),
sa.Column('summary', sa.String(length=500), nullable=False),
sa.Column('explanation', sa.Text(), nullable=True),
sa.Column('deep_link', sa.String(length=500), nullable=True),
sa.Column('status', sa.Enum('NEW', 'DISMISSED', 'ACTED_UPON', name='ai_recommendation_status'), nullable=False),
sa.Column('model_version', sa.String(length=50), nullable=False),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], name=op.f('fk_ai_recommendations_branch_id_branches'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['nursery_id'], ['nurseries.id'], name=op.f('fk_ai_recommendations_nursery_id_nurseries'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['source_prediction_id'], ['ai_predictions.id'], name=op.f('fk_ai_recommendations_source_prediction_id_ai_predictions'), ondelete='SET NULL'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_recommendations'))
)

    op.create_index('ix_ai_recommendations_branch_status', 'ai_recommendations', ['branch_id', 'status'], unique=False)

    op.create_table('disease_reports',
sa.Column('plant_id', sa.UUID(), nullable=False),
sa.Column('source_ai_prediction_id', sa.UUID(), nullable=True),
sa.Column('condition_name', sa.String(length=255), nullable=False),
sa.Column('status', sa.Enum('DRAFT', 'CONFIRMED', 'DISMISSED', 'TREATED', 'RESOLVED', name='disease_report_status'), nullable=False),
sa.Column('severity', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='disease_report_severity'), nullable=False),
sa.Column('is_ai_sourced', sa.Boolean(), nullable=False),
sa.Column('ai_confidence', sa.Numeric(precision=5, scale=4), nullable=True),
sa.Column('photo_url', sa.String(length=1000), nullable=True),
sa.Column('confirmed_by_user_id', sa.UUID(), nullable=True),
sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('dismissed_reason', sa.Text(), nullable=True),
sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['confirmed_by_user_id'], ['users.id'], name=op.f('fk_disease_reports_confirmed_by_user_id_users')),
sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_disease_reports_plant_id_plants'), ondelete='CASCADE'),
sa.ForeignKeyConstraint(['source_ai_prediction_id'], ['ai_predictions.id'], name=op.f('fk_disease_reports_source_ai_prediction_id_ai_predictions'), ondelete='SET NULL'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_disease_reports'))
)

    op.create_index('ix_disease_reports_plant_id', 'disease_reports', ['plant_id'], unique=False)

    op.create_index('ix_disease_reports_status_severity', 'disease_reports', ['status', 'severity'], unique=False)

    op.create_table('treatments',
sa.Column('disease_report_id', sa.UUID(), nullable=False),
sa.Column('description', sa.Text(), nullable=False),
sa.Column('outcome', sa.Enum('ONGOING', 'RECOVERED', 'PLANT_LOST', name='treatment_outcome'), nullable=False),
sa.Column('applied_by_user_id', sa.UUID(), nullable=False),
sa.Column('applied_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
sa.ForeignKeyConstraint(['applied_by_user_id'], ['users.id'], name=op.f('fk_treatments_applied_by_user_id_users')),
sa.ForeignKeyConstraint(['disease_report_id'], ['disease_reports.id'], name=op.f('fk_treatments_disease_report_id_disease_reports'), ondelete='CASCADE'),
sa.PrimaryKeyConstraint('id', name=op.f('pk_treatments'))
)

    op.create_index('ix_treatments_disease_report_id', 'treatments', ['disease_report_id'], unique=False)

def downgrade() -> None:
    op.drop_table('treatments')
    op.drop_table('disease_reports')
    op.drop_table('ai_recommendations')
    op.drop_table('watering_logs')
    op.drop_table('sale_items')
    op.drop_table('purchase_order_items')
    op.drop_table('plant_transfers')
    op.drop_table('plant_images')
    op.drop_table('payments')
    op.drop_table('passports')
    op.drop_table('invoice_sales')
    op.drop_table('invoice_items')
    op.drop_table('inventory_adjustments')
    op.drop_table('health_history')
    op.drop_table('growth_timeline')
    op.drop_table('fertilizer_logs')
    op.drop_table('environmental_readings')
    op.drop_table('ai_predictions')
    op.drop_table('sales')
    op.drop_table('role_assignment_branch_scopes')
    op.drop_table('purchase_orders')
    op.drop_table('plants')
    op.drop_table('invoices')
    op.drop_table('suppliers')
    op.drop_table('role_permissions')
    op.drop_table('role_assignments')
    op.drop_table('reports')
    op.drop_table('plant_varieties')
    op.drop_table('invites')
    op.drop_table('inventory')
    op.drop_table('customers')
    op.drop_table('ai_assistant_messages')
    op.drop_table('usage_counters')
    op.drop_table('subscriptions')
    op.drop_table('species')
    op.drop_table('roles')
    op.drop_table('org_settings')
    op.drop_table('notifications')
    op.drop_table('notification_preferences')
    op.drop_table('employees')
    op.drop_table('branches')
    op.drop_table('audit_logs')
    op.drop_table('attachments')
    op.drop_table('ai_assistant_conversations')
    op.drop_table('users')
    op.drop_table('units')
    op.drop_table('plant_categories')
    op.drop_table('permissions')
    op.drop_table('nurseries')
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
