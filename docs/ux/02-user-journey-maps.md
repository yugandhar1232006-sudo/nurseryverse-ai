# User Journey Maps

One primary journey per persona (from `docs/product/03-user-personas.md`), covering the highest-value recurring workflow for that role. Page IDs reference `01-sitemap.md`.

## Renata (Org Owner) — "Monday morning cross-branch review"

| Step | Action | Page(s) | Emotion / risk if missing |
|---|---|---|---|
| 1 | Logs in, lands on org-wide dashboard | PG-03 → PG-07 | Wants an immediate read on the whole business, not a login wall to a single branch |
| 2 | Scans per-branch revenue, inventory alerts, AI health-risk summary cards | PG-07 | Frustration if she has to click into each branch to get this |
| 3 | Notices Branch 3 has an elevated survival-risk flag; drills in | PG-07 → PG-31 (filtered to branch) | Needs the "why," not just a number — explanation matters |
| 4 | Opens the specific at-risk plants, reviews AI reasoning and recent health history | PG-31 → PG-22 → PG-26 | Trust breaks down if the AI can't justify itself |
| 5 | Messages/assigns the branch manager to inspect (via notification or assistant) | PG-10 or PG-09 | Wants to close the loop without leaving the app |
| 6 | Checks revenue forecast for the quarter before a planning call | PG-32 | Needs a defensible number, not a black box |
| 7 | Exports a summary report for a bank/investor conversation | PG-51 → PG-52 | Export must be presentable, not a raw data dump |

**Success:** the entire review happens without leaving the dashboard-and-drill-down pattern; she never has to ask a branch manager for numbers manually.

## Marcus (Branch Manager) — "Daily branch open"

| Step | Action | Page(s) | Emotion / risk if missing |
|---|---|---|---|
| 1 | Logs in, lands on his branch's dashboard (branch pre-selected, no org-wide noise) | PG-03 → PG-08 | Should not have to filter out other branches every day |
| 2 | Reviews today's action list: watering due, low stock, confirmed disease reports | PG-08 → PG-34 / PG-36 / PG-29 | This list is the job — if it's wrong, he stops trusting the system |
| 3 | Assigns/checks off watering tasks as staff complete them | PG-34 | Needs real-time reflection of staff logging, not stale data |
| 4 | Reviews a disease report a staff member flagged overnight, confirms and assigns treatment | PG-29 → PG-30 | Needs to act fast; friction here directly costs plants |
| 5 | Checks inventory against a supplier delivery arriving today | PG-49 → PG-50 (receive) → PG-36 | Receiving stock must update inventory immediately |
| 6 | End of day: reviews sales summary against target | PG-40 | Wants a number, not a spreadsheet export chore |

**Success:** the branch dashboard is the single place he starts and returns to all day; every other page is a drill-down from it.

## Priya (Horticulturist) — "Field inspection round with photo-first logging"

| Step | Action | Page(s) | Emotion / risk if missing |
|---|---|---|---|
| 1 | Logs in on phone, opens her assigned inspection/watering list | PG-03 → PG-34 | Needs mobile-first, low-friction entry |
| 2 | Scans a plant's QR code to open its digital twin directly | (QR scan) → PG-22 | Manual search would be too slow walking the floor |
| 3 | Notices leaf discoloration, takes a photo, submits for AI disease detection | PG-22 → PG-28 | Needs a fast answer, not a spinner she has to wait around for |
| 4 | Reviews AI result (condition + confidence), confirms or overrides, logs treatment | PG-28 → PG-30 | Needs to trust but verify — override must be easy, not buried |
| 5 | Logs a growth measurement on a nearby plant while she's there | PG-22 → PG-23 | One-trip logging — she won't come back later to log more |
| 6 | Logs a watering event against a zone | PG-25 → PG-35 | Should take seconds, not a full form |
| 7 | Checks the AI-recommended watering schedule for the rest of the day's round | PG-34 | Wants the system to tell her what's next, not rely on memory |

**Success:** she never has to switch to a desktop or fill out paperwork later — every observation is captured at the plant, in the moment.

## Devon (Sales Staff) — "Customer checkout with a plant question"

| Step | Action | Page(s) | Emotion / risk if missing |
|---|---|---|---|
| 1 | Logs in at the POS terminal | PG-03 → PG-39 | Needs to land directly on checkout, not a dashboard he doesn't use |
| 2 | Customer asks about a specific plant's care; Devon scans its QR code | PG-39 → PG-22 (read-only) | Needs care info surfaced instantly, not a manager lookup |
| 3 | Adds the plant to the sale via the same scan | PG-39 | Scan-to-cart should be one action, not scan-then-search |
| 4 | System blocks him from adding an already-sold item scanned by mistake | PG-39 (validation) | Prevents an awkward customer-facing error later |
| 5 | Completes sale, attaches to a returning customer's record | PG-39 → PG-42 (lookup) | Needs fast customer search, not a long form |
| 6 | Prints/emails receipt | PG-41 | Standard checkout expectation |

**Success:** the entire interaction, including the customer's care question, is handled from one screen without calling a manager over.

## Alex (Platform Admin, internal) — "Onboard a new nursery customer"

| Step | Action | Page(s) | Emotion / risk if missing |
|---|---|---|---|
| 1 | Logs into internal admin console (separate from customer-facing app) | Admin console (out of customer sitemap; noted in Architecture) | Must not require raw DB access for a routine task |
| 2 | Provisions a new Org, first Branch, and Owner account | Admin console → triggers PG-02-equivalent for the customer | Should be a guided flow, not manual SQL |
| 3 | Monitors AI inference error rate and job queue health post-launch | Admin console | Needs cross-tenant visibility that customers never get |
| 4 | Investigates a support ticket by viewing that tenant's audit log (scoped, not raw access) | Admin console → tenant-scoped audit view | Must never expose one tenant's data outside proper scoping, even to internal staff, without a deliberate support-access grant |

**Success:** onboarding and support are repeatable processes, not custom engineering — this journey is why FR/NFR requirements call out internal admin tooling explicitly even though it's not a customer-facing page in the sitemap.
