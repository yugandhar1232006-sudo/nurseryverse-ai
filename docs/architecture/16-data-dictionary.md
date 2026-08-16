# Data Dictionary

Complete column-level reference for all 50 tables, satisfying Production Database Readiness Review §8. Generated mechanically by `apps/api/scripts/generate_data_dictionary.py` directly from `app.models.Base.metadata` — every type shown is compiled against the real PostgreSQL dialect, so this document cannot drift from the live schema (regenerate after any model change: `python3 scripts/generate_data_dictionary.py > ../docs/architecture/16-data-dictionary.md`, run from `apps/api/`).

<!-- Generated mechanically by scripts/generate_data_dictionary.py -->
<!-- Total tables: 50 -->

### `ai_assistant_conversations`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `user_id` | `UUID` | FK -> users.id, NOT NULL |
| `title` | `VARCHAR(255)` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Indexes:**
- `ix_ai_assistant_conversations_user_id` (user_id)

### `ai_assistant_messages`

| Column | Type | Flags |
|---|---|---|
| `conversation_id` | `UUID` | FK -> ai_assistant_conversations.id, NOT NULL |
| `role` | `VARCHAR(20)` | NOT NULL |
| `content` | `TEXT` | NOT NULL |
| `proposed_action` | `JSON` | - |
| `action_status` | `VARCHAR(30)` | - |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_ai_assistant_messages_conversation_id` (conversation_id)

### `ai_predictions`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `branch_id` | `UUID` | FK -> branches.id |
| `plant_id` | `UUID` | FK -> plants.id |
| `prediction_type` | `ai_prediction_type` | NOT NULL |
| `model_version` | `VARCHAR(50)` | NOT NULL |
| `result` | `JSON` | NOT NULL |
| `confidence` | `NUMERIC(5, 4)` | - |
| `explanation` | `TEXT` | - |
| `inputs_summary` | `JSON` | - |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_ai_predictions_nursery_branch` (nursery_id, branch_id)
- `ix_ai_predictions_plant_type_created` (plant_id, prediction_type, created_at)

### `ai_recommendations`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `source_prediction_id` | `UUID` | FK -> ai_predictions.id |
| `priority` | `VARCHAR(20)` | NOT NULL, DEFAULT 'medium' |
| `summary` | `VARCHAR(500)` | NOT NULL |
| `explanation` | `TEXT` | - |
| `deep_link` | `VARCHAR(500)` | - |
| `status` | `ai_recommendation_status` | NOT NULL, DEFAULT <AIRecommendationStatus.NEW: 'new'> |
| `model_version` | `VARCHAR(50)` | NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_ai_recommendations_branch_status` (branch_id, status)

### `attachments`

| Column | Type | Flags |
|---|---|---|
| `entity_type` | `VARCHAR(50)` | NOT NULL |
| `entity_id` | `UUID` | NOT NULL |
| `file_name` | `VARCHAR(255)` | NOT NULL |
| `file_url` | `VARCHAR(1000)` | NOT NULL |
| `content_type` | `VARCHAR(100)` | - |
| `file_size_bytes` | `INTEGER` | - |
| `uploaded_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `uploaded_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |

**Indexes:**
- `ix_attachments_entity_type_entity_id` (entity_type, entity_id)

### `audit_logs`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `actor_user_id` | `UUID` | FK -> users.id |
| `action` | `VARCHAR(100)` | NOT NULL |
| `entity_type` | `VARCHAR(100)` | NOT NULL |
| `entity_id` | `UUID` | - |
| `diff` | `JSON` | - |
| `request_id` | `VARCHAR(64)` | - |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_audit_logs_actor_id` (actor_user_id)
- `ix_audit_logs_nursery_created_at` (nursery_id, created_at)

