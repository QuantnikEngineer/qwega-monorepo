# QUANTNIK Frontend

React SPA for the QUANTNIK SDLC automation platform. Provides conversational AI interfaces, admin panels, and role-based dashboards.

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Node.js | **20+** | Required by `@tailwindcss/vite` |
| npm | 9+ | Bundled with Node.js |
| quantnik-api-gateway | Running | Must be available at `:8080` |
| quantnik-auth-service | Running | Gateway depends on it |

> **Startup Order:** auth-service → api-gateway → frontend

## Quick Start

```bash
cd quantnik-frontend

# 1. Install dependencies (--legacy-peer-deps required for Radix UI)
npm install --legacy-peer-deps

# 2. Create .env file
copy .env.example .env    # Windows
# cp .env.example .env    # macOS/Linux

# 3. Start dev server
npm run dev
```

The development server runs at `http://localhost:3000` and proxies API requests to the gateway at `:8080`.

### Verify Setup

1. Open http://localhost:3000 in browser
2. Navigate to `/login`
3. Login with your SuperAdmin credentials (created in auth-service setup)

### Common Issues

**"npm install" fails with peer dependency errors:**
```bash
npm install --legacy-peer-deps
```

**"ECONNREFUSED" on login:**
Ensure `quantnik-api-gateway` is running on port 8080.

**Corporate proxy issues:**
```powershell
npm config set proxy http://proxy.company.com:8080
npm config set https-proxy http://proxy.company.com:8080
npm install --legacy-peer-deps
```

## Architecture

```
Frontend (:3000 dev / :8080 prod)
    │
    └── All /api, /auth, /confluence-api, /jira-api requests
            │
            ▼
      API Gateway (:8080)
            │
            ▼
      Auth Service (:8090)  +  Orchestrators (:8081, :8082)
```

### Key Routes

| Route | Access | Description |
|-------|--------|-------------|
| `/login` | Public | Email/password login with @wipro.com enforcement |
| `/register` | Public | Self-registration (PM-mode or project-mode) |
| `/register?project=<slug>` | Public | Direct-to-project registration |
| `/execute` | Requires agents | Conversational AI — agent selection + chat |
| `/dashboard` | PM role | Project overview, team cards, onboarding wizard |
| `/` | Authenticated | Home page |

### Post-Login Redirect Logic

| Role | Default Landing |
|------|----------------|
| PM | `/dashboard` |
| PO/SM/BA (project-registered) | `/execute` |
| Any role with agents | `/execute` |
| Others | `/` |

## Auth & Authorization

- **JWT-based** — login returns access token + httpOnly refresh cookie
- **Token refresh** — automatic background refresh with retry logic (2 retries with exponential backoff for transient failures)
- **CASL** — frontend authorization library mirrors backend capabilities for UI gating
- **`requiresAnyAgent`** — Execute page is gated by agent assignment, not capability

## Registration

The frontend supports dual-mode self-registration:

- **PM-mode** — Standard registration creating a new PM user. Accessed via `/register` when no default project is configured.
- **Project-mode** — Register directly into a pre-configured project with a specific role. Users can immediately access agents after registration.

### How it works

1. User clicks "Register" on the login page
2. Frontend calls `GET /auth/registration-defaults` to check for a default project
3. If a default project is configured and open for registration → project-mode form (project pre-selected, role pre-assigned)
4. If no default → PM-mode form (standard registration)

Project-mode can also be accessed directly via `/register?project=<slug>`.

### Configuration

| Variable | Description |
|----------|-------------|
| `REGISTRATION_DEFAULT_PROJECT_SLUG` | Set in **auth-service** `.env` — slug of the default project for self-registration |
| `REGISTRATION_DEFAULT_ROLE` | Set in **auth-service** `.env` — role assigned (default: `po_sm_ba`) |

> **Admin setup:** In Admin → Manage Projects, toggle "Open for Registration" on the target project. A copyable registration link is displayed when enabled.

## Admin Features (AdminFAB Popover)

Role-specific admin menus accessible via floating action button:

| Role | Sections | Items |
|------|----------|-------|
| SuperAdmin | ADMINISTRATION | Manage Users, Projects, Roles & Capabilities, Service Registry, Agent Access (role→agent mapping) |
| SuperAdmin | INTEGRATIONS | Project Integrations |
| PM | PROJECT | My Project |
| PM | TEAM | Manage My Team |
| PM | INTEGRATIONS | View Integrations (read-only) |
| MLOps | INTEGRATIONS | Project Integrations |

## Role Model

6 roles in two tiers:

