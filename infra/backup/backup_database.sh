#!/usr/bin/env bash
#
# Phase 6 Module 14 (Production Readiness) -- daily logical backup.
# docs/architecture/10-devops.md §5: "automated daily logical backup +
# continuous WAL archiving, 30-day rolling retention plus monthly
# snapshots retained 12 months. Backups are stored in a separate
# object-storage location from the application's own Cloudinary media
# ... Backup jobs alert on failure (not just log it)."
#
# This script covers the "daily logical backup" half; wal_archive.sh
# (this directory) covers "continuous WAL archiving" -- together they're
# what makes restore_database.sh's point-in-time recovery possible (a
# logical backup alone only restores to the moment it was taken; WAL
# replay on top of it is what gets RPO down to 15 minutes per
# docs/architecture/10-devops.md §6).
#
# Intended invocation: a daily cron job / systemd timer / Kubernetes
# CronJob on a host with network access to both Postgres and the backup
# object-storage bucket -- NOT run inside the `api`/`worker` containers
# themselves (those have no reason to hold object-storage credentials).
#
# NOT independently run-verified: this development sandbox has neither a
# live Postgres nor `aws`/`pg_dump` available (disclosed in
# docs/architecture/30-module14-production-readiness.md) -- validated via
# `bash -n` syntax check and manual review only.
#
# Requires: pg_dump (matching the target Postgres major version -- 16,
# per docs/architecture/09-infrastructure.md §5), aws-cli v2 (or any
# S3-API-compatible equivalent -- MinIO, Backblaze B2, etc. all speak the
# same `aws s3` commands via --endpoint-url).
#
# Required environment variables:
#   POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, PGPASSWORD
#   BACKUP_S3_BUCKET       -- e.g. s3://nurseryverse-backups-prod
#   BACKUP_S3_ENDPOINT_URL -- optional; set for non-AWS S3-compatible storage
# Optional:
#   ALERT_WEBHOOK_URL      -- if set, POSTed to on failure (see alert_failure below)
#   BACKUP_RETENTION_DAYS  -- default 30
#   BACKUP_RETENTION_MONTHS -- default 12 (first-of-month snapshots only)

set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:?POSTGRES_HOST is required}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:?POSTGRES_DB is required}"
POSTGRES_USER="${POSTGRES_USER:?POSTGRES_USER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required, e.g. s3://nurseryverse-backups-prod}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
BACKUP_RETENTION_MONTHS="${BACKUP_RETENTION_MONTHS:-12}"

export PGPASSWORD

S3_OPTS=()
if [[ -n "${BACKUP_S3_ENDPOINT_URL:-}" ]]; then
    S3_OPTS+=(--endpoint-url "${BACKUP_S3_ENDPOINT_URL}")
fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DAY_OF_MONTH="$(date -u +%d)"
WORKDIR="$(mktemp -d)"
DUMP_FILE="${WORKDIR}/nurseryverse_${TIMESTAMP}.dump"

alert_failure() {
    local message="$1"
    echo "BACKUP FAILED: ${message}" >&2
    # "Backup jobs alert on failure (not just log it)" -- a webhook POST
    # (Slack incoming-webhook and PagerDuty Events API v2 both accept a
    # bare JSON body shaped close enough to this to work, or route through
    # whatever alerting integration the deployment actually uses) is the
    # generic mechanism; swapped for a real target (PagerDuty/Opsgenie/
    # Slack) at deploy time via ALERT_WEBHOOK_URL. If unset, this still
    # exits non-zero, which most schedulers (cron+MAILTO, systemd timers
    # via OnFailure=, a Kubernetes CronJob's own failure tracking) also
    # surface as a failure on their own -- but should not be relied on
    # alone in production, per the architecture doc's explicit "not just
    # log it."
    if [[ -n "${ALERT_WEBHOOK_URL:-}" ]]; then
        curl -fsS -X POST -H "Content-Type: application/json" \
            -d "{\"text\": \"NurseryVerse AI backup failure on ${POSTGRES_HOST}/${POSTGRES_DB} at ${TIMESTAMP}: ${message}\"}" \
            "${ALERT_WEBHOOK_URL}" || echo "additionally failed to POST to ALERT_WEBHOOK_URL" >&2
    fi
}
trap 'alert_failure "unexpected error at line ${LINENO}"; rm -rf "${WORKDIR}"' ERR
trap 'rm -rf "${WORKDIR}"' EXIT

echo "Starting logical backup of ${POSTGRES_DB}@${POSTGRES_HOST}:${POSTGRES_PORT} at ${TIMESTAMP}"

