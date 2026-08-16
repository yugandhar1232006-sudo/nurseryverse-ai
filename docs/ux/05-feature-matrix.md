# Feature Matrix

Cross-reference of features against subscription tier (from BRD §5) and role. "●" = full access, "◐" = limited/read-only or capped, "—" = not available.

## Feature × Plan Tier

| Feature | Starter | Growth | Enterprise |
|---|---|---|---|
| Branches | 1 | up to 5 | unlimited |
| Employee seats | up to 3 | unlimited | unlimited |
| Species catalog & Plant Digital Twin | ● | ● | ● |
| Growth timeline & health history | ● | ● | ● |
| AI Disease Detection | ◐ (capped monthly scans) | ● | ● (+ custom model fine-tuning) |
| AI Growth / Survival / Water prediction | ◐ (capped) | ● | ● |
| AI Revenue Forecast | — | ● | ● |
| AI Recommendation Engine | — | ● | ● |
| AI Assistant | ◐ (capped conversations) | ● | ● |
| Inventory management | ● | ● | ● |
| Sales / POS | ● | ● | ● |
| Customers & Invoicing | ● | ● | ● |
| Supplier & Purchasing | ● | ● | ● |
| Notifications (in-app, email) | ● | ● | ● |
| Notifications (SMS) | — | ◐ (opt-in add-on) | ● |
| Reports (PDF/Excel/CSV) | ● | ● | ● |
| Plant Passport | ● | ● | ● |
| Audit log | ◐ (90-day retention) | ● (12-month) | ● (custom retention) |
| Custom roles (beyond system defaults) | — | ● | ● |
| SSO | — | — | ● |
| Data export / API access | ◐ (manual export) | ◐ (manual export) | ● (API access) |
| SLA-backed uptime | — | — | ● |

## Feature × Role (functional access, independent of plan)

| Feature area | Owner/Admin | Branch Manager | Horticulturist | Sales Staff |
|---|---|---|---|---|
| Org & Branch settings | ● | ◐ (own branch only) | — | — |
| Employee management | ● | ◐ (own branch, non-admin roles) | — | — |
| Species catalog | ● | ● | ◐ (read) | — |
| Plant Digital Twin — view | ● | ● | ● | ◐ (read, own branch) |
| Plant Digital Twin — create/edit | ● | ● | ● | — |
| AI Disease Detection | ● | ● | ● | — |
| AI Predictions dashboard | ● | ● | ◐ (read) | — |
| Revenue Forecast | ● | ◐ (own branch) | — | — |
| AI Assistant | ● | ● | ◐ (read-focused queries) | ◐ (read-focused queries) |
| Inventory | ● | ● | ◐ (read) | ◐ (read, for sale) |
| Sales / POS | ● | ● | — | ● |
| Customers | ● | ● | — | ● |
| Invoicing | ● | ◐ (own branch) | — | ◐ (create only) |
| Suppliers & Purchasing | ● | ● | — | — |
| Reports | ● | ◐ (own branch) | — | — |
| Audit log | ● | — | — | — |
| Notifications | ● | ● | ● | ● |

This is the functional summary; the authoritative, granular permission-by-permission definition is `07-role-permission-matrix.md`.
