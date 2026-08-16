# User Stories

Format: `US-<epic>.<n>` — As a `<persona>`, I want `<goal>`, so that `<benefit>`. Each story lists acceptance criteria and the Functional Requirements it satisfies. Personas reference `03-user-personas.md`; FR IDs reference `04-functional-requirements.md`.

## Epic A — Access & Onboarding

**US-A.1** — As Renata (Owner), I want to sign up and create my Org in one flow, so that I can start setting up my nursery without waiting on anyone. *Acceptance:* signup creates Org + Owner account + first login in a single guided flow; Org name, first Branch, and Owner credentials are captured. *Satisfies:* FR-2.1, FR-1.1.

**US-A.2** — As Marcus (Branch Manager), I want to receive an email invite with a role already assigned, so that I don't have to ask Renata what I can access. *Acceptance:* invite email contains a signup link pre-scoped to the assigned role and Branch(es); role is visible on first login. *Satisfies:* FR-3.1, FR-3.2.

**US-A.3** — As any user, I want to reset my password if I forget it, so that I'm not locked out. *Acceptance:* reset link is single-use, expires within a configurable window, and invalidates all existing sessions on successful reset. *Satisfies:* FR-1.3.

**US-A.4** — As Renata (Owner), I want to deactivate an employee's access immediately when they leave, so that former staff can't access nursery data. *Acceptance:* deactivation revokes all active sessions/tokens for that user within one refresh cycle; their historical actions remain in the audit log. *Satisfies:* FR-3.3, FR-3.4, FR-1.6.

## Epic B — Branch & Organization Setup

**US-B.1** — As Renata (Owner), I want to add a new Branch with its own address and settings, so that I can expand without the system conflating locations. *Acceptance:* new Branch has independent timezone, thresholds, and staff assignments; existing Branches are unaffected. *Satisfies:* FR-2.2, FR-2.3.

**US-B.2** — As Renata (Owner), I want a single dashboard showing all my Branches' key numbers side by side, so that I don't have to visit each branch's data separately. *Acceptance:* org dashboard shows per-branch revenue, inventory alerts, and AI health flags updated same-day. *Satisfies:* FR-2.4.

## Epic C — Species & Digital Twin

**US-C.1** — As Marcus (Branch Manager), I want to maintain a shared species catalog, so that staff aren't re-entering the same care info for every plant of that species. *Acceptance:* species record is reusable org-wide; editing a species does not require editing existing plant records individually. *Satisfies:* FR-4.1, FR-4.2.

**US-C.2** — As Priya (Horticulturist), I want every plant to get a unique QR-linked record when it's created, so that I can always pull up its full history by scanning it. *Acceptance:* QR code is generated at creation and printable; scanning it opens the plant's digital twin. *Satisfies:* FR-5.1, FR-5.2.

**US-C.3** — As Priya (Horticulturist), I want to see a plant's growth, health, environment, watering, and AI predictions in one place, so that I don't have to piece its story together from separate screens. *Acceptance:* digital twin view aggregates all linked records chronologically, with the most recent status prominent. *Satisfies:* FR-5.3.

**US-C.4** — As Marcus (Branch Manager), I want to transfer a plant to another branch and have that recorded, so that inventory stays accurate across locations. *Acceptance:* transfer updates the plant's current Branch and appends a transfer event to its history; both branches' inventory counts reflect the change immediately. *Satisfies:* FR-5.5.

## Epic D — Growth & Health Tracking

**US-D.1** — As Priya (Horticulturist), I want to log a growth measurement with a photo in under a minute, so that logging doesn't eat into my care time. *Acceptance:* growth log form requires only measurement + optional photo, mobile-optimized, submits in one screen. *Satisfies:* FR-6.1.

**US-D.2** — As Priya (Horticulturist), I want to see a plant's growth charted over time, so that I can spot a stalled or accelerating growth trend. *Acceptance:* growth timeline renders as both a chart and a list, filterable by date range. *Satisfies:* FR-6.2.

**US-D.3** — As Priya (Horticulturist), I want to log a health observation or disease report from my phone with a photo, so that the record is created at the point of observation, not from memory later. *Acceptance:* health/disease logging is available as a mobile-first flow; disease reports capture treatment and outcome fields. *Satisfies:* FR-7.1, FR-7.2, FR-7.3.

**US-D.4** — As Marcus (Branch Manager), I want to be notified when a serious disease report is confirmed, so that I can act before it spreads to nearby stock. *Acceptance:* confirmed disease report above the configured severity threshold triggers an in-app + email notification to relevant roles within the branch. *Satisfies:* FR-7.5, FR-17.1, FR-17.2.

