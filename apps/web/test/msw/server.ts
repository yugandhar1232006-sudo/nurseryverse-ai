import { setupServer } from "msw/node";

import { handlers } from "./handlers";
import { shellHandlers } from "./shell-handlers";
import { dashboardHandlers } from "./dashboard-handlers";
import { organizationHandlers } from "./organization-handlers";
import { catalogHandlers } from "./catalog-handlers";
import { plantsHandlers } from "./plants-handlers";
import { digitalTwinHandlers } from "./digital-twin-handlers";
import { inventoryHandlers } from "./inventory-handlers";
import { customersHandlers } from "./customers-handlers";
import { salesHandlers } from "./sales-handlers";
import { passportHandlers } from "./passport-handlers";
import { aiHandlers } from "./ai-handlers";
import { reportsHandlers } from "./reports-handlers";
import { adminHandlers } from "./admin-handlers";

/**
 * Node-side MSW server for Vitest -- see test/setup.ts for lifecycle
 * hooks. `catalogHandlers` is listed *before* `shellHandlers` on purpose:
 * MSW resolves the first matching handler in registration order (a
 * per-test `server.use(...)` override still wins over either, since it
 * prepends), and `shellHandlers` already registers its own deliberately-
 * empty `GET /api/v1/species` stub for 7C's global-search fan-out (see
 * that file's own docstring -- "empty by default; tests override per
 * case"). Without this ordering, every 7F test relying on
 * `catalogHandlers`' real species fixture as its *default* (i.e. not
 * itself calling `server.use` for that route) would silently get the
 * search stub's empty page instead -- found via a real test failure
 * (`components/catalog/__tests__/species-catalog.test.tsx`, two tests
 * that never called `server.use` for `GET /species` were seeing "No
 * species yet" instead of the fixture). The same shadowing risk applies
 * to `shellHandlers`' `/plants`, `/customers`, and `/inventory` stubs
 * once 7G/7I/7J add their own dedicated handler files -- register those
 * ahead of `shellHandlers` too. `plantsHandlers` (7G) is the first of
 * these: it owns the real `GET /api/v1/plants` fixture, so it must sit
 * ahead of `shellHandlers`' empty search-fan-out stub for the same
 * reason `catalogHandlers` does. `inventoryHandlers` (7I) is the second,
 * for the identical reason against `GET /api/v1/inventory`.
 * `customersHandlers` and `salesHandlers` (7J) are the third and fourth --
 * `customersHandlers` owns the real `GET /api/v1/customers` fixture that
 * was previously shadowed by `shellHandlers`' empty search-fan-out stub;
 * `salesHandlers` doesn't shadow anything in `shellHandlers` but is kept
 * in the same group for locality with `customersHandlers`, both being
 * Module 9. `aiHandlers` (7L) doesn't shadow anything in `shellHandlers`
 * either (no `/ai/*` stub exists there) but is kept adjacent to
 * `passportHandlers` for locality, both being small single-file modules.
 * `adminHandlers` (7O) is registered last, next to `organizationHandlers`:
 * it deliberately does NOT redefine `GET /admin/roles`, `GET
 * /admin/users`, or `GET /admin/users/{id}/effective-permissions` --
 * `organizationHandlers` already owns those three real routes (borrowed
 * for 7E's Employees screen) -- so there is no overlap/shadowing between
 * the two files despite both touching `/api/v1/admin/*` (see
 * `admin-handlers.ts`'s own docstring for the full reasoning).
 */
export const server = setupServer(
  ...handlers,
  ...catalogHandlers,
  ...plantsHandlers,
  ...digitalTwinHandlers,
  ...inventoryHandlers,
  ...customersHandlers,
  ...salesHandlers,
  ...passportHandlers,
  ...aiHandlers,
  ...shellHandlers,
  ...dashboardHandlers,
  ...reportsHandlers,
  ...organizationHandlers,
  ...adminHandlers,
);
