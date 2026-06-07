# Wega API Gateway

Central API gateway for the WEGA platform. Sits between the frontend and all backend services, handling JWT validation, CORS, rate limiting, capability-based authorization, audit logging, and reverse-proxying to upstream services.

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | `python --version` |
| pip | Latest | `pip --version` |
| wega-auth-service | Running | Must be available at `:8090` for JWT/JWKS |

> **Important:** Start `wega-auth-service` BEFORE starting the gateway. The gateway fetches JWKS from auth-service for JWT validation.

## Architecture

```
Frontend (:3000)
    │
    ▼
┌──────────────────────────────┐
│     API Gateway (:8080)      │
│  JWT · RBAC · Rate Limit     │
│  Audit Log · CORS · Proxy    │
└──────┬──────┬──────┬─────────┘
       │      │      │
       ▼      ▼      ▼
  Auth     SDLC    Planning     Confluence/
 Service  Orch     Orch         JIRA proxy
 (:8090) (:8081)  (:8082)
```

## Quick Start

```bash
cd wega-api-gateway

# 1. Create and activate virtual environment
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Windows CMD: venv\Scripts\activate.bat
# macOS/Linux: source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
copy .env.example .env         # Windows
# cp .env.example .env         # macOS/Linux

# 4. Verify .env settings (defaults work for local dev)
# AUTH_SERVICE_URL=http://localhost:8090
# INTERNAL_API_KEY=wega-internal-dev-key

# 5. Run
python run.py

# 6. Verify
curl http://localhost:8080/health
```

The service will be available at `http://localhost:8080`.

### Verify Auth Connectivity

```bash
# Should return JWKS from auth-service (proxied)
curl http://localhost:8080/auth/jwks
```

If this fails, ensure `wega-auth-service` is running on port 8090.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | Public | Health check |
| POST | `/auth/login` | Public | Proxy → Auth Service login |
| POST | `/auth/refresh` | Public | Proxy → Auth Service token refresh |
| POST | `/auth/register` | Public | Proxy → Auth Service self-registration |
| GET | `/auth/registration-defaults` | Public | Proxy → Auth Service registration defaults |
| POST | `/auth/activate` | Public | Proxy → Auth Service account activation |
| GET | `/auth/jwks` | Public | JWKS endpoint (public keys) |
| `*` | `/api/*` | JWT | Proxy → upstream services (orchestrator, auth) |
| `*` | `/confluence-api/*` | JWT | Proxy → Confluence |
| `*` | `/jira-api/*` | JWT | Proxy → JIRA |

## Middleware Stack

Requests pass through these middleware layers in order:

1. **CORS** — Cross-origin resource sharing
2. **Audit Logging** — Request/response logging with correlation IDs
3. **Rate Limiting** — Login endpoint rate limiting (configurable via `LOGIN_RATE_LIMIT_MAX` / `LOGIN_RATE_LIMIT_WINDOW`)
4. **JWT Validation** — RS256 token validation via JWKS (skipped for public routes)
5. **Capability Check** — Role-based access control per route
6. **Settings Resolver** — Tool configuration header injection (non-auth routes only)

### Settings Resolver (Middleware #6)

For non-auth `/api/*` requests (orchestrator/agent traffic), the gateway:

1. **Strips inbound `X-Tool-*` headers** — prevents clients from spoofing tool config
2. **Extracts `X-Project-Id`** from the JWT-injected identity headers
3. **Fetches project tool settings** from Auth Service via `GET /api/internal/project-settings/{project_id}` (authenticated with shared `INTERNAL_API_KEY`)
4. **Injects `X-Tool-*` headers** into the proxied request so downstream agents receive tool configuration without direct DB access
5. **Caches results** in-memory with configurable TTL (default 30s)

Example injected headers for a Jira-configured project:
```
X-Jira-Base-Url: https://company.atlassian.net
X-Jira-Project-Key: WEGA
X-Jira-Email: bot@company.com
```

> **Note:** Secret values (API tokens, passwords) are NOT injected as headers. Agents retrieve secrets via the Auth Service API when needed.

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment | `development` |
| `DEBUG` | Debug mode | `false` |
| `HOST` | Bind host | `0.0.0.0` |
| `PORT` | Bind port | `8080` |
| `AUTH_SERVICE_URL` | Auth service base URL | `http://localhost:8090` |
| `ORCHESTRATOR_URL` | SDLC orchestrator base URL | `http://localhost:8081` |
| `PLANNING_ORCHESTRATOR_URL` | Planning orchestrator base URL | `http://localhost:8082` |
| `TESTCASE_AGENT_URL` | Test-case agent service URL | Auto-computed from GCP params |
| `TESTCASE_POLL_URL` | Test-case job polling URL | Auto-computed from GCP params |
| `RAG_SERVICE_URL` | RAG service URL | `http://localhost:8085` |
| `INTEGRATION_SERVICE_URL` | Integration service URL | `http://localhost:8084` |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |
| `JWT_ISSUER` | Expected JWT issuer claim | `wega-auth` |
| `JWT_AUDIENCE` | Expected JWT audience claim | `wega-api` |
| `JWKS_CACHE_TTL_SECONDS` | JWKS public key cache TTL | `300` |
| `SSE_HEARTBEAT_SECONDS` | SSE keepalive interval | `15` |
| `SSE_RECONNECT_MS` | SSE client reconnect hint | `3000` |
| `INTERNAL_API_KEY` | Shared API key for Auth Service internal endpoints | *(required)* |
| `LOGIN_RATE_LIMIT_MAX` | Max login attempts per IP before rate limiting | `15` |
| `LOGIN_RATE_LIMIT_WINDOW` | Rate limit window in seconds | `60` |
| `GCP_PROJECT_NUMBER` | GCP project number (for URL auto-compute) | *(optional)* |
| `GCP_PROFILE_PREFIX` | Environment prefix (`dev-`, `qa-`, `prod-`) | *(optional)* |
| `SETTINGS_CACHE_TTL` | Tool settings cache TTL in seconds | `30` |

