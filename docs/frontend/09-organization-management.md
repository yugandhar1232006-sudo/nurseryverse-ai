# 7E — Organization Management

## Architecture

```
lib/api/organizations.ts        + createOrganization/updateOrganization/archiveOrganization/
                                   updateOrganizationSettings/transferOwnership (Module 4 /orgs/*)
lib/api/branches.ts              + getBranch/createBranch/updateBranch/archiveBranch (Module 4
                                   /branches/*)
lib/api/employees.ts             New: inviteEmployee/getEmployee/updateEmployeeProfile/
                                   transferEmployeeBranches/deactivateEmployee/reactivateEmployee
                                   (Module 4 /employees/* action routes -- operate on employee_id)
lib/api/admin.ts                 New (starts small, grows in 7O): listRoles/searchUsers/
                                   getEffectivePermissions (Module 13 /admin/* reads 7E needs)
lib/organization/queries.ts      organizationKeys + useRolesQuery/useUsersQuery/useBranchQuery/
                                   useEffectivePermissionsQuery
lib/organization/mutations.ts    11 mutation hooks: create/update/archive org, update org settings,
                                   create/update/archive branch, invite/update/transfer/deactivate/
                                   reactivate employee
lib/validation/organization.ts   Zod schemas + FormValues types for every 7E form

components/organization/
  create-organization-form.tsx   Onboarding: POST /orgs -- see "The org-less gap" below
  org-profile-card.tsx           Name/contact/logo -- read-only or editable per org:write
  org-settings-card.tsx          Currency/timezone/branding color/email sender identity/SMS toggle
  branches-panel.tsx             List + create/edit/archive, each gated on branch:write/branch:delete
  branch-form-dialog.tsx         Full 7-day operating-hours editor
  employees-panel.tsx            Real GET /admin/users list (see "Two employee reads" below)
  invite-employee-dialog.tsx     Real role/branch pickers from GET /admin/roles + GET /branches
  employee-detail-dialog.tsx     On-demand effective-permissions, branch transfer, deactivate/
                                   reactivate

components/ui/alert-dialog.tsx   New shadcn primitive (needed `npm install
                                   @radix-ui/react-alert-dialog`) -- the standard destructive-
                                   confirmation pattern for the rest of Phase 7 (archive branch,
                                   void invoice, delete scheduled report, etc.)

app/(app)/settings/page.tsx      Rewritten from a ComingSoon placeholder. org_id === null ->
                                   CreateOrganizationForm only; otherwise a real 4-tab surface
                                   (Organization / Branches / Employees / Notifications --
                                   Notifications stays ComingSoon, deferred to 7M by design)
components/dashboards/no-reporting-access.tsx  + an org_id === null branch (see below)
```

## The org-less gap (a real product hole this phase closed, not a 7E kickoff line item)

