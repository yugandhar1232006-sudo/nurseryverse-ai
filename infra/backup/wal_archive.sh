#!/usr/bin/env bash
#
# Phase 6 Module 14 (Production Readiness) -- continuous WAL archiving.
# docs/architecture/10-devops.md §5/§6: "continuous WAL archiving" is
# what bounds RPO to 15 minutes (§6: "bounded by the WAL-archiving
# interval") -- backup_database.sh's daily logical dump alone would only
# ever restore to a point up to 24 hours stale; this script is what lets
# restore_database.sh replay forward from that dump to a much more
# recent point in time.
#
# Not run directly -- configured as Postgres's own `archive_command` (see
# postgresql.conf.snippet in this directory), which Postgres invokes once
# per completed WAL segment, passing the segment's path (%p) and bare
# filename (%f) as $1/$2 per Postgres's own archive_command contract.
#
# NOT independently run-verified: no live Postgres or `aws` in this
# development sandbox (disclosed in docs/architecture/
# 30-module14-production-readiness.md) -- validated via `bash -n` syntax
# check and manual review against Postgres's documented archive_command
# contract only.
#
# Required environment variables (set wherever postgresql.conf's
# archive_command is configured -- typically the postgres container's own
# environment, since Postgres itself invokes this script):
#   BACKUP_S3_BUCKET       -- same bucket backup_database.sh uses
#   BACKUP_S3_ENDPOINT_URL -- optional, for non-AWS S3-compatible storage

set -euo pipefail

WAL_PATH="$1"   # %p -- full path to the completed WAL segment
WAL_FILENAME="$2"  # %f -- bare segment filename

BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET is required}"

S3_OPTS=()
if [[ -n "${BACKUP_S3_ENDPOINT_URL:-}" ]]; then
    S3_OPTS+=(--endpoint-url "${BACKUP_S3_ENDPOINT_URL}")
fi

# Postgres's own archive_command contract (per its documentation): must
# return 0 ONLY once the segment is safely, durably stored -- Postgres
# will not reuse/recycle the local WAL segment until this succeeds, and
# will retry indefinitely (logging a warning) if this keeps failing.
# `aws s3 cp` without `--no-progress` output redirected to /dev/null
# keeps Postgres's own log clean; a non-zero exit here propagates
# naturally via `set -euo pipefail` + this being the script's last command.
aws s3 cp "${S3_OPTS[@]}" "${WAL_PATH}" "${BACKUP_S3_BUCKET}/wal/${WAL_FILENAME}" --only-show-errors
