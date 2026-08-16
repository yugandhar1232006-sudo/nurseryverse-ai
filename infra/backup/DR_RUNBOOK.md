# Disaster Recovery Runbook

Phase 6 Module 14 (Production Readiness). Operationalizes docs/architecture/10-devops.md §5/§6 and docs/architecture/05-database-architecture.md §8 into concrete, executable steps using this directory's scripts. Read this document fully before an actual incident — the quarterly drill (§6 below) is when it should first be read carefully, not during a live outage.

## 1. Targets

RTO (Recovery Time Objective): 4 hours. RPO (Recovery Point Objective): 15 minutes, bounded by `archive_timeout = 300` in `postgresql.conf.snippet` (a WAL segment archives at least every 5 minutes even under light write load, leaving margin against the 15-minute target). These are the same targets docs/architecture/10-devops.md §6 sets for a single-reference-customer v1 deployment — revisit if an Enterprise SLA commitment requires tighter numbers for a specific customer.

## 2. What triggers this runbook

Any incident where the production database is lost, corrupted, or unreachable in a way that cannot be resolved by simply restarting the `postgres` container against its existing volume (a full host loss, a corrupted data directory, an accidental `DROP TABLE`/`DELETE` in production, a botched migration with no forward fix). For a simple container crash/restart, do NOT run this runbook — restart the container and confirm via `/readyz` first; this runbook is for when that no longer works.

## 3. Recovery procedure

### Step 1 — Provision a new host

