#!/usr/bin/env bash
#
# Phase 6 Module 14 (Production Readiness) -- restore + point-in-time
# recovery. docs/architecture/10-devops.md §6's DR runbook step 2:
# "restore the database from the most recent backup + WAL replay to the
# target point in time." Two modes:
#
#   1. Plain restore (no --target-time): restores the most recent (or a
#      given --backup-key) logical dump only. Point-in-time is whatever
#      moment that dump was taken at.
#   2. Point-in-time recovery (--target-time set): restores the dump,
#      then configures Postgres to replay archived WAL forward from that
#      dump up to (and stopping at) --target-time -- this is what
#      achieves the 15-minute RPO target, since the daily dump alone can
#      be up to 24h stale.
#
# DESTRUCTIVE: drops and recreates the target database. Requires
# --confirm (a bare re-run of the command with that flag added) -- a
# restore invoked without it prints what it WOULD do and exits 0 without
# touching anything, specifically so this can't be fat-fingered against a
# live database by a script/runbook-follower moving fast during an actual
# incident.
#
# NOT independently run-verified: no live Postgres, `aws`, `pg_restore`,
# or `pg_ctl` in this development sandbox (disclosed in
# docs/architecture/30-module14-production-readiness.md) -- validated via
# `bash -n` syntax check and manual review against documented pg_restore/
# recovery.signal semantics only. Per docs/architecture/10-devops.md §6
# ("the restore procedure is exercised on a defined cadence (quarterly)
# against a non-production environment"), this script's first genuine
# execution should be that first quarterly drill, not an actual incident.
#
# Usage:
#   restore_database.sh [--backup-key daily/nurseryverse_<ts>.dump] \
#                        [--target-time "2026-08-13 14:30:00 UTC"] \
#                        --confirm
#
# Required environment variables:
#   POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, PGPASSWORD
#   BACKUP_S3_BUCKET, PGDATA (only required for --target-time / PITR mode
#     -- the data directory Postgres will start up against for WAL replay)

set -euo pipefail

BACKUP_KEY=""
TARGET_TIME=""
CONFIRM="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backup-key) BACKUP_KEY="$2"; shift 2 ;;
        --target-time) TARGET_TIME="$2"; shift 2 ;;
        --confirm) CONFIRM="true"; shift ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

POSTGRES_HOST="${POSTGRES_HOST:?POSTGRES_HOST is required}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:?POSTGRES_DB is required}"
POSTGRES_USER="${POSTGRES_USER:?POSTGRES_USER is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required}"
export PGPASSWORD

S3_OPTS=()
if [[ -n "${BACKUP_S3_ENDPOINT_URL:-}" ]]; then
    S3_OPTS+=(--endpoint-url "${BACKUP_S3_ENDPOINT_URL}")
fi

if [[ -z "${BACKUP_KEY}" ]]; then
    echo "No --backup-key given -- resolving most recent daily backup..."
    BACKUP_KEY="daily/$(aws s3 ls "${S3_OPTS[@]}" "${BACKUP_S3_BUCKET}/daily/" | sort | tail -n1 | awk '{print $NF}')"
    if [[ "${BACKUP_KEY}" == "daily/" ]]; then
        echo "No backups found under ${BACKUP_S3_BUCKET}/daily/ -- aborting." >&2
        exit 1
    fi
fi
echo "Selected backup: ${BACKUP_S3_BUCKET}/${BACKUP_KEY}"

echo
echo "=========================================================="
echo " RESTORE PLAN"
echo "=========================================================="
echo " Target database : ${POSTGRES_DB}@${POSTGRES_HOST}:${POSTGRES_PORT}"
echo " Backup source    : ${BACKUP_S3_BUCKET}/${BACKUP_KEY}"
if [[ -n "${TARGET_TIME}" ]]; then
    echo " Mode             : point-in-time recovery, target ${TARGET_TIME}"
else
    echo " Mode             : plain restore (point-in-time = backup's own timestamp)"
fi
echo " THIS WILL DROP AND RECREATE '${POSTGRES_DB}' ON ${POSTGRES_HOST}."
echo "=========================================================="
echo

if [[ "${CONFIRM}" != "true" ]]; then
    echo "Dry run only (no --confirm given) -- exiting without making changes."
    exit 0
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT
DUMP_FILE="${WORKDIR}/restore.dump"

echo "Downloading backup..."
aws s3 cp "${S3_OPTS[@]}" "${BACKUP_S3_BUCKET}/${BACKUP_KEY}" "${DUMP_FILE}"

echo "Dropping and recreating database ${POSTGRES_DB}..."
psql --host="${POSTGRES_HOST}" --port="${POSTGRES_PORT}" --username="${POSTGRES_USER}" \
    --dbname=postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"
psql --host="${POSTGRES_HOST}" --port="${POSTGRES_PORT}" --username="${POSTGRES_USER}" \
    --dbname=postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${POSTGRES_DB};"

echo "Restoring logical dump (this may take a while for a large database -- pg_restore -j parallelizes across available cores)..."
pg_restore \
    --host="${POSTGRES_HOST}" \
    --port="${POSTGRES_PORT}" \
    --username="${POSTGRES_USER}" \
    --dbname="${POSTGRES_DB}" \
    --jobs="$(nproc 2>/dev/null || echo 2)" \
    --no-owner \
    --no-privileges \
    "${DUMP_FILE}"

if [[ -z "${TARGET_TIME}" ]]; then
    echo "Plain restore complete. Database is at the state of the backup taken at the timestamp embedded in '${BACKUP_KEY}'."
    exit 0
fi

# --- Point-in-time recovery: replay archived WAL forward from the dump
# above up to TARGET_TIME. This half operates directly against a Postgres
# data directory (PGDATA), NOT through the client protocol -- it assumes
# it's being run on/against a Postgres instance that can be stopped and
# restarted in recovery mode (the standard PITR procedure), which in this
# project's Compose-based deployment means running this script against a
# freshly-provisioned `postgres` container (per the DR runbook's own
# "provision a new host" step), not the live production instance in place. ---
PGDATA="${PGDATA:?PGDATA is required for --target-time / PITR mode}"

echo "Configuring recovery to replay WAL up to: ${TARGET_TIME}"
cat > "${PGDATA}/postgresql.auto.conf" <<EOF
restore_command = 'aws s3 cp ${BACKUP_S3_ENDPOINT_URL:+--endpoint-url ${BACKUP_S3_ENDPOINT_URL} }${BACKUP_S3_BUCKET}/wal/%f %p --only-show-errors'
recovery_target_time = '${TARGET_TIME}'
recovery_target_action = 'promote'
EOF
touch "${PGDATA}/recovery.signal"

echo "postgresql.auto.conf and recovery.signal written to ${PGDATA}."
echo "Start (or restart) the Postgres server process against this data"
echo "directory now -- it will replay WAL from ${BACKUP_S3_BUCKET}/wal/ up to"
echo "${TARGET_TIME}, then automatically promote to a normal read/write"
echo "server (recovery_target_action = promote) and remove recovery.signal"
echo "on its own, per Postgres's documented recovery behavior."
echo
echo "This script does not start Postgres itself -- how the server process"
echo "is (re)started is deployment-specific (a container restart, a"
echo "systemd unit, pg_ctl start, etc.); this script's job ends at"
echo "producing a data directory correctly configured to recover to the"
echo "requested point in time on its next start."
