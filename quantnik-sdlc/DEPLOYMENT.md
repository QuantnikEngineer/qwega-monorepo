# QUANTNIK Frontend — Deployment Guide

> **Platform**: Google Cloud Run &nbsp;|&nbsp; **CI/CD**: Harness (push-to-deploy)
>
> **Deployment order across services**: `quantnik-auth-service` → `quantnik-api-gateway` → `quantnik-frontend`

---

## Dev Deployment (Current)

| Service | URL |
|---------|-----|
| Auth Service | `https://dev-quantnik-auth-service-204952354085.us-central1.run.app` |
| API Gateway | `https://dev-quantnik-api-gateway-204952354085.us-central1.run.app` |
| Frontend | `https://dev-quantnik-frontend-204952354085.us-central1.run.app` |

**URL pattern**: `https://{profile}-{service-name}-{PROJECT_NUMBER}.{REGION}.run.app`

---

## Infrastructure

| Item | Value |
|------|-------|
| GCP Project | `digital-rig-poc` (Project Number: `204952354085`) |
| Region | `us-central1` |
| CI/CD | Harness — push-to-deploy, pipeline configured in Harness UI (not pipeline-as-code) |
| Database | None (frontend is a static SPA; auth-service owns PostgreSQL on AWS RDS) |
| Secrets | **No GCP Secret Manager access** — sensitive values set as plain env vars on Cloud Run (acceptable for dev) |
| VPC | VPC Service Controls are active on the GCP project — affects Cloud Build log streaming |

---

## Architecture Context

```
Browser ──▶ Frontend (nginx SPA) ──▶ API Gateway ──▶ Backend services
```

The frontend serves the React SPA via nginx. All backend traffic (`/api/*`, `/auth/*`, `/jira/*`, `/confluence/*`) is proxied by nginx to the API gateway via the `GATEWAY_UPSTREAM` env var.

---

## Dockerfile (two-stage)

1. **Builder** (`node:20-alpine`): Runs `npm run build` (Vite). `VITE_*` vars are baked into the JS bundle at this stage. *(Changed from `node:18-alpine` — `@tailwindcss/vite` requires Node >= 20.)*
2. **Runtime** (`nginx:alpine`): Serves the SPA. `nginx.conf.template` uses `envsubst` to inject `GATEWAY_UPSTREAM` at container start.

---

## Environment Variables

### Build-time (baked into JS bundle via Dockerfile `ARG`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_AUTH_ENABLED` | `true` | Enable auth/login flow in the SPA |
| `VITE_GATEWAY_URL` | _(empty)_ | Leave empty for prod — SPA uses relative URLs |
| `VITE_ATLASSIAN_BASE_URL` | hardcoded in code | For Jira/Confluence browse links |
| `VITE_JIRA_PROJECT_KEY` | hardcoded in code | Jira project key |

### Runtime (set via Cloud Run `--set-env-vars` or Harness pipeline)

| Variable | Required | Description |
|----------|----------|-------------|
| `GATEWAY_UPSTREAM` | ✅ | API Gateway Cloud Run URL (e.g., `https://quantnik-api-gateway-*.run.app`) |

### How It Works

```
Browser request to /api/users
  → nginx matches location /api/
  → proxy_pass to ${GATEWAY_UPSTREAM}
  → API Gateway handles JWT validation, routing, proxying
```

The `GATEWAY_UPSTREAM` is the **only** runtime env var needed. Everything else is baked at build time with sensible defaults in the Dockerfile.

---

## Harness Pipeline

Trigger on push. Two steps. Each service is its own repo and pipeline on Harness — the monorepo is local-only for development convenience.

> **VPC-SC note**: `gcloud builds submit` fails to stream logs due to VPC Service Controls.
> Add `--gcs-log-dir=gs://${PROJECT}_cloudbuild/logs` to redirect logs to a GCS bucket.
>
> **Env var retention**: After the first deploy sets env vars, subsequent image-only redeploys
> (from Harness) preserve them. You only need to set env vars on the first deploy.

```bash
# 1. Build (with VPC-SC log redirect; VITE_AUTH_ENABLED=true is the Dockerfile default)
gcloud builds submit --tag gcr.io/${PROJECT}/${SERVICE_NAME} \
    --gcs-log-dir=gs://${PROJECT}_cloudbuild/logs

# 2. Deploy
gcloud run deploy ${SERVICE_NAME} \
    --image gcr.io/${PROJECT}/${SERVICE_NAME} \
    --platform managed --region us-central1 \
    --allow-unauthenticated \
    --memory 512Mi --cpu 1 --concurrency 80 \
    --set-env-vars GATEWAY_UPSTREAM=<API_GATEWAY_CLOUD_RUN_URL>
```

---

## Local Development

```bash
cp .env.example .env
npm install
npm run dev    # starts on port 3000, proxies to gateway on port 8080
```

Requires `quantnik-api-gateway` running on port 8080.

---

## Deployment Learnings & Gotchas

1. **CRLF → LF**: Shell scripts (`deploy.sh`, `entrypoint.sh`) MUST have Unix LF line endings. Windows CRLF causes `/bin/sh: ... not found` container crashes. Solution: `.gitattributes` with `*.sh text eol=lf`.
2. **Node 18 → 20**: `@tailwindcss/vite` requires Node >= 20. Dockerfile changed from `node:18-alpine` to `node:20-alpine`.
3. **VPC-SC Cloud Build**: `gcloud builds submit` fails to stream logs due to VPC Service Controls. Solution: `--gcs-log-dir=gs://${PROJECT}_cloudbuild/logs` redirects logs to a GCS bucket.
4. **Cloud Run retains env vars**: After the first deploy sets env vars, subsequent image-only redeploys (from Harness) preserve them. Only need to set env vars on the first deploy.
5. **Database is PostgreSQL on AWS RDS** (auth-service): The frontend has no database, but be aware the auth-service database is PostgreSQL on AWS RDS — not SQLite.
6. **Deployment order matters**: `quantnik-auth-service` → `quantnik-api-gateway` → `quantnik-frontend`. Each depends on the previous. The frontend needs the gateway URL at deploy time.
7. **Harness pipelines are separate**: Each service is its own repo and pipeline on Harness. The monorepo is local-only for development convenience.
8. **TanStack Query cache on logout**: The React app uses TanStack Query with `staleTime: 5min`. Without clearing the cache on logout, a new user inherits cached data from the previous session (e.g., SuperAdmin's 3 projects shown to a PM who should see 1). Fix: `queryClient.clear()` in the logout callback (`src/auth/AuthContext.tsx`).
9. **Traffic pinning after rollback**: If you pin traffic to a specific revision via `gcloud run services update-traffic --to-revisions=REV=100`, subsequent `services update --update-env-vars` creates a new revision but does NOT move traffic. You must explicitly run `gcloud run services update-traffic --to-latest`.
