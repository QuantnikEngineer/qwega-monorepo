# Wega Auth Service

Authentication and authorization service for the WEGA SDLC automation platform.

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | `python --version` |
| PostgreSQL | 14+ | **Required** — SQLite not supported |
| pip | Latest | `pip --version` |

### PostgreSQL Setup (Required Before First Run)

The auth service requires PostgreSQL. This is the most common setup blocker.

**Check if PostgreSQL is installed:**
```powershell
# Windows - check common install location
Test-Path "C:\Program Files\PostgreSQL"
Get-ChildItem "C:\Program Files\PostgreSQL" -ErrorAction SilentlyContinue
```

**Create the database:**
```powershell
# Windows (use full path if psql not in PATH)
$PSQL = "C:\Program Files\PostgreSQL\17\bin\psql.exe"  # Adjust version
& $PSQL -U postgres -h localhost -c "CREATE DATABASE wega_auth;"
```

```bash
# macOS/Linux
psql -U postgres -h localhost -c "CREATE DATABASE wega_auth;"
```

If prompted for password, use the password set during PostgreSQL installation (often `postgres` in dev environments).

---

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1
# Or Windows CMD: venv\Scripts\activate.bat
# Or macOS/Linux: source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config
cp .env.example .env    # macOS/Linux
copy .env.example .env  # Windows

# 5. Edit .env — set your PostgreSQL password
# DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/wega_auth

# 6. Generate RS256 key pair (first time only)
python scripts/generate_keys.py

# 7. Set up db_config.py for scripts
cd scripts
cp db_config.example.py db_config.py  # Edit password in ENVIRONMENTS["local"]
cd ..

# 8. Run database migrations
alembic upgrade head

# 9. Run in development mode
python run.py
```

The service will be available at `http://localhost:8090`.

### Verify Setup

```bash
curl http://localhost:8090/health
curl http://localhost:8090/.well-known/jwks.json
```

### Diagnostic Script

If something fails, run:
```powershell
.\venv\Scripts\python.exe scripts\_audit_db.py
```
This shows tables, users, migration version, and JWT key status.

## First-Time Setup: Creating a SuperAdmin

After running migrations, there are **no users with passwords**. You need to create at least one SuperAdmin to log in and manage the platform.

```bash
# Create a superadmin (from wega-auth-service/)
python scripts/create_superadmin.py --email you@wipro.com --name "Your Name" --password "YourPass123!@#"
```

Password policy: minimum 12 characters, must include uppercase, lowercase, digit, and special character.

The script is **idempotent** — running it again for the same email resets the password and ensures the superadmin role is assigned. Omit `--password` to be prompted interactively (hides input).

**Creating additional superadmins:**

```bash
python scripts/create_superadmin.py --email colleague@wipro.com --name "Colleague Name" --password "TheirPass123!@#"
```

> **Note:** Regular users (non-superadmin) should be created through the Admin Panel UI after logging in as SuperAdmin. The admin panel generates activation links that users open to set their own passwords.

## Role Model (Phase 3)

6 roles in two tiers:

- **Org-tier**: `superadmin` (scope_type=platform), `pm` (scope_type=org)
- **Project-tier**: `po_sm_ba`, `developer`, `tester`, `mlops` (scope_type=project, scope_id required)

## API Endpoints

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/login` | Public | Email/password login → JWT + refresh cookie |
| POST | `/api/auth/refresh` | Public | Rotate refresh token |
| POST | `/api/auth/logout` | JWT | Revoke session |
| POST | `/api/auth/change-password` | JWT | Change password (old password required) |
| GET | `/api/auth/me` | JWT | Current user profile with roles, capabilities, agents |
| GET | `/api/auth/activate?token=` | Public | Validate activation token |
| POST | `/api/auth/activate` | Public | Redeem activation token + set password |
| GET | `/.well-known/jwks.json` | Public | Public JWKS for JWT verification |

### Registration (Self-Service)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | Public | Self-register (PM-mode or project-mode) |
| GET | `/api/auth/registration-defaults` | Public | Get default registration mode for frontend |

**Dual-mode registration:**

- **PM-mode** (default): User registers as a PM with org-scoped access. Standard onboarding flow — create project, add members, configure tools.
- **Project-mode**: User registers directly into a pre-configured project with a specific role (default: `po_sm_ba`). Ideal for demos and trials — users can immediately access agents.

Project-mode is triggered when:
1. The request includes `project_slug` in the POST body, OR
2. `REGISTRATION_DEFAULT_PROJECT_SLUG` is configured and the project has `open_for_registration = true`

Projects must have `open_for_registration` enabled (toggle available in Admin → Manage Projects).

### Users

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/users` | JWT + `org:manage_users` or `team:manage_users` | List users (scoped by role) |
| POST | `/api/users` | JWT + `org:manage_users` or `team:manage_users` | Create user with role assignments |
| GET | `/api/users/{user_id}` | JWT | Get user details |
| PUT | `/api/users/{user_id}` | JWT + `org:manage_users` | Update user |
| DELETE | `/api/users/{user_id}` | JWT + `org:manage_users` | Deactivate user (soft delete) |
| POST | `/api/users/{user_id}/reset-password` | JWT + `org:manage_users` | Generate new activation token |
| POST | `/api/users/{user_id}/resend-activation` | JWT + `org:manage_users` | Resend activation for PENDING users |