### `branches`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `name` | `VARCHAR(255)` | NOT NULL |
| `address_line1` | `VARCHAR(255)` | NOT NULL |
| `address_line2` | `VARCHAR(255)` | - |
| `city` | `VARCHAR(120)` | NOT NULL |
| `region` | `VARCHAR(120)` | - |
| `postal_code` | `VARCHAR(20)` | - |
| `country` | `VARCHAR(2)` | NOT NULL |
| `timezone` | `VARCHAR(64)` | NOT NULL |
| `status` | `branch_status` | NOT NULL, DEFAULT <BranchStatus.ACTIVE: 'active'> |
| `default_low_stock_threshold` | `INTEGER` | NOT NULL, DEFAULT 10 |
| `default_watering_overdue_hours` | `INTEGER` | NOT NULL, DEFAULT 48 |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(nursery_id, name)`

### `customers`

| Column | Type | Flags |
|---|---|---|
| `name` | `VARCHAR(255)` | NOT NULL |
| `email` | `VARCHAR(320)` | - |
| `phone` | `VARCHAR(50)` | - |
| `customer_type` | `customer_type` | NOT NULL, DEFAULT <CustomerType.RETAIL: 'retail'> |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Indexes:**
- `ix_customers_nursery_name` (nursery_id, name)

### `disease_reports`

| Column | Type | Flags |
|---|---|---|
| `plant_id` | `UUID` | FK -> plants.id, NOT NULL |
| `source_ai_prediction_id` | `UUID` | FK -> ai_predictions.id |
| `condition_name` | `VARCHAR(255)` | NOT NULL |
| `status` | `disease_report_status` | NOT NULL, DEFAULT <DiseaseReportStatus.DRAFT: 'draft'> |
| `severity` | `disease_report_severity` | NOT NULL |
| `is_ai_sourced` | `BOOLEAN` | NOT NULL, DEFAULT False |
| `ai_confidence` | `NUMERIC(5, 4)` | - |
| `photo_url` | `VARCHAR(1000)` | - |
| `confirmed_by_user_id` | `UUID` | FK -> users.id |
| `confirmed_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `dismissed_reason` | `TEXT` | - |
| `resolved_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_disease_reports_plant_id` (plant_id)
- `ix_disease_reports_status_severity` (status, severity)

### `employees`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `user_id` | `UUID` | FK -> users.id, NOT NULL |
| `status` | `employee_status` | NOT NULL, DEFAULT <EmployeeStatus.INVITED: 'invited'> |
| `deactivated_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(nursery_id, user_id)`

### `environmental_readings`

| Column | Type | Flags |
|---|---|---|
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `plant_id` | `UUID` | FK -> plants.id |
| `zone` | `VARCHAR(100)` | - |
| `temperature_celsius` | `NUMERIC(5, 2)` | - |
| `humidity_percent` | `NUMERIC(5, 2)` | - |
| `soil_moisture_percent` | `NUMERIC(5, 2)` | - |
| `light_lux` | `NUMERIC(10, 2)` | - |
| `source` | `VARCHAR(20)` | NOT NULL, DEFAULT 'manual' |
| `recorded_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_environmental_readings_branch_recorded_at` (branch_id, recorded_at)
- `ix_environmental_readings_plant_id` (plant_id)

### `fertilizer_logs`

| Column | Type | Flags |
|---|---|---|
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `plant_id` | `UUID` | FK -> plants.id |
| `zone` | `VARCHAR(100)` | - |
| `product_name` | `VARCHAR(255)` | NOT NULL |
| `quantity_ml` | `NUMERIC(8, 2)` | - |
| `npk_ratio` | `VARCHAR(20)` | - |
| `notes` | `TEXT` | - |
| `recorded_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `recorded_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_fertilizer_logs_branch_zone` (branch_id, zone)
- `ix_fertilizer_logs_plant_id_recorded_at` (plant_id, recorded_at)

### `growth_timeline`

| Column | Type | Flags |
|---|---|---|
| `plant_id` | `UUID` | FK -> plants.id, NOT NULL |
| `height_cm` | `NUMERIC(6, 2)` | - |
| `spread_cm` | `NUMERIC(6, 2)` | - |
| `growth_stage` | `VARCHAR(50)` | - |
| `photo_url` | `VARCHAR(1000)` | - |
| `notes` | `TEXT` | - |
| `recorded_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `recorded_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_growth_timeline_plant_id_recorded_at` (plant_id, recorded_at)

### `health_history`

| Column | Type | Flags |
|---|---|---|
| `plant_id` | `UUID` | FK -> plants.id, NOT NULL |
| `status_label` | `VARCHAR(50)` | NOT NULL |
| `notes` | `TEXT` | - |
| `photo_url` | `VARCHAR(1000)` | - |
| `recorded_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `recorded_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_health_history_plant_id_recorded_at` (plant_id, recorded_at)

### `inventory`

| Column | Type | Flags |
|---|---|---|
| `species_id` | `UUID` | FK -> species.id |
| `category_id` | `UUID` | FK -> plant_categories.id, NOT NULL |
| `unit_id` | `UUID` | FK -> units.id, NOT NULL |
| `name` | `VARCHAR(255)` | NOT NULL |
| `quantity` | `INTEGER` | NOT NULL, DEFAULT 0 |
| `unit_cost` | `NUMERIC(10, 2)` | - |
| `unit_price` | `NUMERIC(10, 2)` | - |
| `low_stock_threshold` | `INTEGER` | NOT NULL, DEFAULT 10 |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(branch_id, name)`