`POST /auth/signup` never creates an organization -- every new account starts with `org_id: null`
and `permissions: []`. Before this phase, there was **no frontend entry point at all** to the real,
already-implemented `POST /orgs` route (which atomically makes the caller Owner of a brand-new org --
see `apps/api/app/api/routes/organizations.py`'s own docstring). A fresh signup was permanently
stuck: Settings was a `ComingSoon` stub, the Dashboard showed `NoReportingAccess`'s generic
no-permissions copy, and there was no path forward. This was found by reading the actual backend
route list against what 7B/7C/7D shipped, not from the kickoff spec (which assumes an org already
exists). Fixed with `CreateOrganizationForm`, rendered by `SettingsPage` whenever
`user.org_id === null`, and a matching early-return branch in `NoReportingAccess` ("Set up your
organization" with a link to Settings, instead of the generic "reporting isn't part of your role"
message that would otherwise be technically true but misleading for this specific case).

## Two employee reads, on purpose

`GET /employees` (`EmployeeResponse`) carries `user_id` but no name, email, status, department, or
position -- there's nothing display-ready to build an Employees list from. The real join lives at
`GET /admin/users` (`AdminUserResponse`), which is what `EmployeesPanel` actually renders. Despite
living under the `/admin/*` path prefix (Module 13/7O's territory), this route and
`GET /admin/users/{id}/effective-permissions` are both gated on `employees:read`, not an admin-only
permission (confirmed directly in `apps/api/app/api/routes/admin.py`) -- so any Branch Manager who
can see the Employees tab at all can load them. `useEffectivePermissionsQuery` (real role_code/
branch_ids/is_org_wide) is deliberately fetched only when a specific employee's detail dialog opens,
not eagerly per list row, to avoid an N+1 request pattern against a list that can hold dozens of
employees.

## Permission model (real, not invented)

Per `docs/ux/07-role-permission-matrix.md`: `org:read` and `branch:read` are granted **R** to every
role, so the Organization and Branches tabs are always visible (write actions inside them are
individually gated on `org:write`/`branch:write`/`branch:delete`). `employees:read`/`write`/`delete`
are Owner/Org Admin/Branch Manager only -- `SettingsPage` gates the whole Employees tab on
`employees:read` at the route level (not inside `EmployeesPanel`), so a Horticulturist or Sales Staff
user never even triggers a `GET /admin/users` request for data they can't see.

## A real defect found and fixed: org-creation success didn't unstick the UI

**The defect:** `useCreateOrganizationMutation`'s first version called
`queryClient.invalidateQueries({ queryKey: authKeys.me() })` on success, following the same pattern
as 7B's `useConfirmEmailVerificationMutation`. `invalidateQueries` only marks a query stale and
refetches it if an *active observer* is currently mounted. `useMeQuery()` is only ever mounted on the
Account page (`app/(app)/account/page.tsx`) -- nowhere near Settings, where `CreateOrganizationForm`
renders. The Settings page reads `org_id` straight from `useSessionStore`, which `invalidateQueries`
never touches directly.

**Root cause:** an incorrect assumption that *any* invalidation of `authKeys.me()` would propagate
to the session store, when the actual sync only happens via `useMeQuery`'s own `useEffect`, and only
while that hook is mounted somewhere.

**How it was found:** a Vitest/RTL test
(`components/organization/__tests__/organization.test.tsx`, "creates the organization, then
re-fetches /auth/me and swaps to the real tabbed settings UI") drove the real form against a real
`apiClient` call through MSW, then asserted the tabbed UI appeared -- it timed out because nothing
had actually re-synced the store.

**The fix:** `useCreateOrganizationMutation`'s `onSuccess` now calls
`queryClient.fetchQuery({ queryKey: authKeys.me(), queryFn: getMe })` (forces the real request
unconditionally, no observer required) and then `useSessionStore.getState().setUser(me)` directly --
the same synchronous-mirror pattern `useMeQuery`'s effect uses, just invoked explicitly instead of
depending on some other page happening to have the hook mounted.

**Regression coverage:** the test above now passes; it's part of the 7E suite that runs on every
future regression pass.

**Not touched:** `lib/auth/mutations.ts`'s `useConfirmEmailVerificationMutation` has this same latent
gap (nothing mounts `useMeQuery` on `/verify-email` either), but 7B is approved/frozen and the
consequence there is materially milder -- a "verified" banner that clears a little later rather than
a user stuck mid-onboarding with no path forward. Documented here rather than silently fixed in a
completed phase, per the kickoff's defect policy ("do not modify completed backend/frontend modules
unless genuinely required").

## A real TypeScript defect class found and fixed: Zod `.and()` breaks RHF's `Path<T>`

**The defect:** `branchSchema` was originally built as `z.object({...}).and(z.object({ hours: ... }))`
so the flat fields and the per-weekday `hours` record could be composed separately. This produced 13
`error TS2719: Two different types with this name exist, but they are unrelated` errors, all on
`FormField`'s `control` prop wherever a nested `hours.${day}.*` path was used.

**Root cause:** react-hook-form's `Path<T>`/`Control<T>` generic machinery (used to type-check
`FormField`'s `name` prop against the schema) does not flatten Zod intersection (`ZodIntersection`)
types the same way it flattens a single `z.object`. Two structurally-compatible but nominally
different `Control<...>` instantiations resulted, one at the top-level `useForm` call and one wherever
a nested-path `FormField` was type-checked, and TypeScript refused to unify them.

**The fix:** `branchSchema` is now a single flat `z.object({ ..., hours: z.record(...) })` with no
`.and()`. Same real backend contract, same runtime validation, no intersection type.

**A related class, same root symptom:** `inviteEmployeeSchema`/`reactivateEmployeeSchema`'s
`branch_ids: z.array(z.string()).default([])` and `branchSchema`'s original
`latitude/longitude: z.union([z.coerce.number()..., z.literal("")])` both split a schema's *input*
type (what a raw, not-yet-validated form value looks like) from its *output* type (what
`zodResolver` produces after parsing) -- `.default()` makes a field optional on input but required on
output; `z.coerce.number()` makes a field `unknown` on input but `number` on output. Passing a single
`z.infer<...>` generic to `useForm<T>` while `zodResolver` internally needs `Resolver<Input, ...,
Output>` produced `error TS2322`/`TS2345` mismatches on every affected form (`branch-form-dialog.tsx`,
`invite-employee-dialog.tsx`, `employee-detail-dialog.tsx`). Fixed by removing the asymmetry instead
of fighting the generics: `branch_ids` has no `.default()` (every caller already supplies
`branch_ids: []` in `defaultValues`), and `latitude`/`longitude` are plain `z.string()` fields with a
`.refine()` for range validation, coerced to `number | null` once, explicitly, at submit time in
`onSubmit` -- matching how the field actually behaves as an `<Input>` value anyway.

**Also found while fixing the above:** the new React Compiler ESLint rule flagged
`employee-detail-dialog.tsx`'s `useEffect(() => { if (permsQuery.data) setSelectedBranchIds(...) },
[permsQuery.data])` as a synchronous-setState-in-effect (cascading render risk). Replaced with React's
documented "adjusting state when a prop changes" pattern -- comparing `permsQuery.data` against a
`syncedPermsData` state value directly in the render body -- which is not an Effect and does not
cascade.

**Total defect count from this pass:** 27 `error TS2322`/`TS2345`/`TS2719` TypeScript errors and 1
`react-hooks/set-state-in-effect` ESLint error, all fixed; 3 fixture-file `Record<string, never>`
typing issues in `test/fixtures/dashboards.ts` (pre-existing from 7D, only surfaced once 7E's stricter
build ran clean enough to reach them) fixed by casting to the backend's genuinely opaque
`Record<string, never>` schema shape rather than fighting it, matching the cast `plant-tab.tsx`
already used for the same real backend looseness (`by_species`/`AtRiskPlantResponse.result` are
untyped free-form dicts in the OpenAPI schema itself, not a frontend gap).

## UI states

Every 7E screen implements loading (`Skeleton`), empty (`EmptyState`), error-with-retry
(`ErrorState`), and permission-denied (`PermissionGate` fallback) states using the same 7A primitives
as 7D, not bespoke per-screen implementations. Destructive actions (archive branch, remove employee)
use the new `AlertDialog` rather than the plain `Dialog`, matching its stricter "must explicitly
choose Cancel or the destructive action" semantics.

## Testing

- **Vitest/RTL** (`components/organization/__tests__/organization.test.tsx`, 7 tests, all passing):
  org-less onboarding form rendering; the org-creation-then-unlocks-tabs flow (the test that caught
  the defect above); Employees tab permission gating; real branch list + archive-through-AlertDialog;
  real employee list (name/email from `GET /admin/users`) + invite flow; branch-list error state +
  retry; org profile read-only rendering for a role with no `org:write`.
- **Full regression**: all 23 Vitest/RTL test files (142 tests: 135 from 7A-7D + 7 new) pass.
  `npx tsc --noEmit` clean. `npx eslint .` clean (0 errors; 1 pre-existing `react-hooks/
  incompatible-library` warning on `form.watch()`, informational only -- React Compiler correctly
  declining to memoize around React Hook Form's mutable API, not a defect). `npx next build`
  production build succeeds.
- **Playwright** (`e2e/organization.spec.ts`, 3 tests): written and reviewed against the real
  components/routes; collected successfully (`npx playwright test --list` resolves all 3); **not
  execution-verified** in this sandbox -- no Chromium binary installed and no Postgres/Docker, the
  same disclosed constraint as `e2e/auth.spec.ts`/`e2e/shell.spec.ts`/`e2e/dashboards.spec.ts`.
  Covers: a fresh signup creating a real org and seeing the tabbed settings UI unlock as Owner; that
  same Owner creating a real branch; the auth-required redirect. Branch/Employee CRUD against real
  component code is additionally covered by the Vitest/RTL suite above with MSW-mocked network
  responses.

## Known limitations

- `OrgSettingsCard`'s branding-color picker is a native `<input type="color">` plus a synced hex text
  field -- no palette/preset picker, since the backend only stores a single hex string
  (`branding_primary_color`) and doesn't define a preset list.
- `EmployeeDetailDialog`'s branch-transfer checkbox list re-fetches `GET /branches` from the shell's
  own `useBranchesQuery` cache rather than a dedicated endpoint; fine at expected branch-count scale
  (tens, not thousands) per the same assumption 7C's `BranchSelector` already makes.
- Employee "Employee Profile" editing (name/department/position beyond invite-time fields) is
  currently accessible via `updateEmployeeProfile`/`useUpdateEmployeeProfileMutation` in
  `lib/organization/mutations.ts`, but no form UI calls it yet in this phase -- `EmployeeDetailDialog`
  covers status/branch-scope changes, which are the actions the 7E kickoff's own "Employee Status" /
  "Branch Assignment" / "Employee Transfer" line items name. A dedicated profile-edit form is a
  small, additive follow-up, not a blocker.
