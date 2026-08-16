# Data Flow Diagrams

System-level data flow (not UI screen flow — see `03-screen-flow-diagrams.md` for that). These trace how data moves through frontend, API, database, cache, queue, and external services for the highest-value operations.

## 1. Plant Photo Upload → AI Disease Detection (synchronous inference)

```mermaid
sequenceDiagram
    participant U as User (mobile)
    participant FE as Next.js Frontend
    participant API as FastAPI Backend
    participant Cloud as Cloudinary
    participant AI as AI Disease Detection Module
    participant DB as PostgreSQL
    participant WS as WebSocket/Notification

    U->>FE: Capture/select photo
    FE->>API: POST /ai/disease-detection/scan (multipart)
    API->>Cloud: Upload image
    Cloud-->>API: Image URL
    API->>DB: Insert plant_images row
    API->>AI: Run inference (image URL/tensor)
    AI-->>API: Prediction (condition, confidence)
    API->>DB: Insert ai_predictions row (always, before response)
    alt confidence above auto-flag threshold
        API->>DB: Insert draft disease_reports row
        API->>WS: Push notification event
    end
    API-->>FE: Prediction result + report status
    FE-->>U: AIResultCard rendered
```

## 2. Sale Transaction (inventory consistency path)

```mermaid
sequenceDiagram
    participant U as Sales Staff
    participant FE as Frontend (POS)
    participant API as Backend
    participant DB as PostgreSQL

    U->>FE: Scan/search item, add to cart
    FE->>API: GET /plants/{id} or /inventory/{id}
    API->>DB: Read current status/quantity
    DB-->>API: Status/quantity
    API-->>FE: Availability confirmed/denied
    U->>FE: Complete sale
    FE->>API: POST /sales
    API->>DB: BEGIN transaction
    API->>DB: Insert sales + sale_items
    API->>DB: Update plants.status = sold OR inventory.quantity -= n
    API->>DB: COMMIT
    API-->>FE: Sale confirmation + receipt data
```

The sale-completion write is a single database transaction spanning the sale record and the inventory/plant status update — this is the mechanism behind FR-13.2's "no overselling" guarantee; a failed status update rolls back the sale, not the other way around.

## 3. AI Revenue Forecast (asynchronous, scheduled + on-demand)

```mermaid
sequenceDiagram
    participant Sched as Celery Beat (scheduled) / User (on-demand)
    participant Worker as Celery Worker
    participant DB as PostgreSQL
    participant AI as Revenue Forecast Module
    participant WS as WebSocket

    Sched->>Worker: Enqueue forecast job (nightly, or on-demand request)
    Worker->>DB: Read sales history for branch/org
    DB-->>Worker: Historical sales data
    Worker->>AI: Run forecast model
    AI-->>Worker: Forecast curve + confidence interval
    Worker->>DB: Insert ai_predictions row (revenue_forecast type)
    Worker->>WS: Push "forecast ready" event
    WS-->>Sched: Notify requesting user (if on-demand)
```

## 4. Notification Dispatch (multi-channel fan-out)

```mermaid
sequenceDiagram
    participant Trigger as Triggering Event (health/watering/inventory/invoice)
    participant Service as Domain Service
    participant Queue as Redis / Celery
    participant Worker as Notification Worker
    participant DB as PostgreSQL
    participant Email as Email Provider
    participant SMS as SMS Provider (optional)
    participant WS as WebSocket

    Trigger->>Service: Domain event occurs (e.g., disease confirmed)
    Service->>DB: Insert notifications row
    Service->>Queue: Enqueue dispatch job
    Queue->>Worker: Pick up job
    Worker->>DB: Read user notification_preferences
    Worker->>WS: Push in-app notification (always)
    alt email enabled for category
        Worker->>Email: Send email
    end
    alt SMS enabled for category and org
        Worker->>SMS: Send SMS
    end
```

## 5. Report Export (long-running, async with completion notification)

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as Backend
    participant Queue as Celery
    participant Worker as Report Worker
    participant DB as PostgreSQL
    participant Cloud as Cloudinary (document storage)
    participant WS as WebSocket

    U->>FE: Configure + request report (PG-52)
    FE->>API: POST /reports/generate
    API->>Queue: Enqueue report job
    API-->>FE: 202 Accepted (job id)
    Queue->>Worker: Pick up job
    Worker->>DB: Query report data
    Worker->>Worker: Render PDF/Excel/CSV
    Worker->>Cloud: Upload generated file
    Worker->>DB: Insert reports row (metadata + URL)
    Worker->>WS: Push "report ready" event
    WS-->>FE: Notify user, show download link
```

## 6. Cross-Cutting: Tenant Scoping on Every Request

```mermaid
flowchart LR
    A[Incoming request + JWT] --> B[Auth middleware: verify token]
    B --> C[Resolve user, org_id, branch_ids, role, permissions]
    C --> D[Set Postgres session vars for RLS]
    D --> E[Permission middleware: require_permission check]
    E -->|denied| F[403, audit-logged]
    E -->|allowed| G[Service layer executes, scoped to org_id/branch_id]
    G --> H[Repository query - RLS enforces isolation as defense in depth]
    H --> I[Response]
```

Every diagram above assumes this scoping step has already occurred — it is the first thing that happens on every authenticated request and is not repeated in the other diagrams for brevity.
