# syntax=docker/dockerfile:1
#
# Phase 6 Module 14 (Production Readiness) -- docs/architecture/09-infrastructure.md
# §1: "worker.Dockerfile (same base as api.Dockerfile, different
# entrypoint -- `celery -A app.workers worker`), and the `beat` process
# reuses the `worker` image with a different command (`celery -A
# app.workers beat`), not a separate image."
#
# This file's `deps`/`runner` stages intentionally duplicate api.Dockerfile's
# rather than building `FROM` a pre-built api image by tag: that would
# couple this build to api.Dockerfile having already been built first
# (ordering the Compose/CI build graph would otherwise not need to care
# about), for a payoff -- a few hundred MB of shared base-image layers --
# Docker's own layer cache already gives both Dockerfiles for free since
# they start from the identical `python:3.10-slim` base and copy the
# identical requirements/base.txt in the identical order. Only the final
# CMD differs from api.Dockerfile below.
#
# `beat` is NOT a separate Dockerfile/image, per the architecture doc
# quoted above -- docker-compose.yml's `beat` service (Task #160) builds
# from this same file and overrides `command:` to run `celery -A
# app.workers beat` instead of `worker`.
#
# Build context is `apps/api/` (this file's grandparent directory), e.g.:
#   docker build -f infra/docker/worker.Dockerfile -t nurseryverse-worker:latest .
#
# NOT independently build-verified -- see api.Dockerfile's own header
# comment for why (no `docker` binary in this development sandbox).

########################################
# Stage 1: deps -- compile/install Python dependencies into a venv
########################################
FROM python:3.10-slim AS deps

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        g++ \
        make \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

# See api.Dockerfile for why this runs at build time, not on first task.
RUN python -c "import cmdstanpy; cmdstanpy.install_cmdstan(dir='/opt/cmdstan', version='2.35.0', cores=2, overwrite=True)"

########################################
# Stage 2: runner -- minimal production image
########################################
FROM python:3.10-slim AS runner

# libpq5 only -- unlike api.Dockerfile's runner stage, this image never
# serves HTTP, so no `curl` is needed for its HEALTHCHECK below (which
# shells out to `celery inspect ping` over the broker connection instead).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /usr/sbin/nologin --create-home app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    CMDSTAN=/opt/cmdstan/cmdstan-2.35.0 \
    CELERY_CONCURRENCY=4

COPY --from=deps /opt/venv /opt/venv
COPY --from=deps /opt/cmdstan /opt/cmdstan

WORKDIR /app
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini ./alembic.ini

USER app

# No EXPOSE: worker/beat never serve HTTP traffic (docs/architecture/
# 09-infrastructure.md §9 -- "worker/beat report health via a Celery-native
# heartbeat mechanism ... rather than an HTTP endpoint, since they don't
# serve HTTP traffic"). Healthcheck below uses Celery's own `inspect ping`
# over its broker connection instead of an HTTP probe, matching that.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD celery -A app.workers inspect ping -d celery@$HOSTNAME --timeout 5 || exit 1

# Default command runs the worker process; docker-compose.yml's `beat`
# service (Task #160) overrides this with `celery -A app.workers beat`
# against the identical image, per this file's header comment.
CMD ["celery", "-A", "app.workers", "worker", "--loglevel=info", "--concurrency=4"]