**Check constraints:**
- `quantity >= 0`

**Indexes:**
- `ix_inventory_nursery_branch` (nursery_id, branch_id)

### `inventory_adjustments`

| Column | Type | Flags |
|---|---|---|
| `inventory_id` | `UUID` | FK -> inventory.id, NOT NULL |
| `quantity_delta` | `INTEGER` | NOT NULL |
| `quantity_after` | `INTEGER` | NOT NULL |
| `reason` | `inventory_adjustment_reason` | NOT NULL |
| `reference_sale_id` | `UUID` | FK -> sales.id |
| `reference_purchase_order_id` | `UUID` | FK -> purchase_orders.id |
| `note` | `TEXT` | - |
| `adjusted_by_user_id` | `UUID` | FK -> users.id |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_inventory_adjustments_inventory_id` (inventory_id)

### `invites`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `invited_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `email` | `VARCHAR(320)` | NOT NULL |
| `role_id` | `UUID` | FK -> roles.id, NOT NULL |
| `token` | `VARCHAR(128)` | NOT NULL |
| `expires_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL |
| `accepted_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(token)`

### `invoice_items`

| Column | Type | Flags |
|---|---|---|
| `invoice_id` | `UUID` | FK -> invoices.id, NOT NULL |
| `description` | `VARCHAR(500)` | NOT NULL |
| `quantity` | `INTEGER` | NOT NULL, DEFAULT 1 |
| `unit_price` | `NUMERIC(10, 2)` | NOT NULL |
| `line_total` | `NUMERIC(10, 2)` | NOT NULL |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_invoice_items_invoice_id` (invoice_id)

### `invoice_sales`

| Column | Type | Flags |
|---|---|---|
| `invoice_id` | `UUID` | PK, FK -> invoices.id, NOT NULL |
| `sale_id` | `UUID` | PK, FK -> sales.id, NOT NULL |

### `invoices`

| Column | Type | Flags |
|---|---|---|
| `customer_id` | `UUID` | FK -> customers.id, NOT NULL |
| `invoice_number` | `VARCHAR(50)` | NOT NULL |
| `status` | `invoice_status` | NOT NULL, DEFAULT <InvoiceStatus.DRAFT: 'draft'> |
| `terms` | `VARCHAR(50)` | - |
| `po_reference` | `VARCHAR(100)` | - |
| `total_amount` | `NUMERIC(10, 2)` | NOT NULL |
| `due_date` | `TIMESTAMP WITH TIME ZONE` | - |
| `sent_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `paid_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `void_reason` | `TEXT` | - |
| `pdf_url` | `VARCHAR(1000)` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(nursery_id, invoice_number)`

**Indexes:**
- `ix_invoices_branch_status` (branch_id, status)

### `knowledge_base_chunks`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id |
| `source_type` | `VARCHAR(30)` | NOT NULL |
| `source_ref` | `VARCHAR(255)` | - |
| `title` | `VARCHAR(255)` | - |
| `content` | `TEXT` | NOT NULL |
| `embedding` | `VECTOR(1024)` | NOT NULL |
| `embedding_model_version` | `VARCHAR(50)` | NOT NULL |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Indexes:**
- `ix_knowledge_base_chunks_embedding_hnsw` (embedding)
- `ix_knowledge_base_chunks_nursery_source` (nursery_id, source_type)

### `notification_preferences`

| Column | Type | Flags |
|---|---|---|
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `user_id` | `UUID` | FK -> users.id, NOT NULL |
| `category` | `notification_category` | NOT NULL |
| `channel` | `notification_channel` | NOT NULL |
| `enabled` | `BOOLEAN` | NOT NULL, DEFAULT True |

**Composite unique constraints:**
- `(user_id, category, channel)`

### `notifications`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `recipient_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `category` | `notification_category` | NOT NULL |
| `message` | `VARCHAR(500)` | NOT NULL |
| `deep_link` | `VARCHAR(500)` | - |
| `read_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_notifications_recipient_read` (recipient_user_id, read_at)

### `nurseries`