### Roles

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/roles` | JWT | List all roles |
| GET | `/api/roles/agents` | JWT | List role-agent mappings |
| GET | `/api/roles/capabilities` | JWT | List role-capability mappings |

### Projects

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/projects` | JWT | List projects (org-scoped) |
| POST | `/api/projects` | JWT + `project:create` | Create project (one-per-org constraint) |
| GET | `/api/projects/{project_id}` | JWT | Get project details |
| PUT | `/api/projects/{project_id}` | JWT + `project:manage` | Update project (includes `open_for_registration` toggle) |
| DELETE | `/api/projects/{project_id}` | JWT + `project:manage` | Delete project |
| GET | `/api/projects/{project_id}/members` | JWT | List project members |
| POST | `/api/projects/{project_id}/members` | JWT + `project:manage_members` | Add project member |
| DELETE | `/api/projects/{project_id}/members/{user_id}` | JWT + `project:manage_members` | Remove project member |

### Services & Settings (Tool Integrations)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/services` | JWT | List service registry (available tools) |
| GET | `/api/services/{service_id}` | JWT | Get service details |
| GET | `/api/projects/{project_id}/settings` | JWT + `integration:use_tools` | Get project tool settings (enabled tools + config) |
| PUT | `/api/projects/{project_id}/settings/{service_id}` | JWT + `integration:configure_tools` | Save tool settings (MLOps/SA only) |

### Internal (Service-to-Service)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/internal/project-settings/{project_id}` | API Key (`X-Internal-Api-Key`) | Get all enabled tool configs for gateway header injection |

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | Public | Health check |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/create_superadmin.py` | Create or reset a SuperAdmin user with password (idempotent) |
| `scripts/reset_password.py` | Reset any user's password by email (idempotent) |
| `scripts/list_users.py` | List all users, roles, projects, agents (`--verbose` for full detail) |
| `scripts/db_config.example.py` | Template for DB environment profiles — copy to `db_config.py` and fill in credentials |
| `scripts/_setup_demo.py` | API-based demo data setup (creates users, project, tool configs) |
| `scripts/bootstrap_admin.py` | *(Legacy)* Generate activation URL for seeded admin — prefer `create_superadmin.py` |
| `scripts/generate_keys.py` | Generate RS256 key pair for JWT signing |

All scripts support `--env local` (default) or `--env remote` for targeting different databases. See `db_config.example.py` for setup.

## Database

- PostgreSQL always — localhost for local dev, AWS RDS for Cloud Run
- Migrations managed by Alembic

### Key Migrations

| Migration | Description |
|-----------|-------------|
| `001_unified_schema` | Core schema: users, roles, auth_methods, sessions, projects, service_registry, org, superadmin + demo users, role-agent mappings |
| `6f360649fc0f_grant_pm_po_all_agents` | Grants PM and PO/SM/BA roles access to all 11 agents (idempotent) |
| `002_agent_catalog` | Creates `agent_catalog` table, seeds 11 agents, adds FK + unique constraints on `role_agents` (idempotent) |
| `003_add_ado_service` | Adds Azure DevOps service to service registry |
| `004_project_agent_overrides` | Per-project agent override configuration |
| `005_sharepoint_clientsecret` | Stub — bridges QA/stage DB state from a prior branch deployment (no-op) |
| `005_open_for_registration` | Adds `open_for_registration` boolean to projects table |

## Dependencies

| Package | Purpose |
|---------|---------|
| FastAPI | HTTP framework |
| uvicorn | ASGI server |
| pydantic-settings | Environment configuration |
| structlog | Structured logging |
| argon2-cffi | Password hashing (Argon2id, OWASP 2025 params) |
| PyJWT[crypto] | JWT token handling (RS256) |
| cryptography | RSA key operations |
| SQLAlchemy[asyncio] | Async ORM (PostgreSQL) |
| alembic | Database migrations |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/ -m integration -v       # Integration tests
pytest tests/ -m "not migration" -v   # Skip migration tests (need PostgreSQL)
```

