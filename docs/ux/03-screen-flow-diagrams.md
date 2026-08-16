# Screen Flow Diagrams

Flow-level detail for the highest-value multi-screen workflows. Page IDs reference `01-sitemap.md`.

## 1. Onboarding (new Org)

```mermaid
flowchart TD
    A[PG-01 Landing] --> B[PG-02 Sign Up]
    B --> C{Email verified?}
    C -- No --> D[Resend verification]
    D --> C
    C -- Yes --> E[Create Org + first Branch - guided]
    E --> F[PG-07 Org Dashboard - empty state]
    F --> G[Prompt: invite employees]
    G --> H[PG-16 Invite Employee]
    F --> I[Prompt: add species / first plants]
    I --> J[PG-19 Create Species]
    J --> K[PG-21 Create Plant]
```

## 2. Employee Invite → First Login

```mermaid
flowchart TD
    A[Admin: PG-16 Invite Employee] --> B[Invite email sent]
    B --> C[PG-06 Accept Invite]
    C --> D{Existing account email?}
    D -- No --> E[Set password]
    D -- Yes --> F[Log in to accept]
    E --> G[Role + Branch scope applied]
    F --> G
    G --> H[PG-08 Branch Dashboard]
```

## 3. Plant Creation → Digital Twin → Sale (full lifecycle)

```mermaid
flowchart TD
    A[PG-20 Plants List] --> B[PG-21 Create Plant]
    B --> C[Select Species - PG-17/18]
    C --> D[QR code generated]
    D --> E[PG-22 Plant Digital Twin]
    E --> F[PG-23 Log growth entries over time]
    E --> G[PG-25 Log environmental / watering]
    E --> H[PG-28 AI Disease Detection scans]
    H --> I{Disease detected above threshold?}
    I -- Yes --> J[PG-30 Disease Report - treat]
    I -- No --> E
    J --> K{Outcome}
    K -- Recovered --> E
    K -- Plant lost --> L[Status: Deceased/Write-off]
    E --> M[Status: Ready for Sale]
    M --> N[PG-39 POS - scan QR, add to sale]
    N --> O[Status: Sold]
    O --> P[PG-53 Plant Passport generated]
```

## 4. AI Disease Detection → Treatment (detail)

```mermaid
flowchart TD
    A[PG-22 Plant Digital Twin] --> B[PG-28 Capture / upload photo]
    B --> C[Submit to AI Disease Detection service]
    C --> D[Prediction: condition + confidence]
    D --> E{Confidence above auto-flag threshold?}
    E -- Yes --> F[Draft Disease Report auto-created]
    E -- No --> G[Result shown, no report auto-created]
    F --> H[PG-30 Staff reviews, confirms or overrides]
    G --> I[Staff can manually create report - PG-29]
    H --> J{Confirmed?}
    J -- Yes --> K[Notification sent - FR-7.5]
    J -- No, false positive --> L[Marked dismissed, logged for model feedback]
    K --> M[Treatment logged]
    M --> N{Outcome}
    N -- Recovered --> O[PG-22 Twin updated, status normal]
    N -- Ongoing --> P[Remains open, follow-up reminder]
    N -- Lost --> Q[Plant status: Deceased]
```

## 5. POS Sale (Devon's checkout flow)

```mermaid
flowchart TD
    A[PG-39 POS / New Sale] --> B[Scan QR or search item]
    B --> C{Item type}
    C -- Individual plant --> D[Check status = Ready for Sale]
    C -- Bulk inventory --> E[Check quantity available]
    D --> F{Available?}
    E --> F
    F -- No --> G[Block add, show reason]
    F -- Yes --> H[Add to cart]
    H --> I[Attach customer - PG-42 search or create]
    I --> J[Apply discount if applicable]
    J --> K[Complete sale]
    K --> L[Inventory / plant status updated]
    L --> M[PG-41 Receipt generated]
    M --> N{Wholesale customer?}
    N -- Yes --> O[PG-46 Generate Invoice from sale]
    N -- No --> P[End]
```

## 6. Invoice Creation & Tracking

```mermaid
flowchart TD
    A[PG-40 Sales History] --> B[Select one or more sales]
    B --> C[PG-46 Create Invoice]
    C --> D[Apply terms - net 30/60, PO ref]
    D --> E[Generate PDF, email to customer]
    E --> F[PG-45 Invoice Detail - status: Sent]
    F --> G{Payment received?}
    G -- Yes, before due --> H[Status: Paid]
    G -- No, past due --> I[Status: Overdue]
    I --> J[Notification triggered - FR-15.4]
    G -- Voided --> K[Status: Void, audit logged]
```

## 7. Watering Task Flow

```mermaid
flowchart TD
    A[AI Water Recommendation engine] --> B[PG-34 Watering Schedule generated]
    B --> C[Staff opens today's tasks]
    C --> D[PG-35 Log watering event per plant/zone]
    D --> E[Watering history updated]
    E --> F[Schedule recalculated for next due date]
    B --> G{Task overdue past threshold?}
    G -- Yes --> H[Notification - FR-11.3]
    H --> C
```

## 8. Purchasing / Receiving Flow

```mermaid
flowchart TD
    A[PG-47 Suppliers List] --> B[PG-49 Purchase Orders List]
    B --> C[PG-50 Create Purchase Order]
    C --> D[Send to supplier - external]
    D --> E[Stock arrives]
    E --> F[PG-50 Receive against PO]
    F --> G[PG-36 Inventory quantities updated]
    G --> H{Below low-stock threshold before receipt?}
    H -- Yes --> I[Low-stock notification cleared]
```
