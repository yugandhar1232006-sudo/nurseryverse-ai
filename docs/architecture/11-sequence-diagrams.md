# Sequence Diagrams

Technical (component-level) sequence diagrams for the seven flows specified for this phase. These are more granular than the product-level flows in `docs/ux/03-screen-flow-diagrams.md` and `docs/ux/11-data-flow-diagrams.md` — every actor here is a concrete architectural component (service class, table, external system) defined earlier in this Phase 4 document set.

## 1. Login

```mermaid
sequenceDiagram
    participant FE as Next.js Frontend
    participant MW as Auth Middleware
    participant Auth as AuthService
    participant DB as PostgreSQL (users)
    participant Redis as Redis (refresh denylist)

    FE->>MW: POST /auth/login {email, password}
    MW->>Auth: authenticate(email, password)
    Auth->>DB: SELECT user WHERE email = ?
    DB-->>Auth: user row (password_hash)
    Auth->>Auth: verify_password(password, password_hash)
    alt invalid credentials
        Auth-->>FE: 401 invalid_credentials (generic message)
    else valid
        Auth->>Auth: issue access_token (RS256, 15min)
        Auth->>Auth: issue refresh_token (opaque, hashed)
        Auth->>DB: store hashed refresh_token
        Auth->>Redis: (no denylist entry yet - token is fresh)
        Auth-->>FE: 200 {access_token} + Set-Cookie: refresh_token (httpOnly)
        FE->>FE: store access_token in memory (Zustand)
    end
```

## 2. Plant Registration

```mermaid
sequenceDiagram
    participant FE as Frontend (PG-21)
    participant API as PlantService
    participant SpeciesRepo as SpeciesRepository
    participant PlantRepo as PlantRepository
    participant QR as QRCodeService
    participant Cloud as Cloudinary
    participant DB as PostgreSQL
    participant Audit as AuditLogService

    FE->>API: POST /plants {species_id, branch_id, initial_photo}
    API->>SpeciesRepo: get(species_id) - tenant-scoped
    SpeciesRepo->>DB: SELECT species WHERE id = ? AND nursery_id = ?
    DB-->>SpeciesRepo: species row
    API->>Cloud: signed upload (initial_photo)
    Cloud-->>API: image URL
    API->>DB: BEGIN
    API->>PlantRepo: insert(plant, status=in_production)
    API->>QR: generate_token_and_code(plant.id)
    QR->>PlantRepo: update(qr_code_token)
    API->>DB: insert plant_images row
    API->>Audit: log(actor, "plant.created", plant.id)
    API->>DB: COMMIT
    API-->>FE: 201 {plant with QR code}
```

## 3. AI Disease Detection

```mermaid
sequenceDiagram
    participant FE as Frontend (PG-28)
    participant API as FastAPI endpoint
    participant Cloud as Cloudinary
    participant FS as FeatureStore
    participant Model as Disease Detection CNN
    participant Logger as PredictionLogger
    participant DB as PostgreSQL
    participant Notif as NotificationService
    participant WS as WebSocket/Redis pub-sub

    FE->>API: POST /ai/disease-detection/scan (image)
    API->>Cloud: signed upload + fetch normalized derivative
    Cloud-->>API: image URL
    API->>FS: assemble(plant_id) - species susceptibility prior
    FS-->>API: features
    API->>Model: predict(image, features)
    Model-->>API: {condition, confidence}
    API->>Logger: persist(prediction) - ALWAYS, before response
    Logger->>DB: insert ai_predictions row
    alt confidence >= auto-flag threshold
        API->>DB: insert draft disease_reports row
        API->>Notif: create(event=disease_confirmed_pending)
        Notif->>WS: publish event
        WS-->>FE: real-time notification badge update
    end
    API-->>FE: 200 {prediction, report_id?}
```

## 4. Digital Twin Update (growth log triggers a prediction refresh)

