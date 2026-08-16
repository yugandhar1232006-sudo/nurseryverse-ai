# Role & Permission Matrix

## System Default Roles

| Role code | Name | Scope | Notes |
|---|---|---|---|
| `owner` | Org Owner | Entire Org, all Branches | Exactly one per Org; created at signup; cannot be deleted, only transferred |
| `org_admin` | Org Admin | Entire Org, all Branches | Same permission surface as Owner except billing ownership transfer and Org deletion |
| `branch_manager` | Branch Manager | Assigned Branch(es) only | Full operational control within assigned branches |
| `horticulturist` | Horticulturist / Plant Care | Assigned Branch(es) only | Plant/health/growth/environmental/watering focus; no financial access |
| `sales_staff` | Sales Staff | Assigned Branch(es) only | Sales/POS/customer focus; read-only on plants/inventory |
| `platform_admin` | Platform Admin (internal) | Cross-tenant, NurseryVerse-internal only | Not assignable within a customer Org; separate admin console, scoped support access only |

**Custom roles** (Growth/Enterprise tier, FR-1.5): Org Admin can compose a custom role from the atomic permissions below. Custom roles cannot exceed the permission ceiling of `org_admin` and cannot be granted cross-Org scope.

Permission format: `<module>:<action>`. Actions: `read`, `write` (create/update), `delete`, `approve` (confirm an AI-flagged or otherwise pending item), `export`.

## Permission Matrix

Legend: **F** = Full (all branches/org-wide), **B** = Branch-scoped (own assigned branch only), **R** = Read only, **–** = No access.

| Permission | Owner | Org Admin | Branch Manager | Horticulturist | Sales Staff |
|---|---|---|---|---|---|
| `org:read` | F | F | R | R | R |
| `org:write` | F | F | – | – | – |
| `org:delete` | F (Owner only) | – | – | – | – |
| `branch:read` | F | F | B | B | B |
| `branch:write` | F | F | – | – | – |
| `branch:delete` | F | F | – | – | – |
| `employees:read` | F | F | B | – | – |
| `employees:write` | F | F | B (non-admin roles only) | – | – |
| `employees:delete` | F | F | – | – | – |
| `roles:manage` (custom roles) | F | F | – | – | – |
| `species:read` | F | F | B | B | R |
| `species:write` | F | F | B | – | – |
| `species:delete` | F | F | – | – | – |
| `plants:read` | F | F | B | B | B |
| `plants:write` | F | F | B | B | – |
| `plants:transfer` | F | F | B | – | – |
| `growth:read` | F | F | B | B | – |
| `growth:write` | F | F | B | B | – |
| `health:read` | F | F | B | B | – |
| `health:write` | F | F | B | B | – |
| `disease:read` | F | F | B | B | – |
| `disease:write` | F | F | B | B | – |
| `disease:approve` | F | F | B | B | – |
| `ai_predictions:read` | F | F | B | B | – |
| `ai_predictions:run` (on-demand) | F | F | B | B | – |
| `ai_assistant:use` | F | F | B | B (read-focused) | B (read-focused) |
| `ai_assistant:confirm_write` | F | F | B | B (limited to health/watering) | – |
| `environmental:read` | F | F | B | B | – |
| `environmental:write` | F | F | B | B | – |
| `watering:read` | F | F | B | B | – |
| `watering:write` | F | F | B | B | – |
| `inventory:read` | F | F | B | B | B |
| `inventory:write` | F | F | B | – | – |
| `inventory:adjust` | F | F | B | – | – |
| `sales:read` | F | F | B | – | B |
| `sales:write` | F | F | B | – | B |
| `sales:void` | F | F | B | – | – |
| `customers:read` | F | F | B | – | B |
| `customers:write` | F | F | B | – | B |
| `invoices:read` | F | F | B | – | B |
| `invoices:write` | F | F | B | – | B (create only) |
| `invoices:void` | F | F | B | – | – |
| `suppliers:read` | F | F | B | – | – |
| `suppliers:write` | F | F | B | – | – |
| `suppliers:delete` | F | F | – | – | – |
| `purchase_orders:read` | F | F | B | – | – |
| `purchase_orders:write` | F | F | B | – | – |
| `purchase_orders:receive` | F | F | B | – | – |
| `notifications:read` | F | F | B | B | B |
| `notifications:manage_preferences` | F (self) | F (self) | B (self) | B (self) | B (self) |
| `reports:read` | F | F | B | – | – |
| `reports:export` | F | F | B | – | – |
| `passport:read` | F | F | B | B | B |
| `passport:generate` | F | F | B | B | – |
| `audit:read` | F | F | – | – | – |
| `settings:org` | F | F | – | – | – |
| `settings:branch` | F | F | B | – | – |
| `settings:billing` | F (owner-only for plan/payment method changes) | R | – | – | – |

## Permission Enforcement Notes

Every permission check is evaluated server-side on every request (never trusted from the client) via a `require_permission("<module>:<action>")` dependency, as defined in the Enterprise System Architecture document. Branch-scoped (`B`) permissions additionally require the target resource's `branch_id` to be in the requesting user's assigned-branches set — this is enforced both in the service layer and as a PostgreSQL row-level security policy (defense in depth, per NFR-4.3). `ai_assistant:confirm_write` is deliberately narrower than the underlying module permission for a role (e.g., Horticulturist can confirm assistant-proposed watering/health writes but not inventory or financial writes) — the Assistant never grants a user more capability than their existing role permissions already allow; it only offers a faster path to actions they could already take manually.