- **Org-tier** (SuperAdmin assigns): `superadmin`, `pm`
- **Project-tier** (PM assigns): `po_sm_ba`, `developer`, `tester`, `mlops`

See the auth-service repo (`quantnik-auth-service/TESTING.md § Roles & Capabilities`) for the full RBAC reference.

## Tech Stack

| Concern | Technology |
|---------|-----------|
| Framework | React 18 + TypeScript |
| Build | Vite 6 (SWC) |
| UI Components | Radix UI + Tailwind CSS |
| Authorization | CASL |
| HTTP Client | Axios (via `authApi.ts` service) |
| Routing | React Router v6 |
| Production | nginx (reverse proxy, SPA routing, security headers) |

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Development server (port 3000) |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |

## Cache Management

On logout, the **TanStack Query cache is cleared** to prevent stale data from a previous user session leaking into the next user's view. This ensures role-specific data (dashboards, admin panels, agent lists) is always fresh after login.

## Docker

```bash
# Standard build
docker build -t quantnik-frontend .

# Override base image registry (used by CI/CD pipelines)
docker build --build-arg BASE_REGISTRY=your-registry.example.com -t quantnik-frontend .

docker run -p 8080:8080 -e GATEWAY_UPSTREAM=http://gateway-host:8080 quantnik-frontend
```

## Deployment (GCP Cloud Run)

### Prerequisites

- `gcloud` CLI authenticated and project set
- **quantnik-auth-service** and **quantnik-api-gateway** already deployed (this service depends on both)

### Deploy

```bash
# Dev environment (plain env vars)
./deploy.sh --profile dev --project digital-rig-poc

# Production (with Secret Manager for Atlassian creds)
./deploy.sh --profile prod --project digital-rig-poc --use-secrets

# Preview commands without executing
./deploy.sh --profile dev --project digital-rig-poc --dry-run
```

The deploy script:
- Builds the Docker image via `gcloud builds submit`
- Deploys to Cloud Run with profile-based naming (`dev-quantnik-frontend`, `prod-quantnik-frontend`)
- Automatically computes `GATEWAY_UPSTREAM` from the gateway's Cloud Run URL
- Sets concurrency=80, memory=512Mi
- Deploys as `--allow-unauthenticated` (public-facing)

### How It Works

The frontend is a React SPA served by nginx. At container startup:
1. `envsubst` replaces `${GATEWAY_UPSTREAM}` in `nginx.conf.template`
2. nginx serves static files and reverse-proxies `/api/*`, `/auth/*`, `/jira/*`, `/confluence/*` to the gateway

> **Important:** `VITE_*` environment variables (like `VITE_APP_TITLE`) are baked into the JS bundle at **build time** (`npm run build` inside Docker). To change them, you must rebuild the image. `GATEWAY_UPSTREAM` is injected at **runtime** via envsubst.

### Environment Variables (Cloud Run)

| Variable | Required | Description |
|----------|----------|-------------|
| `GATEWAY_UPSTREAM` | Yes | API Gateway Cloud Run URL (auto-set by deploy.sh) |
| `PORT` | No | `8080` (default, Cloud Run standard) |

### Smoke Test

```bash
# Health check
curl https://dev-quantnik-frontend-XXXXX.us-central1.run.app/health
# Expected: healthy

# Login page loads
curl -s https://dev-quantnik-frontend-XXXXX.us-central1.run.app/login | head -20
# Expected: HTML with React app
```

### Deployment Order

This service is deployed **last** (depends on auth-service and api-gateway):

```
1. quantnik-auth-service
2. quantnik-api-gateway
3. quantnik-frontend      ← YOU ARE HERE
```

> **Full deployment guide:** See [`DEPLOYMENT.md`](./DEPLOYMENT.md).

## Key Source Files

| File | Purpose |
|------|---------|
| `src/App.tsx` | Route definitions, auth guards |
| `src/pages/LoginPage.tsx` | Login form + post-login redirect |
| `src/pages/RegisterPage.tsx` | Self-registration form (PM + project mode) |
| `src/components/Header.tsx` | Navigation bar with role-based items |
| `src/components/AdminFAB.tsx` | Floating admin menu (role-gated) |
| `src/components/PMDashboard.tsx` | PM landing page |
| `src/admin/components/` | Admin panels (users, projects, roles, settings) |
| `src/admin/components/ManageProjectsSheet.tsx` | Project admin with registration toggle + link copy |
| `src/auth/AuthContext.tsx` | Auth state, token refresh with retry logic |
| `src/services/authApi.ts` | Auth API service (login, refresh, CRUD) |
  