| Column | Type | Flags |
|---|---|---|
| `name` | `VARCHAR(255)` | NOT NULL |
| `logo_url` | `VARCHAR(500)` | - |
| `contact_email` | `VARCHAR(320)` | NOT NULL |
| `contact_phone` | `VARCHAR(50)` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

### `org_settings`

| Column | Type | Flags |
|---|---|---|
| `sms_enabled` | `BOOLEAN` | NOT NULL, DEFAULT False |
| `sms_provider_config` | `JSON` | - |
| `email_sender_identity` | `VARCHAR(255)` | - |
| `branding_primary_color` | `VARCHAR(7)` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |

**Composite unique constraints:**
- `(nursery_id)`

### `passports`

| Column | Type | Flags |
|---|---|---|
| `plant_id` | `UUID` | FK -> plants.id, NOT NULL |
| `version` | `INTEGER` | NOT NULL, DEFAULT 1 |
| `public_token` | `VARCHAR(128)` | NOT NULL |
| `token_expires_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `content_snapshot` | `JSON` | NOT NULL |
| `pdf_url` | `VARCHAR(1000)` | - |
| `generated_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `generated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Composite unique constraints:**
- `(public_token)`

**Indexes:**
- `ix_passports_plant_id_version` (plant_id, version)

### `payments`

| Column | Type | Flags |
|---|---|---|
| `invoice_id` | `UUID` | FK -> invoices.id, NOT NULL |
| `amount` | `NUMERIC(10, 2)` | NOT NULL |
| `method` | `VARCHAR(50)` | NOT NULL |
| `reference` | `VARCHAR(100)` | - |
| `received_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `received_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_payments_invoice_id` (invoice_id)

### `permissions`

| Column | Type | Flags |
|---|---|---|
| `code` | `VARCHAR(100)` | NOT NULL |
| `module` | `VARCHAR(50)` | NOT NULL |
| `action` | `VARCHAR(50)` | NOT NULL |
| `description` | `VARCHAR(255)` | NOT NULL |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Composite unique constraints:**
- `(code)`

### `plant_categories`

| Column | Type | Flags |
|---|---|---|
| `code` | `VARCHAR(50)` | NOT NULL |
| `name` | `VARCHAR(100)` | NOT NULL |
| `description` | `VARCHAR(500)` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Composite unique constraints:**
- `(code)`

### `plant_images`

| Column | Type | Flags |
|---|---|---|
| `plant_id` | `UUID` | FK -> plants.id, NOT NULL |
| `url` | `VARCHAR(1000)` | NOT NULL |
| `thumbnail_url` | `VARCHAR(1000)` | - |
| `caption` | `VARCHAR(255)` | - |
| `captured_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `uploaded_by_user_id` | `UUID` | FK -> users.id |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_plant_images_plant_id` (plant_id)

### `plant_transfers`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `plant_id` | `UUID` | FK -> plants.id, NOT NULL |
| `from_branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `to_branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `note` | `TEXT` | - |
| `transferred_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `transferred_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_plant_transfers_plant_id` (plant_id)

### `plant_varieties`

| Column | Type | Flags |
|---|---|---|
| `species_id` | `UUID` | FK -> species.id, NOT NULL |
| `name` | `VARCHAR(255)` | NOT NULL |
| `description` | `VARCHAR(500)` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(species_id, name)`

### `plants`

| Column | Type | Flags |
|---|---|---|
| `species_id` | `UUID` | FK -> species.id, NOT NULL |
| `variety_id` | `UUID` | FK -> plant_varieties.id |
| `common_label` | `VARCHAR(255)` | - |
| `zone` | `VARCHAR(100)` | - |
| `status` | `plant_status` | NOT NULL, DEFAULT <PlantStatus.IN_PRODUCTION: 'in_production'> |
| `qr_code_token` | `VARCHAR(64)` | NOT NULL |
| `price` | `NUMERIC(10, 2)` | - |
| `planted_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL |
| `sold_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `deceased_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `deceased_reason` | `TEXT` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(qr_code_token)`

**Indexes:**
- `ix_plants_nursery_branch` (nursery_id, branch_id)
- `ix_plants_species_id` (species_id)
- `ix_plants_status` (status)

### `purchase_order_items`

