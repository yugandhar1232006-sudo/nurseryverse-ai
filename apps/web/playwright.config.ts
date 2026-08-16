import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the *real* authentication flow -- per the Phase 7B
 * kickoff's "Use Playwright for the real authentication flow against the
 * backend where practical. Do not mock the entire authentication system
 * for E2E tests," these tests hit an actually-running Next.js dev server
 * talking to an actually-running FastAPI backend + Postgres, with no MSW
 * and no stubbing. There is deliberately no `webServer` entry here that
 * auto-starts the Next.js app: unlike a typical Playwright setup, the
 * *backend* this app depends on also has to be running first (Postgres
 * migrated and seeded, Redis up, the FastAPI process serving
 * `NEXT_PUBLIC_API_BASE_URL`), and that's owned by `docker-compose.yml`
 * at the repo root, not by this app. Auto-starting only the frontend
 * would just produce a wall of "backend unreachable" failures that look
 * like broken tests rather than the missing-precondition they'd actually
 * be.
 *
 * Prerequisites to run this suite for real (see
 * docs/frontend/06-authentication.md's Testing section for the full
 * writeup, including why this sandbox itself cannot run it):
 *   1. `docker compose up postgres redis api` from the repo root (or the
 *      full stack) -- migrated + seeded per apps/api's own tooling.
 *   2. `npm run dev` in apps/web, or `npm run build && npm run start`.
 *   3. A seeded test user matching E2E_TEST_EMAIL/E2E_TEST_PASSWORD below
 *      (see e2e/auth.spec.ts's top-of-file docstring for the exact
 *      account this suite expects to exist).
 *
 * PLAYWRIGHT_BASE_URL defaults to the app's own default dev port.
 */
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // auth state (lockouts, session revocation) is shared/mutable server-side; keep this suite serial
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