# Custom format (-Fc): compressed, and the only format pg_restore can
# selectively restore from / parallelize with -j -- plain SQL dumps
# can't do either, which matters once this database is large enough that
# restore time (not backup time) is what threatens the 4-hour RTO.
pg_dump \
    --host="${POSTGRES_HOST}" \
    --port="${POSTGRES_PORT}" \
    --username="${POSTGRES_USER}" \
    --dbname="${POSTGRES_DB}" \
    --format=custom \
    --compress=9 \
    --file="${DUMP_FILE}"

DUMP_SIZE_BYTES=$(stat -c%s "${DUMP_FILE}" 2>/dev/null || stat -f%z "${DUMP_FILE}")
if [[ "${DUMP_SIZE_BYTES}" -lt 1024 ]]; then
    alert_failure "dump file is suspiciously small (${DUMP_SIZE_BYTES} bytes) -- refusing to upload what is likely a truncated/empty backup"
    exit 1
fi
echo "pg_dump complete: ${DUMP_FILE} (${DUMP_SIZE_BYTES} bytes)"

# Daily object -- subject to BACKUP_RETENTION_DAYS pruning below.
DAILY_KEY="daily/nurseryverse_${TIMESTAMP}.dump"
aws s3 cp "${S3_OPTS[@]}" "${DUMP_FILE}" "${BACKUP_S3_BUCKET}/${DAILY_KEY}"
echo "Uploaded to ${BACKUP_S3_BUCKET}/${DAILY_KEY}"

# Monthly snapshot -- an explicit copy under monthly/, taken only on the
# 1st of the month, retained far longer (BACKUP_RETENTION_MONTHS) than
# the rolling daily set. A copy, not a second pg_dump run, so the monthly
# snapshot is byte-identical to that day's daily backup rather than a
# separately-timed (and therefore inconsistent-with-the-daily-set) dump.
if [[ "${DAY_OF_MONTH}" == "01" ]]; then
    MONTHLY_KEY="monthly/nurseryverse_${TIMESTAMP}.dump"
    aws s3 cp "${S3_OPTS[@]}" "${DUMP_FILE}" "${BACKUP_S3_BUCKET}/${MONTHLY_KEY}"
    echo "Uploaded monthly snapshot to ${BACKUP_S3_BUCKET}/${MONTHLY_KEY}"
fi

echo "Pruning daily/ objects older than ${BACKUP_RETENTION_DAYS} days"
CUTOFF_DAILY=$(date -u -d "-${BACKUP_RETENTION_DAYS} days" +%Y%m%d 2>/dev/null || date -u -v-"${BACKUP_RETENTION_DAYS}"d +%Y%m%d)
aws s3 ls "${S3_OPTS[@]}" "${BACKUP_S3_BUCKET}/daily/" | while read -r _ _ _ key; do
    [[ -z "${key}" ]] && continue
    OBJ_DATE="$(echo "${key}" | grep -oE '[0-9]{8}T[0-9]{6}Z' | cut -c1-8 || true)"
    [[ -z "${OBJ_DATE}" ]] && continue
    if [[ "${OBJ_DATE}" < "${CUTOFF_DAILY}" ]]; then
        echo "  deleting expired daily backup: ${key}"
        aws s3 rm "${S3_OPTS[@]}" "${BACKUP_S3_BUCKET}/daily/${key}"
    fi
done

echo "Pruning monthly/ objects older than ${BACKUP_RETENTION_MONTHS} months"
CUTOFF_MONTHLY=$(date -u -d "-${BACKUP_RETENTION_MONTHS} months" +%Y%m%d 2>/dev/null || date -u -v-"${BACKUP_RETENTION_MONTHS}"m +%Y%m%d)
aws s3 ls "${S3_OPTS[@]}" "${BACKUP_S3_BUCKET}/monthly/" | while read -r _ _ _ key; do
    [[ -z "${key}" ]] && continue
    OBJ_DATE="$(echo "${key}" | grep -oE '[0-9]{8}T[0-9]{6}Z' | cut -c1-8 || true)"
    [[ -z "${OBJ_DATE}" ]] && continue
    if [[ "${OBJ_DATE}" < "${CUTOFF_MONTHLY}" ]]; then
        echo "  deleting expired monthly snapshot: ${key}"
        aws s3 rm "${S3_OPTS[@]}" "${BACKUP_S3_BUCKET}/monthly/${key}"
    fi
done

echo "Backup complete."
