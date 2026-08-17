# Production Deployment — M7

Covers deploying the full NurseryVerse stack (web + API + worker + supporting services) from the Docker Compose files in this repo.

## Architecture

The production deployment follows the same-origin model described in `docs/architecture/01-high-level-architecture.md`:

```
Internet → Nginx (TLS termination, security headers, CSP)
              ├── /          → web (Next.js standalone, port 3000)
              ├── /api/*    → api (FastAPI + gunicorn, port 8000)
              ├── /healthz  → api (liveness probe)
              └── /readyz   → api (readiness probe)
```

Only Nginx faces the public internet. All other services communicate over the internal Docker Compose network (`nurseryverse`).

## Seven Services

| Service | Image | Purpose | Resource Limits |
|---------|-------|---------|-----------------|
| postgres | pgvector/pgvector:pg16 | Primary data store + pgvector embeddings | 2 CPU / 2 GB |
| redis | redis:7.4-alpine | Celery broker/backend + rate limiter | 1 CPU / 512 MB |
| api | nurseryverse-api | FastAPI application server | 2 CPU / 2 GB |
| worker | nurseryverse-worker | Celery workers (inference, reports, jobs) | 2 CPU / 4 GB |
| beat | nurseryverse-worker (same image) | Celery beat scheduler (single replica) | 0.5 CPU / 512 MB |
| web | nurseryverse-web | Next.js standalone server | 1 CPU / 1 GB |
| nginx | nginx:1.27-alpine | Reverse proxy, TLS, security headers | 1 CPU / 256 MB |

## Prerequisites

