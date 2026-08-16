# User Personas

Five personas cover the platform's primary roles. Every functional requirement and user story is written against one or more of these. RBAC roles in the Permission Matrix (`10-permission-matrix.md`, Phase 2) map directly onto them, though an Org Admin may create custom roles that blend responsibilities.

---

## 1. Renata — Nursery Owner / Multi-Branch Operator

**Role in system:** Org Owner / Org Admin
**Age/background:** 45, owns a 4-branch wholesale-and-retail nursery group, came up through horticulture but now spends most of her time on the business side.
**Goals:** know, at a glance, how each branch is performing (revenue, inventory health, plant loss); reduce the specimen losses that quietly erode margin; make purchasing and staffing decisions based on data instead of the branch manager's gut feel; eventually franchise/expand and needs the business to run on repeatable systems, not tribal knowledge.
**Pain points today:** each branch manager keeps records differently (some paper, some spreadsheets); she finds out about a disease outbreak or a dead specimen crop days after it happened; she has no reliable revenue forecast, so cash-flow planning is reactive; onboarding a new branch manager means re-explaining ad hoc processes.
**Success criteria:** opens one dashboard and sees all branches' health/revenue/inventory status same-day; gets proactively alerted to AI-flagged disease/water risk before it becomes a write-off; can pull a defensible revenue forecast for a bank/investor conversation.
**Primary devices:** desktop (dashboard review), phone (alerts on the go).

---

## 2. Marcus — Branch Manager

**Role in system:** Branch Manager
**Age/background:** 34, runs the day-to-day of a single branch — staffing, stock, sales floor, and reporting up to Renata.
**Goals:** keep his branch's inventory accurate without spending hours on manual counts; make sure staff log plant health/watering consistently; hit his branch's sales targets; not get blindsided by a stockout or a preventable plant loss.
**Pain points today:** inventory counts are always slightly wrong by the time anyone checks them; he relies on staff remembering to water/check plants rather than a system that tells them what's due; he has no easy way to show Renata what's actually happening at his branch without compiling a report manually.
**Success criteria:** a daily view of what needs attention (watering due, low stock, AI health flags) that staff can act on directly; sales and inventory numbers he trusts without double-checking; less time spent building reports for the owner.
**Primary devices:** tablet on the floor, desktop in the office.

---

## 3. Priya — Horticulturist / Plant Care Specialist

**Role in system:** Staff — Plant Care
**Age/background:** 27, degree in horticulture, responsible for day-to-day plant health monitoring, watering, and treatment across the branch's stock.
**Goals:** catch disease and stress early, before it spreads or kills a specimen; spend her time on plant care, not paperwork; trust that the system's AI suggestions are a genuine second opinion, not noise she has to double-check anyway.
**Pain points today:** by the time a disease is visually obvious, it's often already spread to nearby plants; logging health observations on paper means the record is disconnected from the plant by the time anyone reviews it; she has no easy way to look up a species' specific care requirements in the moment.
**Success criteria:** can photograph a plant on her phone and get an AI disease read with a confidence level in seconds; the system tells her what's overdue for watering/inspection instead of her having to remember; every observation she logs becomes part of that plant's permanent record automatically.
**Primary devices:** phone/tablet, camera-first workflows.

---

## 4. Devon — Sales / POS Staff

**Role in system:** Staff — Sales
**Age/background:** 22, part-time/seasonal retail staff, handles checkout and customer questions on the sales floor.
**Goals:** ring up a sale quickly and correctly; answer basic customer questions about a plant (care, price, availability) without having to ask a manager; not accidentally sell something that's already been sold or isn't actually in stock.
**Pain points today:** the POS system and the "is this plant actually still here" reality don't always match; he has no quick way to pull up care info for a customer asking about a specific plant.
**Success criteria:** checkout reflects real-time inventory so he's not overselling; scanning a plant's QR code brings up its passport/care info instantly for a customer conversation; sales he completes update inventory and the owner's dashboard without extra steps.
**Primary devices:** tablet/desktop POS terminal.

---

## 5. Alex — Platform System Administrator (NurseryVerse staff, not a customer)

**Role in system:** Platform Admin (cross-tenant, internal)
**Age/background:** NurseryVerse's own operations/support engineer, responsible for onboarding new nursery customers and keeping the platform healthy.
**Goals:** onboard a new nursery org without custom engineering work; monitor system health, AI model performance, and background job failures across all tenants; investigate support issues (with proper tenant-scoped audit access, not blanket data access).
**Pain points today:** N/A — this persona defines requirements for the (out-of-customer-scope but necessary) internal admin tooling and observability the platform needs to actually operate as a business.
**Success criteria:** can provision a new Org/Branch structure quickly; has visibility into job queue health, AI inference error rates, and per-tenant usage against plan limits; can support a customer issue without needing raw database access.
**Primary devices:** desktop, internal admin console (not part of the customer-facing app; noted here so architecture accounts for it).