| Column | Type | Flags |
|---|---|---|
| `purchase_order_id` | `UUID` | FK -> purchase_orders.id, NOT NULL |
| `inventory_id` | `UUID` | FK -> inventory.id, NOT NULL |
| `ordered_quantity` | `INTEGER` | NOT NULL |
| `received_quantity` | `INTEGER` | NOT NULL, DEFAULT 0 |
| `unit_cost` | `NUMERIC(10, 2)` | NOT NULL |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Check constraints:**
- `received_quantity <= ordered_quantity`

**Indexes:**
- `ix_purchase_order_items_po_id` (purchase_order_id)

### `purchase_orders`

| Column | Type | Flags |
|---|---|---|
| `supplier_id` | `UUID` | FK -> suppliers.id, NOT NULL |
| `po_number` | `VARCHAR(50)` | NOT NULL |
| `status` | `purchase_order_status` | NOT NULL, DEFAULT <PurchaseOrderStatus.DRAFT: 'draft'> |
| `total_cost` | `NUMERIC(10, 2)` | NOT NULL, DEFAULT 0 |
| `sent_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(nursery_id, po_number)`

**Indexes:**
- `ix_purchase_orders_branch_status` (branch_id, status)

### `reports`

| Column | Type | Flags |
|---|---|---|
| `branch_id` | `UUID` | FK -> branches.id |
| `report_type` | `report_type` | NOT NULL |
| `format` | `report_format` | NOT NULL |
| `status` | `report_status` | NOT NULL, DEFAULT <ReportStatus.PENDING: 'pending'> |
| `filters` | `JSON` | - |
| `file_url` | `VARCHAR(1000)` | - |
| `requested_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `completed_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |

**Indexes:**
- `ix_reports_nursery_created_at` (nursery_id, created_at)

### `role_assignment_branch_scopes`

| Column | Type | Flags |
|---|---|---|
| `role_assignment_id` | `UUID` | PK, FK -> role_assignments.id, NOT NULL |
| `branch_id` | `UUID` | PK, FK -> branches.id, NOT NULL |

### `role_assignments`

| Column | Type | Flags |
|---|---|---|
| `user_id` | `UUID` | FK -> users.id, NOT NULL |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `role_id` | `UUID` | FK -> roles.id, NOT NULL |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(user_id, nursery_id)`

### `role_permissions`

| Column | Type | Flags |
|---|---|---|
| `role_id` | `UUID` | PK, FK -> roles.id, NOT NULL |
| `permission_id` | `UUID` | PK, FK -> permissions.id, NOT NULL |
| `scope` | `VARCHAR(1)` | NOT NULL, DEFAULT 'B' |

### `roles`

| Column | Type | Flags |
|---|---|---|
| `nursery_id` | `UUID` | FK -> nurseries.id |
| `code` | `VARCHAR(50)` | NOT NULL |
| `name` | `VARCHAR(100)` | NOT NULL |
| `is_system_role` | `BOOLEAN` | NOT NULL, DEFAULT False |
| `permission_ceiling_role_code` | `VARCHAR(50)` | NOT NULL, DEFAULT 'org_admin' |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(nursery_id, code)`

### `sale_items`

| Column | Type | Flags |
|---|---|---|
| `sale_id` | `UUID` | FK -> sales.id, NOT NULL |
| `plant_id` | `UUID` | FK -> plants.id |
| `inventory_id` | `UUID` | FK -> inventory.id |
| `quantity` | `INTEGER` | NOT NULL, DEFAULT 1 |
| `unit_price` | `NUMERIC(10, 2)` | NOT NULL |
| `line_total` | `NUMERIC(10, 2)` | NOT NULL |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Check constraints:**
- `(plant_id IS NOT NULL AND inventory_id IS NULL) OR (plant_id IS NULL AND inventory_id IS NOT NULL)`

**Indexes:**
- `ix_sale_items_sale_id` (sale_id)

### `sales`

| Column | Type | Flags |
|---|---|---|
| `customer_id` | `UUID` | FK -> customers.id |
| `status` | `sale_status` | NOT NULL, DEFAULT <SaleStatus.COMPLETED: 'completed'> |
| `subtotal_amount` | `NUMERIC(10, 2)` | NOT NULL |
| `discount_amount` | `NUMERIC(10, 2)` | NOT NULL, DEFAULT 0 |
| `total_amount` | `NUMERIC(10, 2)` | NOT NULL |
| `payment_method` | `VARCHAR(50)` | - |
| `sold_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `void_reason` | `TEXT` | - |
| `voided_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `idempotency_key` | `VARCHAR(128)` | - |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |

**Composite unique constraints:**
- `(branch_id, idempotency_key)`