1. **Docker Compose v2.24+** (for `!override` merge tags in prod overlay)
2. **Pre-built images** pushed to a container registry (CI builds them via `.github/workflows/ci.yml`)
3. **TLS certificates** (Let's Encrypt / certbot / platform-managed)
4. **.env file** alongside `docker-compose.yml` (see `.env.example`)

## Environment Variables

### Required (no defaults — deployment fails without them)

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | Strong database password |
| `JWT_PRIVATE_KEY` | RSA-2048 private key for JWT signing (PEM) |
| `JWT_PUBLIC_KEY` | RSA-2048 public key for JWT verification (PEM) |
| `API_IMAGE_TAG` | e.g. `ghcr.io/org/nurseryverse-api:1.0.0` |
| `WORKER_IMAGE_TAG` | e.g. `ghcr.io/org/nurseryverse-worker:1.0.0` |
| `WEB_IMAGE_TAG` | e.g. `ghcr.io/org/nurseryverse-web:1.0.0` |
| `TLS_CERT_DIR` | Path to TLS cert material mounted into Nginx |

### Optional (degrade gracefully when unset)

| Variable | Default | Feature |
|----------|---------|---------|
| `ANTHROPIC_API_KEY` | (empty) | AI Assistant — logs error, returns "not configured" |
| `VOYAGE_API_KEY` | (empty) | Knowledge base embeddings — disabled when unset |
| `CLOUDINARY_CLOUD_NAME/API_KEY/API_SECRET` | (empty) | Image/document uploads — disabled when unset |
| `SMTP_HOST/PORT/USERNAME/PASSWORD` | (empty) | Email notifications — disabled when unset |

### Production-only overrides

| Variable | Default | Description |
|----------|---------|-------------|
| `API_WEB_CONCURRENCY` | `4` | Gunicorn worker count for the API |
| `AUTH_SIGNUP_RATE_LIMIT_PER_HOUR` | `10` | Production-safe signup rate limit |
| `AUTH_LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | Production-safe login rate limit |

## Build and Push Images

Images are built by CI (`.github/workflows/ci.yml`) on every merge to main. The pipeline:
1. Builds the API image (`apps/api/infra/docker/api.Dockerfile`)
2. Builds the Worker image (`apps/api/infra/docker/worker.Dockerfile`)
3. Builds the Web image (`apps/web/infra/docker/web.Dockerfile`) with `NEXT_PUBLIC_API_BASE_URL=""` (same-origin)
4. Pushes all three to the container registry
5. Tags with the commit SHA and version tag

## Deploy

```bash
# 1. Clone the repo on the target host
git clone https://github.com/org/nurseryverse-ai.git
cd nurseryverse-ai

# 2. Create .env with production values
cp .env.example .env
# Edit .env with real secrets...

# 3. Pull the pre-built images
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

# 4. Start the stack
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 5. Run migrations (first deploy or upgrades)
docker compose exec api alembic upgrade head

# 6. Verify health
curl -f http://localhost/health      # web liveness
curl -f http://localhost/healthz     # api liveness
curl -f http://localhost/readyz      # api readiness
```

## TLS Configuration

Nginx TLS is configured in `infra/nginx/conf.d/default.conf`. Uncomment the SSL directives and mount your certificate material:

```yaml
# In docker-compose.prod.yml's nginx service volumes:
- /etc/letsencrypt/live/your-domain:/etc/nginx/certs:ro
```

Set `TLS_CERT_DIR` in `.env` to the same path. Nginx expects:
- `/etc/nginx/certs/fullchain.pem`
- `/etc/nginx/certs/privkey.pem`

## Nginx Security Headers

Applied to every response (including error responses) via `add_header ... always`:

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` | HSTS |
| `X-Frame-Options` | `DENY` | Clickjacking prevention |
| `X-Content-Type-Options` | `nosniff` | MIME-sniffing prevention |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Referrer leakage |
| `Permissions-Policy` | `geolocation=(), camera=(), microphone=()` | Feature policy |
| `Content-Security-Policy` | See `default.conf` | Script/style/img/font/connect-src |

## Web Image Build Stages

The `web.Dockerfile` uses a 3-stage build:

1. **deps** — `npm ci` with full devDependencies, cached independently of app code
2. **builder** — `next build` with `NEXT_PUBLIC_API_BASE_URL` baked at build time (default `""` = same-origin relative calls)
3. **runner** — minimal `node:26-alpine` with only the standalone output, runs as non-root `node` user

The standalone server reads `PORT` (default 3000) and `HOSTNAME` (default `0.0.0.0`) from environment at runtime.

## Health Checks

| Service | Probe | Implementation |
|---------|-------|----------------|
| api | `/healthz` + `/readyz` | FastAPI startup/shutdown hooks |
| web | `/health` | `apps/web/app/health/route.ts` — lightweight "process is up" |
| postgres | `pg_isready` | Docker Compose healthcheck |
| redis | `redis-cli ping` | Docker Compose healthcheck |
| worker | `celery inspect ping` | Built into `worker.Dockerfile` HEALTHCHECK |
| beat | (none) | Celery beat has no health RPC; supervised at process level |
| nginx | (depends on upstream health) | `depends_on: api + web: service_healthy` |

## Resource Summary

| Service | CPU Limit | Memory Limit | Memory Reservation |
|---------|-----------|-------------|-------------------|
| postgres | 2 | 2 GB | 512 MB |
| redis | 1 | 512 MB | 128 MB |
| api | 2 | 2 GB | 1 GB |
| worker | 2 | 4 GB | 1 GB |
| beat | 0.5 | 512 MB | — |
| web | 1 | 1 GB | 256 MB |
| nginx | 1 | 256 MB | — |
| **Total** | **9.5** | **~8.5 GB** | — |

## Operational Notes

- **Migrations**: Run `docker compose exec api alembic upgrade head` after each deploy that includes migration changes. The API container runs Alembic on startup in development; production requires manual invocation.
- **Celery beat**: Must run exactly 1 replica (pinned in `docker-compose.prod.yml`). Two beat processes would double-fire scheduled tasks.
- **Worker memory**: The worker has the highest allocation (4 GB) because ML inference (torch/xgboost/prophet) runs there, not in the API.
- **Anthropic key**: If unset, the AI Assistant returns a graceful "not configured" error. All other features continue working.
- **Rate limits**: Production defaults are `10 signups/hour` and `10 logins/minute`. Override via environment variables if needed.