Test coverage includes:
- Authentication (login, refresh, logout, password change)
- Registration (PM-mode, project-mode, rate limiting, validation)
- Account lockout and backoff
- Cookie configuration (SameSite, HttpOnly, Secure)
- SAST checks (input sanitization, injection prevention)
- DAST checks (rate limiting, information leakage prevention)

## Docker

```bash
# Standard build
docker build -t wega-auth-service .

# Override base image registry (used by CI/CD pipelines)
docker build --build-arg BASE_REGISTRY=your-registry.example.com -t wega-auth-service .

docker run -p 8090:8080 --env-file .env wega-auth-service
```

## Deployment (GCP Cloud Run)

### Prerequisites

- `gcloud` CLI authenticated and project set (`gcloud auth login && gcloud config set project digital-rig-poc`)
- Remote PostgreSQL database accessible from Cloud Run (have host, port, db name, user, password ready)
- JWT RS256 key pair generated (`python scripts/generate_keys.py`)

### Deploy

```bash
# Dev environment (plain env vars)
./deploy.sh --profile dev --project digital-rig-poc

# Production (with Secret Manager)
./deploy.sh --profile prod --project digital-rig-poc --use-secrets

# Preview commands without executing
./deploy.sh --profile dev --project digital-rig-poc --dry-run
```

The deploy script:
- Builds the Docker image via `gcloud builds submit`
- Deploys to Cloud Run with profile-based naming (`dev-wega-auth-service`, `prod-wega-auth-service`)
- Sets concurrency=10 (Argon2 password hashing is CPU-bound), memory=1Gi
- Deploys as `--allow-unauthenticated` (gateway authenticates via `INTERNAL_API_KEY` header, not Cloud Run IAM)

### Environment Variables (Cloud Run)

| Variable | Required | Example |
|----------|----------|---------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:pass@host:5432/wega_auth` |
| `JWT_PRIVATE_KEY_PATH` | Yes | `/app/keys/private.pem` |
| `JWT_PUBLIC_KEY_PATH` | Yes | `/app/keys/public.pem` |
| `INTERNAL_API_KEY` | Yes | Shared secret with API Gateway |
| `JWT_ISSUER` | No | `wega-auth` (default) |
| `JWT_AUDIENCE` | No | `wega-api` (default) |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` (default) — access token lifetime |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `30` (default) — refresh token lifetime |
| `COOKIE_SAMESITE` | No | `lax` (default) — cookie SameSite policy (`strict` for prod) |
| `LOCKOUT_THRESHOLD` | No | `15` (default) — failed login attempts before lockout |
| `LOCKOUT_WINDOW_MINUTES` | No | `5` (default) — lockout duration in minutes |
| `REGISTRATION_DEFAULT_PROJECT_SLUG` | No | Project slug for default self-registration |
| `REGISTRATION_DEFAULT_ROLE` | No | `po_sm_ba` (default) — role for project-mode registration |
| `REGISTRATION_RATE_LIMIT_MAX` | No | `30` (default) — max registrations per IP per window |
| `REGISTRATION_RATE_LIMIT_WINDOW` | No | `3600` (default) — rate limit window in seconds |
| `FRONTEND_URL` | Yes | `https://dev-wega-frontend-XXXXX.us-central1.run.app` |
| `CORS_ORIGINS` | Yes | Same as FRONTEND_URL |
| `PORT` | No | `8080` (default, Cloud Run standard) |

### Database Migrations