**Check constraints:**
- `total_amount >= 0`

**Indexes:**
- `ix_sales_branch_created_at` (branch_id, created_at)

### `species`

| Column | Type | Flags |
|---|---|---|
| `category_id` | `UUID` | FK -> plant_categories.id, NOT NULL |
| `common_name` | `VARCHAR(255)` | NOT NULL |
| `botanical_name` | `VARCHAR(255)` | NOT NULL |
| `light_requirement` | `VARCHAR(50)` | - |
| `water_baseline_ml_per_week` | `INTEGER` | - |
| `soil_type` | `VARCHAR(100)` | - |
| `temperature_min_celsius` | `NUMERIC(5, 2)` | - |
| `temperature_max_celsius` | `NUMERIC(5, 2)` | - |
| `growth_curve_baseline` | `JSON` | - |
| `disease_susceptibility` | `JSON` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(nursery_id, botanical_name)`

### `subscriptions`

| Column | Type | Flags |
|---|---|---|
| `plan` | `subscription_plan` | NOT NULL, DEFAULT <SubscriptionPlan.STARTER: 'starter'> |
| `status` | `subscription_status` | NOT NULL, DEFAULT <SubscriptionStatus.ACTIVE: 'active'> |
| `branch_limit` | `INTEGER` | NOT NULL, DEFAULT 1 |
| `seat_limit` | `INTEGER` | - |
| `ai_credit_monthly_limit` | `INTEGER` | - |
| `current_period_end` | `TIMESTAMP WITH TIME ZONE` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(nursery_id)`

### `suppliers`

| Column | Type | Flags |
|---|---|---|
| `name` | `VARCHAR(255)` | NOT NULL |
| `contact_name` | `VARCHAR(255)` | - |
| `email` | `VARCHAR(320)` | - |
| `phone` | `VARCHAR(50)` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(branch_id, name)`

### `treatments`

| Column | Type | Flags |
|---|---|---|
| `disease_report_id` | `UUID` | FK -> disease_reports.id, NOT NULL |
| `description` | `TEXT` | NOT NULL |
| `outcome` | `treatment_outcome` | NOT NULL, DEFAULT <TreatmentOutcome.ONGOING: 'ongoing'> |
| `applied_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `applied_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_treatments_disease_report_id` (disease_report_id)

### `units`

| Column | Type | Flags |
|---|---|---|
| `code` | `VARCHAR(20)` | NOT NULL |
| `name` | `VARCHAR(50)` | NOT NULL |
| `unit_type` | `VARCHAR(20)` | NOT NULL, DEFAULT 'count' |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Composite unique constraints:**
- `(code)`

### `usage_counters`

| Column | Type | Flags |
|---|---|---|
| `metric` | `VARCHAR(50)` | NOT NULL |
| `period_start` | `TIMESTAMP WITH TIME ZONE` | NOT NULL |
| `period_end` | `TIMESTAMP WITH TIME ZONE` | NOT NULL |
| `count` | `INTEGER` | NOT NULL, DEFAULT 0 |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `nursery_id` | `UUID` | FK -> nurseries.id, NOT NULL |

**Composite unique constraints:**
- `(nursery_id, metric, period_start)`

### `users`

| Column | Type | Flags |
|---|---|---|
| `email` | `VARCHAR(320)` | NOT NULL |
| `password_hash` | `VARCHAR(255)` | NOT NULL |
| `full_name` | `VARCHAR(255)` | NOT NULL |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT True |
| `last_login_at` | `TIMESTAMP WITH TIME ZONE` | - |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `updated_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |

**Composite unique constraints:**
- `(email)`

**Indexes:**
- `ix_users_email` (email)

### `watering_logs`

| Column | Type | Flags |
|---|---|---|
| `branch_id` | `UUID` | FK -> branches.id, NOT NULL |
| `plant_id` | `UUID` | FK -> plants.id |
| `zone` | `VARCHAR(100)` | - |
| `volume_ml` | `NUMERIC(8, 2)` | - |
| `notes` | `TEXT` | - |
| `recorded_by_user_id` | `UUID` | FK -> users.id, NOT NULL |
| `recorded_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL, SERVER_DEFAULT now() |
| `id` | `UUID` | PK, NOT NULL, SERVER_DEFAULT gen_random_uuid() |

**Indexes:**
- `ix_watering_logs_branch_zone` (branch_id, zone)
- `ix_watering_logs_plant_id_recorded_at` (plant_id, recorded_at)

