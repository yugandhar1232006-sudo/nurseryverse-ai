# syntax=docker/dockerfile:1
#
# Phase 7 (Frontend Production Readiness) -- docs/architecture/09-infrastructure.md
# §1: "web.Dockerfile (Next.js, multi-stage build -- deps -> builder ->
# runner using output: 'standalone', final image contains only the compiled
# standalone server, not the full node_modules/dev toolchain)" and §9:
# "web (Next.js) exposes an equivalent lightweight health route" -- that
# route is apps/web/app/health/route.ts, served at /health (deliberately
# NOT under /api or /healthz, which nginx routes to the api upstream).
#
# Build context is `apps/web/` (this file's grandparent directory), e.g.:
#   docker build -f infra/docker/web.Dockerfile -t nurseryverse-web:latest .
#
# Same-origin model (docs/architecture/01-high-level-architecture.md: "The
# frontend talks to the FastAPI backend over same-origin HTTPS (proxied by
# Nginx)" and docs/frontend/20-production-deployment.md): NEXT_PUBLIC_API_BASE_URL
# is baked at BUILD time (default "") so the client bundle calls the SAME
# origin as the page (relative /api/v1/...) and nginx proxies it to the api
# upstream -- no CORS, and one image works for every environment (10-devops.md
# §7 immutable-build principle). Next.js inlines NEXT_PUBLIC_* into the bundle
# during `next build`, so the runner stage never reads it at runtime.

########################################
# Stage 1: deps -- install node_modules once; cached independently of app code
########################################
FROM node:26-alpine AS deps

WORKDIR /app

# Dependency manifest copied (and installed) before app source, so this
# layer (sharp, etc.) is cached independently of application code -- only
# invalidated when package.json/package-lock.json change, not on every edit.
COPY package.json package-lock.json ./
RUN npm ci

########################################
# Stage 2: builder -- compile the Next.js app into its standalone output
########################################
FROM node:26-alpine AS builder

WORKDIR /app

# NEXT_PUBLIC_API_BASE_URL is inlined by `next build`; default empty string
# = same-origin (relative /api/v1/... calls). Override per-deployment via a
# --build-arg without any code change.
ARG NEXT_PUBLIC_API_BASE_URL=""
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

########################################
# Stage 3: runner -- minimal production image, standalone server only
########################################
FROM node:26-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# curl: used by the HEALTHCHECK below (alpine ships no curl by default).
# Non-root user: `node:26-alpine` already ships a `node` user at
# uid/gid 1000 -- the same uid/gid convention the api/worker images create
# their own `app` user with (that image's base has no uid-1000 user; this
# base already does, so it is used as-is rather than shadowed).
RUN apk add --no-cache curl

# Only the compiled standalone server, not the full node_modules/dev
# toolchain -- per the architecture doc's §1 quote in the header. The
# standalone output carries its own pruned node_modules + package.json.
COPY --from=builder /app/.next/standalone ./
# Static assets are NOT part of the standalone output -- they must be copied
# alongside it into the expected .next/static location (Next standalone docs
# requirement).
COPY --from=builder /app/.next/static ./.next/static
# public/ (favicon, etc.) served at the site root.
COPY --from=builder /app/public ./public

RUN chown -R node:node /app

USER node

EXPOSE 3000

# Liveness signal for `docker compose`'s own healthcheck -- the same
# "process is up, no dependency checks" contract /health implements
# (mirrors the api image's /healthz reasoning).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:3000/health || exit 1

# Next.js standalone server. PORT/HOSTNAME are consumed by server.js itself
# (declared in ENV above, overridable per-deployment via `docker run -e` /
# Compose `environment:` without a rebuild).
CMD ["node", "server.js"]