From the same Docker Compose definitions this repository already contains (`docker-compose.yml` + `docker-compose.prod.yml`), per docs/architecture/10-devops.md §6: bring up a fresh host (or reuse the existing one if only the data directory, not the host itself, was lost), install Docker/Compose, clone this repository (or pull the pinned release tag), and provision `.env` with the same production secrets the incident host had (pulled from the deployment platform's secret store — never committed to this repository).

Do **not** run `docker compose up` yet — bringing up `api`/`worker`/`beat` against an empty/corrupt database before the restore below completes would let them start writing (or serving stale reads) against bad data.

### Step 2 — Restore the database

Bring up only the `postgres` service:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres
```

Wait for it to report healthy (`docker compose ps` — the `pg_isready` healthcheck from `docker-compose.yml`), then run `restore_database.sh` (this directory) from a host that can reach it:

```bash
export POSTGRES_HOST=<new-host> POSTGRES_PORT=5432 \
       POSTGRES_DB=nurseryverse POSTGRES_USER=nurseryverse PGPASSWORD=<from secret store> \
       BACKUP_S3_BUCKET=s3://nurseryverse-backups-prod

# Plain restore -- most recent daily backup, no PITR:
./restore_database.sh --confirm

# Point-in-time recovery -- replay WAL forward to a specific moment
# (e.g. "restore to just before the bad DELETE ran at 14:32 UTC"):
./restore_database.sh --target-time "2026-08-13 14:30:00 UTC" --confirm
```

`restore_database.sh` without `--confirm` prints the restore plan (which backup, which mode, which database gets dropped) and exits without changing anything — run it once without `--confirm` first to sanity-check the plan before re-running with it.

For the PITR path, `restore_database.sh` writes `postgresql.auto.conf`/`recovery.signal` into `PGDATA` and then tells you to (re)start the Postgres server process — do that now (`docker compose restart postgres` against the same data volume the script wrote into). Watch the container logs: Postgres will log WAL segments being replayed, then a "recovery stopping before/at ..." message, then "database system is ready to accept connections" once it promotes.

### Step 3 — Redeploy the last known-good application images

```bash
export API_IMAGE_TAG=ghcr.io/<org>/nurseryverse-api:<last-known-good-tag>
export WORKER_IMAGE_TAG=ghcr.io/<org>/nurseryverse-worker:<last-known-good-tag>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

"Last known good" is whatever tag was running in production immediately before the incident — check the deployment platform's own release history, not necessarily the newest tag in the registry (if the incident was *caused* by a bad release, redeploying that same bad release would just reproduce the problem).

### Step 4 — Verify

1. `curl -f https://<domain>/readyz` — must return `200 {"status": "ok", "database": "reachable"}`. A `503` here means stop and re-diagnose before proceeding; do not cut traffic over to a instance that isn't ready.
2. Smoke-test checklist (minimum, run against the restored environment before cutover):
   - Log in as a known test user (Module 2 auth).
   - Load an organization's dashboard (Module 12) and confirm data looks like the target restore point, not stale/empty.
   - Create one plant record and confirm it appears in its digital twin timeline (Modules 6/7) — proves writes work, not just reads.
   - Check `/metrics` is being scraped and `worker`/`beat` containers are healthy (`docker compose ps`) — confirms the async/background half of the system, not just the request path, is alive.
3. Check `worker`/`beat` logs for the two scheduled sweeps (`app.workers.retry_due_notifications`, `app.workers.run_due_scheduled_reports`) actually firing on schedule post-restore.

### Step 5 — Cut over

Point DNS (or the load balancer, depending on the deployment platform) at the new host's `nginx` service. Keep the old/incident host running (but not receiving traffic) until the new one has been stable for a reasonable observation window, in case a rollback of the cutover itself is needed.

## 4. Rollback (of a bad deploy, not a full DR event)

Per docs/architecture/10-devops.md §4: because images are tagged and immutable, rolling back a bad *code* release (no accompanying schema rollback needed, the common case) is just re-pointing `API_IMAGE_TAG`/`WORKER_IMAGE_TAG` at the previous tag and re-running Step 3 above — no database restore required. Only fall back to the full restore procedure (Steps 1-2) when the release's own migration was destructive and not backward-compatible (flagged as such in that release's own notes, per §4's "rollback requires a DB restore" convention) or when data itself (not just code) was the thing that broke.

## 5. Testing this runbook

Per docs/architecture/10-devops.md §6: exercise this procedure quarterly, against a non-production environment — provision a throwaway host, restore the most recent production backup into it (`restore_database.sh` works identically against a non-prod target; only the `POSTGRES_HOST`/`BACKUP_S3_BUCKET` differ), and time the whole thing end-to-end against the 4-hour RTO target. A drill that reveals the real elapsed time is closer to 4 hours than comfortable is itself a valid finding — file it, don't just note "it eventually worked."

Record, per drill: date run, elapsed time for each step above, whether the RTO/RPO targets were met, and any script/runbook fix that came out of it (a drill that changes nothing about this document going forward is a sign the drill wasn't looked at critically enough).

## 6. What this runbook does NOT cover

- Cloudinary-hosted media (plant images, generated invoices/reports/passports) — per docs/architecture/09-infrastructure.md §6, these live entirely in Cloudinary, not in Postgres or this backup pipeline. Cloudinary's own backup/redundancy is outside this repository's scope; verify Cloudinary's own SLA/backup posture separately as part of any real DR planning, not assumed here.
- Redis — used only as a cache, Celery broker/result-backend, rate-limit token buckets, WS pub/sub, and refresh-token revocation list (docs/architecture/09-infrastructure.md §4), all of which are either derivable from Postgres or acceptable to lose (a cold cache repopulates; an in-flight Celery task is retried; a rate-limit bucket resets, which is safe by construction). Not backed up, deliberately.
- This runbook, `backup_database.sh`, `wal_archive.sh`, and `restore_database.sh` are **not independently run-verified** — this development sandbox never had a live Postgres, `aws`-cli, `pg_dump`/`pg_restore`, or object storage available (disclosed in docs/architecture/30-module14-production-readiness.md). Every script passed a `bash -n` syntax check and manual review against documented `pg_dump`/`pg_restore`/Postgres-recovery semantics, but none have executed against a real database. Treat the first quarterly drill (§5) as this runbook's actual validation, not this document's existence.
