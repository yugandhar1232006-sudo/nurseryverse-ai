# syntax=docker/dockerfile:1
#
# Phase 6 Module 14 (Production Readiness) -- docs/architecture/09-infrastructure.md
# §1: "api.Dockerfile (FastAPI, multi-stage -- dependency install layer
# cached separately from app-code layer for fast rebuilds, final image
# runs via Gunicorn with Uvicorn workers)... Every image runs as a
# non-root user; the API/worker images do not include build tools or
# source-control metadata in the final layer (multi-stage build discards
# them)."
#
# Build context is `apps/api/` (this file's grandparent directory), e.g.:
#   docker build -f infra/docker/api.Dockerfile -t nurseryverse-api:latest .
#
# NOT independently build-verified: this development sandbox has no
# `docker` binary (disclosed in docs/architecture/30-module14-production-readiness.md).
# Validated here via Hadolint-style manual review and `docker build --check`-
# equivalent structural reasoning only -- treat a real `docker build` in a
# CI runner (Task/Module #162's GitHub Actions pipeline) as the first
# genuine build verification this file receives.

########################################
# Stage 1: deps -- compile/install Python dependencies into a venv
########################################
FROM python:3.10-slim AS deps

# Build tools required to compile C-extension dependencies: asyncpg,
# xgboost, and prophet's cmdstanpy backend (which needs a C++ toolchain to
# build the actual cmdstan sampler binary -- see the RUN step below). None
# of this reaches the final `runner` stage; multi-stage build discards it,
# per the architecture doc's "final layer" guarantee quoted above.
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

# Dependency manifest copied (and installed) before app source, so this
# slow layer (torch/prophet/xgboost compile time) is cached independently
# of application code -- only invalidated when requirements/base.txt
# itself changes, not on every `app/` edit.
COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir -r requirements/base.txt

# prophet (Module 10: AI Platform, revenue forecasting) uses cmdstanpy as
# its default inference backend as of prophet>=1.1. cmdstanpy ships as a
# pure-Python package, but the actual C++ sampler binary (cmdstan) is a
# separate build step that must happen once, here, at image-build time --
# a cold worker/API replica should never spend its first inference request
# compiling a C++ program from source. Installed to a fixed, version-
# pinned path (not cmdstanpy's default `~/.cmdstan`) so the `runner` stage
# below can COPY it without depending on which user's home directory the
# `deps` stage happened to build under.
RUN python -c "import cmdstanpy; cmdstanpy.install_cmdstan(dir='/opt/cmdstan', version='2.35.0', cores=2, overwrite=True)"

########################################
# Stage 2: runner -- minimal production image
########################################
FROM python:3.10-slim AS runner

# libpq5: runtime shared library asyncpg/psycopg need to talk to Postgres
# (build-essential/libpq-dev, needed only to *compile* those extensions,
# stay behind in the `deps` stage). curl: used by the HEALTHCHECK below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /usr/sbin/nologin --create-home app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    CMDSTAN=/opt/cmdstan/cmdstan-2.35.0 \
    WEB_CONCURRENCY=4

COPY --from=deps /opt/venv /opt/venv
COPY --from=deps /opt/cmdstan /opt/cmdstan

WORKDIR /app

# Application code, plus migrations/alembic.ini -- not needed to *serve*
# traffic, but kept in the image so `docker compose run api alembic
# upgrade head` (the pre-deploy migration step referenced in Task #162's
# CI/CD pipeline and docs/architecture/10-devops.md's release process) has
# something to run against without a second, migration-only image.
COPY --chown=app:app app ./app
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app alembic.ini ./alembic.ini

USER app

EXPOSE 8000

# Liveness signal for `docker compose`'s own healthcheck (independent of,
# and simpler than, the app's own /healthz-vs-/readyz distinction --
# Compose only needs "is this container's HTTP server answering at all",
# matching /healthz's own "no dependency checks" contract per
# app/api/routes/health.py).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# Gunicorn as the process manager (worker recycling, graceful reload),
# Uvicorn's ASGI worker class underneath (required -- FastAPI is an ASGI,
# not WSGI, application) -- exactly the "runs via Gunicorn with Uvicorn
# workers" split docs/architecture/09-infrastructure.md §1 specifies.
# `app.main:app` is the module-level ASGI instance app/main.py's own
# docstring explains exists specifically so tests can use `create_app()`
# instead -- production, unlike tests, wants the one importable singleton.
# Shell form (not exec-form array) deliberately, so `$WEB_CONCURRENCY`
# (declared above, overridable per-deployment via `docker run -e` /
# Compose `environment:` without a rebuild) actually gets substituted --
# an exec-form CMD would pass the literal string "$WEB_CONCURRENCY"
# straight to gunicorn instead of expanding it.
CMD gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --workers "${WEB_CONCURRENCY:-4}" \
    --timeout 60 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
