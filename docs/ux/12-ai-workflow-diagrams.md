# AI Workflow Diagrams

One workflow per AI module (FR-8, FR-9). Each shows the input → processing → output → persistence path. Model/architecture detail (frameworks, training approach) belongs to Phase 4/8 — this document defines the *workflow contract* those phases implement against.

## 1. Disease Detection

```mermaid
flowchart TD
    A[Trigger: photo captured/uploaded] --> B[Image validated - type/size]
    B --> C[Uploaded to Cloudinary]
    C --> D[Preprocessed - resize/normalize]
    D --> E[CNN inference]
    E --> F[Condition + confidence score]
    F --> G[Persist ai_predictions row - always]
    G --> H{Confidence ≥ auto-flag threshold?}
    H -- Yes --> I[Draft disease_report created]
    I --> J[Notification triggered]
    H -- No --> K[Result shown, no report auto-created]
    J --> L[Human review - confirm/dismiss]
    K --> L
    L --> M{Dismissed as false positive?}
    M -- Yes --> N[Feedback logged for retraining]
    M -- No --> O[Treatment workflow begins]
```

## 2. Growth Prediction

```mermaid
flowchart TD
    A[Trigger: scheduled nightly OR growth entry logged] --> B[Read plant's growth_timeline]
    B --> C[Read species baseline growth curve]
    C --> D{Sufficient plant-specific history?}
    D -- Yes --> E[Model: plant-specific time series]
    D -- No --> F[Model: species baseline + environmental adjustment]
    E --> G[Projected growth curve]
    F --> G
    G --> H[Persist ai_predictions row]
    H --> I[Displayed on PG-23 Growth Timeline as overlay]
```

## 3. Survival Prediction

```mermaid
flowchart TD
    A[Trigger: scheduled OR new health/environmental event] --> B[Aggregate features: health history, environmental exposure, watering consistency, species susceptibility, disease report history]
    B --> C[Classification model - risk score + contributing factors]
    C --> D[Persist ai_predictions row]
    D --> E{Risk score above alert threshold?}
    E -- Yes --> F[Surfaced on PG-31 ranked at-risk list]
    F --> G[Feeds Recommendation Engine]
    E -- No --> H[Available on-demand in PG-26, not proactively surfaced]
```

## 4. Water Recommendation

```mermaid
flowchart TD
    A[Trigger: scheduled OR new environmental reading OR watering event logged] --> B[Read species baseline water requirement]
    B --> C[Read recent environmental readings for zone/plant]
    C --> D[Read recent watering history]
    D --> E[Model + rule layer: recommended volume/frequency]
    E --> F[Persist ai_predictions row]
    F --> G[Watering schedule PG-34 recalculated]
    G --> H{Task becomes overdue?}
    H -- Yes --> I[Notification triggered - FR-11.3]
```

## 5. Revenue Forecast

```mermaid
flowchart TD
    A[Trigger: nightly schedule OR on-demand request] --> B[Read sales history - branch/org, configurable lookback]
    B --> C[Time-series decomposition - seasonality, trend]
    C --> D[Forecast model projects forward window]
    D --> E[Confidence interval computed]
    E --> F[Persist ai_predictions row]
    F --> G[Displayed on PG-32, exportable via PG-52]
```

## 6. Recommendation Engine

```mermaid
flowchart TD
    A[Trigger: scheduled aggregation pass] --> B[Pull latest predictions: survival risk, growth anomalies, water needs]
    B --> C[Pull operational signals: low stock, overdue watering, unresolved disease reports]
    C --> D[Feature-weighted scoring - priority ranking]
    D --> E[LLM generates plain-language explanation per recommendation]
    E --> F[Persist ai_recommendations row]
    F --> G[Surfaced on PG-33 Recommendation Feed]
    G --> H{User dismisses or acts?}
    H -- Dismiss --> I[Logged, deprioritized in future ranking]
    H -- Acts --> J[Deep-link to relevant page - e.g. PG-30, PG-36]
```

## 7. AI Assistant (conversational, tool-using)

```mermaid
flowchart TD
    A[User sends message] --> B[Assistant resolves intent]
    B --> C{Read query or write request?}
    C -- Read --> D[Tool-call into internal service - scoped to user's org/branch/role]
    D --> E[Data returned, formatted as natural-language answer with source reference]
    C -- Write request --> F[Assistant drafts proposed action]
    F --> G[AssistantActionConfirmCard shown to user]
    G --> H{User confirms?}
    H -- Yes --> I[Action executed through the SAME service/validation path as its native page]
    H -- No --> J[Proposal discarded, no side effect]
    I --> K[Result confirmed in chat, entity updated]
    E --> L[Conversation persisted]
    K --> L
    J --> L
```

The Assistant's write path deliberately reuses each feature's existing service-layer validation (per `11-data-flow-diagrams.md`'s tenant-scoping/permission flow) rather than having its own — this is what keeps FR-9.3's guarantee ("never more capability than the user's role already allows") true by construction rather than by convention.

## AI Prediction Logging Contract (applies to all six modules above)

Every module above shares one non-negotiable rule, restated from FR-8.7: **no AI output reaches a user's screen without first being written to `ai_predictions`** (or `ai_recommendations` for the Recommendation Engine), including `model_version`, a summary of inputs used, the confidence score, and a generated explanation. This is what makes FR-8.8 (historical prediction view) and future model-retraining/accuracy-tracking possible — it is enforced at the service layer, not left to each module's discretion.