```mermaid
sequenceDiagram
    participant FE as Frontend (PG-23)
    participant API as GrowthService
    participant DB as PostgreSQL
    participant Queue as Redis (Celery broker)
    participant Worker as Celery Worker
    participant GrowthAI as Growth Prediction Module
    participant WS as WebSocket

    FE->>API: POST /plants/{id}/growth-timeline {height, spread}
    API->>DB: BEGIN
    API->>DB: insert growth_timeline row
    API->>DB: COMMIT
    API->>Queue: enqueue(refresh_growth_prediction, plant_id)
    API-->>FE: 201 {growth entry} (immediate response, not blocked on AI)
    Queue->>Worker: dequeue job
    Worker->>GrowthAI: predict(plant_id)
    GrowthAI->>DB: read growth_timeline + species baseline
    GrowthAI-->>Worker: projected curve
    Worker->>DB: insert ai_predictions row
    Worker->>WS: publish "prediction ready" event
    WS-->>FE: chart overlay updates live (if PG-23 still open)
```

## 5. Inventory Update (Purchase Order receipt)

```mermaid
sequenceDiagram
    participant FE as Frontend (PG-50)
    participant API as PurchaseOrderService
    participant PORepo as PurchaseOrderRepository
    participant InvSvc as InventoryService
    participant DB as PostgreSQL
    participant Audit as AuditLogService

    FE->>API: POST /purchase-orders/{id}/receive {line_items: [{item_id, qty_received}]}
    API->>PORepo: get(po_id) - tenant/branch-scoped
    PORepo-->>API: PO with line items
    API->>API: validate qty_received <= qty_ordered per line
    API->>DB: BEGIN
    loop each line item
        API->>PORepo: update(line.received_quantity)
        API->>InvSvc: apply_change(inventory_id, +qty_received, reason=po_receipt)
        InvSvc->>DB: SELECT ... FOR UPDATE (row lock)
        InvSvc->>DB: update inventory.quantity
        InvSvc->>DB: insert inventory_adjustments row
    end
    API->>Audit: log(actor, "purchase_order.received", po.id)
    API->>DB: COMMIT
    API-->>FE: 200 {updated PO, updated inventory}
```

## 6. Plant Sale

```mermaid
sequenceDiagram
    participant FE as Frontend (PG-39 POS)
    participant API as SalesService
    participant Avail as AvailabilityChecker
    participant PlantSvc as PlantService
    participant DB as PostgreSQL
    participant Audit as AuditLogService

    FE->>API: POST /sales {items: [{plant_id}], customer_id?}
    API->>DB: BEGIN
    API->>Avail: check(plant_id) - SELECT ... FOR UPDATE
    Avail->>DB: lock + read plant.status
    alt status != ready_for_sale
        Avail-->>API: unavailable
        API->>DB: ROLLBACK
        API-->>FE: 409 item_unavailable
    else available
        API->>DB: insert sales + sale_items
        API->>PlantSvc: transition_status(plant_id, sold)
        PlantSvc->>DB: update plants.status
        API->>Audit: log(actor, "sale.completed", sale.id)
        API->>DB: COMMIT
        API-->>FE: 201 {sale, receipt data}
    end
```

## 7. Notification Delivery

```mermaid
sequenceDiagram
    participant Trigger as Triggering Service (e.g., DiseaseReportService)
    participant NotifSvc as NotificationService
    participant DB as PostgreSQL
    participant Queue as Redis (Celery broker)
    participant Dispatcher as NotificationDispatcher (Celery Worker)
    participant Prefs as notification_preferences
    participant WS as WebSocket / Redis pub-sub
    participant Email as Email Provider
    participant SMS as SMS Provider

    Trigger->>NotifSvc: create(event, recipients)
    NotifSvc->>DB: insert notifications row(s) - always, in-app first
    NotifSvc->>Queue: enqueue dispatch job
    NotifSvc-->>Trigger: return (does not block on delivery)
    Queue->>Dispatcher: dequeue job
    Dispatcher->>DB: read Prefs for each recipient
    Dispatcher->>WS: publish in-app event (always, per recipient)
    WS-->>Dispatcher: (fan-out to connected clients via Redis pub/sub)
    alt email enabled for category
        Dispatcher->>Email: send
    end
    alt SMS enabled for category + org + user
        Dispatcher->>SMS: send
    end
    alt delivery failure (email/SMS)
        Dispatcher->>Dispatcher: retry with backoff (Celery retry policy)
    end
```