### URL Auto-Computation (Cloud Run)

When `APP_ENV` is NOT `development` and `GCP_PROJECT_NUMBER` + `GCP_PROFILE_PREFIX` are set, upstream service URLs are auto-computed from the GCP naming convention:

```
https://{prefix}wega-{service}-{project_number}.{region}.run.app
```

In development mode (`APP_ENV=development`), explicit URLs in `.env` are always respected — auto-computation is skipped to prevent accidental remote connections.

## Testing

```bash
pytest tests/ -v
```

## Docker

```bash
# Standard build
docker build -t wega-api-gateway .

# Override base image registry (used by CI/CD pipelines)
docker build --build-arg BASE_REGISTRY=your-registry.example.com -t wega-api-gateway .

docker run -p 8080:8080 --env-file .env wega-api-gateway
```

## Deployment (GCP Cloud Run)

### Prerequisites

- `gcloud` CLI authenticated and project set
- **wega-auth-service** already deployed (gateway needs `AUTH_SERVICE_URL` pointing to it)
- `INTERNAL_API_KEY` shared secret configured in both auth-service and gateway

### Deploy

```bash
# Dev environment
./deploy.sh --profile dev --project digital-rig-poc

# Production
./deploy.sh --profile prod --project digital-rig-poc

# Preview commands without executing
./deploy.sh --profile dev --project digital-rig-poc --dry-run
```

The deploy script:
- Builds the Docker image via `gcloud builds submit`
- Deploys to Cloud Run with profile-based naming (`dev-wega-api-gateway`, `prod-wega-api-gateway`)
- Sets concurrency=80, memory=1Gi, timeout=900s (SSE streaming needs longer timeouts)
- Deploys as `--allow-unauthenticated` (public-facing, JWT validation is handled in code)

### Environment Variables (Cloud Run)

| Variable | Required | Example |
|----------|----------|---------|
| `AUTH_SERVICE_URL` | Yes | `https://dev-wega-auth-service-XXXXX.us-central1.run.app` |
| `ORCHESTRATOR_URL` | Yes | `https://dev-wega-orchestrator-XXXXX.us-central1.run.app` |
| `PLANNING_ORCHESTRATOR_URL` | Yes | `https://dev-wega-planning-orchestrator-XXXXX.us-central1.run.app` |
| `INTERNAL_API_KEY` | Yes | Shared secret with auth-service |
| `JWT_ISSUER` | No | `wega-auth` (default — must match auth-service) |
| `JWT_AUDIENCE` | No | `wega-api` (default — must match auth-service) |
| `CORS_ORIGINS` | Yes | `https://dev-wega-frontend-XXXXX.us-central1.run.app` |
| `APP_ENV` | No | `production` |
| `PORT` | No | `8080` (default) |

### Cross-Service Configuration

These values **must match** between auth-service and gateway:
- `JWT_ISSUER` = `wega-auth` (both services)
- `JWT_AUDIENCE` = `wega-api` (both services)
- `INTERNAL_API_KEY` = same shared secret (both services)

### Smoke Test

```bash
# Health check
curl https://dev-wega-api-gateway-XXXXX.us-central1.run.app/health
# Expected: {"status": "ok"}

# JWKS endpoint (verifies gateway → auth-service connectivity)
curl https://dev-wega-api-gateway-XXXXX.us-central1.run.app/auth/jwks
# Expected: {"keys": [{"kty": "RSA", ...}]}

# Login (verifies full auth flow)
curl -X POST https://dev-wega-api-gateway-XXXXX.us-central1.run.app/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@wipro.com", "password": "YourPass123!@#"}'
# Expected: 200 with JWT token
```

### Deployment Order

This service is deployed **second** (depends on auth-service, frontend depends on it):

```
1. wega-auth-service   (must be running for JWKS/auth)
2. wega-api-gateway    ← YOU ARE HERE
3. wega-frontend       (needs GATEWAY_UPSTREAM pointing here)
```

> **Full deployment guide:** See [`DEPLOYMENT.md`](./DEPLOYMENT.md).
