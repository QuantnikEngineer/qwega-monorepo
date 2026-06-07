# WEGA API Gateway — Deployment Guide

> **Platform**: Google Cloud Run &nbsp;|&nbsp; **CI/CD**: Harness (push-to-deploy)
>
> **Deployment order across services**: `wega-auth-service` → `wega-api-gateway` → `wega-frontend`

---

## Dev Deployment (Current)

| Service | URL |
|---------|-----|
| Auth Service | `https://dev-wega-auth-service-204952354085.us-central1.run.app` |
| API Gateway | `https://dev-wega-api-gateway-204952354085.us-central1.run.app` |
| Frontend | `https://dev-wega-frontend-204952354085.us-central1.run.app` |

**URL pattern**: `https://{profile}-{service-name}-{PROJECT_NUMBER}.{REGION}.run.app`

---

## Infrastructure

| Item | Value |
|------|-------|
| GCP Project | `digital-rig-poc` (Project Number: `204952354085`) |
| Region | `us-central1` |
| CI/CD | Harness — push-to-deploy, pipeline configured in Harness UI (not pipeline-as-code) |
| Database | None (gateway is stateless; auth-service owns PostgreSQL on AWS RDS) |
| Secrets | **No GCP Secret Manager access** — sensitive values set as plain env vars on Cloud Run (acceptable for dev) |
| VPC | VPC Service Controls are active on the GCP project — affects Cloud Build log streaming |

---

## Architecture Context

```
Frontend (nginx) ──▶ API Gateway (FastAPI) ──▶ Auth Service
                                            ──▶ SDLC Orchestrator
                                            ──▶ Planning Orchestrator
```

The gateway validates JWTs (via JWKS from auth-service), resolves per-project tool settings, and proxies requests to upstream services.

---

## Dockerfile

Standard `python:3.11-slim` image. Runs `uvicorn` on `$PORT` (Cloud Run injects `PORT=8080`). Non-root user. Health check at `/health`.

---

## Environment Variables

### Runtime (set via Cloud Run `--set-env-vars` or Harness pipeline)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | ✅ | `development` | `development` / `production` |
| `AUTH_SERVICE_URL` | ✅ | `http://localhost:8090` | Auth service Cloud Run URL |
| `ORCHESTRATOR_URL` | ✅ | `http://localhost:8081` | SDLC orchestrator Cloud Run URL |
| `PLANNING_ORCHESTRATOR_URL` | ✅ | `http://localhost:8082` | Planning orchestrator Cloud Run URL |
| `CORS_ORIGINS` | | `*` | Tighten to frontend URL in prod |
| `JWT_ISSUER` | | `wega-auth` | Must match auth service |
| `JWT_AUDIENCE` | | `wega-api` | Must match auth service |
| `INTERNAL_API_KEY` | ✅ | `wega-internal-dev-key` | Must match auth service |

### How Upstream URLs Are Computed

`deploy.sh` auto-computes Cloud Run URLs:

```
AUTH_SERVICE_URL = https://{profile}-wega-auth-service-{PROJECT_NUMBER}.{REGION}.run.app
ORCHESTRATOR_URL = https://{profile}-wega-sdlc-orchestrator-{PROJECT_NUMBER}.{REGION}.run.app
```

For Harness, set these as pipeline variables or compute in a shell step.

---

## Harness Pipeline

Trigger on push. Two steps. Each service is its own repo and pipeline on Harness — the monorepo is local-only for development convenience.

> **VPC-SC note**: `gcloud builds submit` fails to stream logs due to VPC Service Controls.
> Add `--gcs-log-dir=gs://${PROJECT}_cloudbuild/logs` to redirect logs to a GCS bucket.
>
> **Env var retention**: After the first deploy sets env vars, subsequent image-only redeploys
> (from Harness) preserve them. You only need to set env vars on the first deploy.

```bash
# 1. Build (with VPC-SC log redirect)
gcloud builds submit --tag gcr.io/${PROJECT}/${SERVICE_NAME} \
    --gcs-log-dir=gs://${PROJECT}_cloudbuild/logs

# 2. Deploy
gcloud run deploy ${SERVICE_NAME} \
    --image gcr.io/${PROJECT}/${SERVICE_NAME} \
    --platform managed --region us-central1 \
    --allow-unauthenticated \
    --memory 1Gi --cpu 1 --concurrency 80 \
    --set-env-vars APP_ENV=production \
    --set-env-vars AUTH_SERVICE_URL=<AUTH_SERVICE_CLOUD_RUN_URL> \
    --set-env-vars ORCHESTRATOR_URL=<ORCHESTRATOR_CLOUD_RUN_URL> \
    --set-env-vars PLANNING_ORCHESTRATOR_URL=<PLANNING_CLOUD_RUN_URL> \
    --set-env-vars INTERNAL_API_KEY=<SHARED_KEY>
```

---

## Local Development

```bash
cp .env.example .env
python run.py    # starts on port 8080
```

Requires `wega-auth-service` running on port 8090.

---

## Deployment Learnings & Gotchas

1. **CRLF → LF**: Shell scripts (`deploy.sh`, `entrypoint.sh`) MUST have Unix LF line endings. Windows CRLF causes `/bin/sh: ... not found` container crashes. Solution: `.gitattributes` with `*.sh text eol=lf`.
2. **VPC-SC Cloud Build**: `gcloud builds submit` fails to stream logs due to VPC Service Controls. Solution: `--gcs-log-dir=gs://${PROJECT}_cloudbuild/logs` redirects logs to a GCS bucket.
3. **Cloud Run retains env vars**: After the first deploy sets env vars, subsequent image-only redeploys (from Harness) preserve them. Only need to set env vars on the first deploy.
4. **Database is PostgreSQL on AWS RDS** (auth-service): The gateway is stateless, but be aware the auth-service database is PostgreSQL on AWS RDS — not SQLite.
5. **Deployment order matters**: `wega-auth-service` → `wega-api-gateway` → `wega-frontend`. Each depends on the previous. The gateway needs the auth-service URL at deploy time.
6. **Harness pipelines are separate**: Each service is its own repo and pipeline on Harness. The monorepo is local-only for development convenience.

---

## Domain Fronting / Host Header Fix

When the gateway forwards requests to auth-service on Cloud Run, the original `Host` header (the gateway's own hostname) gets forwarded by default. Corporate proxies like **Zscaler** detect the TLS SNI ≠ Host header mismatch and block the request with an HTML error page ("domain fronting" protection).

**Fix:** The gateway strips the `Host` header in `build_forward_headers()` (`app/middleware/header_injection.py`) so that `httpx` sets the correct `Host` for the upstream URL automatically.

> ⚠️ This is critical for **any Cloud Run service-to-service communication** through corporate networks. Without this fix, inter-service calls silently fail with Zscaler HTML error responses instead of JSON.

---

## X-Internal-Key Trust Mechanism

The gateway sends an `X-Internal-Key` header on **all** forwarded requests to upstream services. The auth-service uses this to trust `X-User-*` headers when IP-based trust isn't available (Cloud Run assigns dynamic IPs).

| Config | Gateway | Auth Service |
|--------|---------|--------------|
| Env var | `INTERNAL_API_KEY` | `INTERNAL_API_KEY` |
| Default | `wega-internal-dev-key` | `wega-internal-dev-key` |
| Cloud Run | 48-byte cryptographic token | Must match gateway's value |

The key **must match** on both services. On Cloud Run, set via:

```bash
gcloud run services update <service> --update-env-vars INTERNAL_API_KEY=<shared-48-byte-token>
```