## Epic E — AI Predictions & Assistant

**US-E.1** — As Priya (Horticulturist), I want to photograph a plant and get an AI read on possible disease, so that I catch problems before they're obvious to the eye. *Acceptance:* photo submission returns a prediction with named condition(s), confidence score, and recommended next step within 5 seconds; result is saved to the plant's record automatically. *Satisfies:* FR-8.1, FR-8.7.

**US-E.2** — As Renata (Owner), I want an AI-generated revenue forecast for each branch, so that I can plan cash flow and staffing ahead of time. *Acceptance:* forecast shows a projected revenue curve with a confidence interval, refreshed on a scheduled cadence and on demand. *Satisfies:* FR-8.5.

**US-E.3** — As Marcus (Branch Manager), I want the system to tell me which plants are at elevated survival risk, so that I know where to focus limited staff attention. *Acceptance:* a ranked, explained list of at-risk plants is available on the branch dashboard, with the contributing factors shown, not just a bare score. *Satisfies:* FR-8.3, FR-8.6.

**US-E.4** — As Priya (Horticulturist), I want an AI-recommended watering schedule per zone, so that I'm not guessing based on habit. *Acceptance:* recommendation reflects species baseline, recent environmental readings, and recent watering history; updates when new readings come in. *Satisfies:* FR-8.4, FR-10.3.

**US-E.5** — As Renata (Owner), I want to ask the AI Assistant business questions in plain language and get answers from my real data, so that I don't have to dig through reports myself. *Acceptance:* assistant answers questions like "which branch had the most plant loss last month" using live tenant data, scoped only to my Org. *Satisfies:* FR-9.1, FR-9.2.

**US-E.6** — As Marcus (Branch Manager), I want the AI Assistant to ask for my confirmation before it changes anything, so that I stay in control of my data. *Acceptance:* any assistant-proposed write action is shown as a preview requiring explicit confirm/cancel before execution. *Satisfies:* FR-9.3.

## Epic F — Inventory, Sales & Invoicing

**US-F.1** — As Devon (Sales Staff), I want the system to stop me from selling something that isn't actually in stock, so that I don't overpromise a customer. *Acceptance:* checkout performs a real-time availability check and blocks/warns before completing a sale of unavailable stock. *Satisfies:* FR-13.2.

**US-F.2** — As Devon (Sales Staff), I want to scan a plant's QR code at checkout, so that I can ring it up and show the customer its care info without manual lookup. *Acceptance:* QR scan at POS pulls up the plant record and adds it to the current sale in one action. *Satisfies:* FR-13.5, FR-5.2.

**US-F.3** — As Marcus (Branch Manager), I want low-stock items to notify me automatically, so that I don't discover a stockout when a customer asks for something. *Acceptance:* inventory falling below its configured threshold triggers a notification to relevant roles. *Satisfies:* FR-12.2, FR-17.1.

**US-F.4** — As Renata (Owner), I want to generate a wholesale invoice with net terms from a batch of sales, so that B2B customers are billed correctly. *Acceptance:* invoice generation supports selecting multiple sales, applying terms, and emailing a PDF to the customer. *Satisfies:* FR-15.1, FR-15.2.

## Epic G — Reporting & Compliance

**US-G.1** — As Renata (Owner), I want to generate a Plant Passport for a specimen plant, so that a wholesale buyer has verifiable provenance and health documentation. *Acceptance:* passport PDF includes species/provenance, health/treatment history summary, current status, and is linked from the plant's QR code. *Satisfies:* FR-18.1.

**US-G.2** — As Renata (Owner), I want to export sales and inventory reports to Excel, so that I can share numbers with my accountant. *Acceptance:* report export supports PDF, Excel, and CSV formats with consistent data across formats. *Satisfies:* FR-18.2.

**US-G.3** — As Alex (Platform Admin), I want an immutable audit log of every mutating action across the platform, so that I can investigate support issues and satisfy compliance requirements. *Acceptance:* audit log entries cannot be edited or deleted through any interface, including admin tooling. *Satisfies:* FR-19.1, FR-19.3.

## Epic H — Notifications & Settings

**US-H.1** — As Priya (Horticulturist), I want to control which notifications I get by email versus in-app, so that I'm not overwhelmed but don't miss anything critical. *Acceptance:* notification preferences are configurable per category and channel at the user level. *Satisfies:* FR-17.4.

**US-H.2** — As Renata (Owner), I want to manage my Org's billing plan and integration settings in one place, so that I'm not hunting through the app to change them. *Acceptance:* a single Settings area covers Org profile, billing/plan, and integration toggles (SMS, email sender). *Satisfies:* FR-20.1, FR-20.3.