> **⚠️ CRITICAL (CI/CD pipelines):** The migration Cloud Run Job image MUST be
> updated to match the service image BEFORE execution. If the pipeline deploys
> a new service image without updating the migration job, the job runs with stale
> code and fails. The `deploy.sh` script handles this automatically; external
> pipelines (Harness, etc.) must replicate this step:
> ```bash
> gcloud run jobs update <profile>-wega-auth-service-migrate \
>   --region us-central1 --image <same-image-as-service>
> gcloud run jobs execute <profile>-wega-auth-service-migrate --wait
> ```
>
> If migration fails with "Can't locate revision", use `alembic stamp --purge`
> to reset: `--args="-m,alembic,stamp,--purge,<last-known-good-revision>"`

```bash
# Option A: Cloud Run Job (production — avoids race conditions with multiple instances)
gcloud run jobs create dev-wega-auth-service-migrate \
  --image gcr.io/digital-rig-poc/dev-wega-auth-service \
  --region us-central1 \
  --set-env-vars DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/wega_auth \
  --command alembic,upgrade,head
gcloud run jobs execute dev-wega-auth-service-migrate --region us-central1

# Option B: Run locally (dev — simpler)
export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/wega_auth
alembic upgrade head
```

### First Deployment — Bootstrap Superadmin

After migrations complete, create the first superadmin user:

```bash
# Locally (with DATABASE_URL pointing to remote DB)
export DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/wega_auth
python scripts/create_superadmin.py --email you@wipro.com --name "Your Name" --password "YourPass123!@#"
```

### Secret Manager (Production)

When using `--use-secrets`, create these secrets first:

```bash
# JWT keys (volume-mounted to /app/keys/)
gcloud secrets create dev-wega-auth-jwt-private-key --data-file=keys/private.pem
gcloud secrets create dev-wega-auth-jwt-public-key --data-file=keys/public.pem

# Database URL
echo -n "postgresql+asyncpg://user:pass@host:5432/wega_auth" | \
  gcloud secrets create dev-wega-auth-database-url --data-file=-

# Internal API key (shared with api-gateway)
echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create dev-wega-internal-api-key --data-file=-
```

Grant access to the Cloud Run service account:

```bash
PROJECT_NUMBER=$(gcloud projects describe digital-rig-poc --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in dev-wega-auth-jwt-private-key dev-wega-auth-jwt-public-key dev-wega-auth-database-url dev-wega-internal-api-key; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
done
```

### Smoke Test

```bash
# Health check
curl https://dev-wega-auth-service-XXXXX.us-central1.run.app/health
# Expected: {"status": "healthy", ...}

# JWKS endpoint
curl https://dev-wega-auth-service-XXXXX.us-central1.run.app/.well-known/jwks.json
# Expected: {"keys": [{"kty": "RSA", ...}]}
```

### Deployment Order

This service must be deployed **first** (other services depend on it):

```
1. wega-auth-service  ← YOU ARE HERE
2. wega-api-gateway   (needs AUTH_SERVICE_URL pointing to auth)
3. wega-frontend      (needs GATEWAY_UPSTREAM pointing to gateway)
```

> **Full deployment guide:** See [`DEPLOYMENT.md`](./DEPLOYMENT.md).

---

## Troubleshooting

### "Connection refused" or "could not connect to server"

PostgreSQL service is not running.

```powershell
# Windows - check service status
Get-Service -Name "postgresql*"

# Start if stopped
Start-Service -Name "postgresql-x64-17"  # Adjust version
```

### "password authentication failed for user postgres"

Wrong password in `.env` or `scripts/db_config.py`.

1. Verify your PostgreSQL password
2. Update `DATABASE_URL` in `.env`
3. Update `password` in `scripts/db_config.py`

### "database 'wega_auth' does not exist"

Run the database creation command from Prerequisites section.

### "No module named 'asyncpg'" or similar import errors

Dependencies not installed. Ensure venv is activated, then:
```bash
pip install -r requirements.txt
```

### "Could not locate 'keys/private.pem'"

JWT keys not generated. Run:
```bash
python scripts/generate_keys.py
```

### "FATAL: role 'postgres' does not exist"

Your PostgreSQL uses a different superuser. Check with:
```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U YOUR_USERNAME -h localhost -l
```

### Corporate Proxy Issues

```powershell
# Set proxy for pip
$env:HTTP_PROXY = "http://proxy.company.com:8080"
$env:HTTPS_PROXY = "http://proxy.company.com:8080"

pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

### PowerShell Execution Policy Error

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
