# QUANTNIK Auth Service — Testing Guide (Phase 3)

> For complete end-to-end testing with screenshots and detailed flows, see [`docs/E2E_WALKTHROUGH.md`](docs/E2E_WALKTHROUGH.md).

## Prerequisites

Ensure services are running:

| Service | Default URL | Command |
|---------|------------|---------|
| Auth Service | `http://localhost:8090` | `python run.py` (from `quantnik-auth-service/`) |
| API Gateway | `http://localhost:8080` | `python run.py` (from `quantnik-api-gateway/`) |
| Frontend | `http://localhost:3000` | `npm run dev` (from `quantnik-frontend/`) |

Ensure migrations have been applied:
```bash
cd quantnik-auth-service
alembic upgrade head
```

---

## 1. Initial SuperAdmin Setup

Use `create_superadmin.py` to provision the first SuperAdmin. The script is **idempotent** — running it again resets the password for the existing account.

```bash
cd quantnik-auth-service
python scripts/create_superadmin.py --email admin@wipro.com --name "Admin" --password "QuantnikAdmin1!@#"
```

After running, log in directly at `http://localhost:3000/login` with the email and password above.

> **Legacy note:** `bootstrap_admin.py` still exists but is superseded by `create_superadmin.py` for all new setups.

---

## 2. Roles & Capabilities (Phase 3)

QUANTNIK defines **6 roles** across three scope tiers:

| Role | Code | Scope | Key Capabilities |
|------|------|-------|-----------------|
| SuperAdmin | `superadmin` | platform | `platform:manage`, `org:manage_users`, all SDLC + integration + admin |
| PM | `pm` | org | `team:manage_users`, `project:create`, `project:manage_members`, `integration:use_tools` |
| PO/SM/BA | `po_sm_ba` | project | `sdlc:execute`, `sdlc:view_pipelines`, `integration:use_tools` |
| Developer | `developer` | project | `sdlc:execute`, `sdlc:view_pipelines`, `integration:use_tools` |
| Tester | `tester` | project | `sdlc:execute`, `sdlc:view_pipelines`, `integration:use_tools` |
| MLOps | `mlops` | project | `sdlc:execute`, `integration:configure_tools`, `project:configure_integrations`, `integration:use_tools` |

**Scope rules:**
- `platform` — unrestricted across the entire instance
- `org` — scoped to the user's organization
- `project` — requires a `scope_id` pointing to a specific project

---

## 3. Test Users (Phase 3 E2E Validated)

These users are recommended for manual and automated testing:

| Email | Display Name | Role | Scope | Password |
|-------|-------------|------|-------|----------|
| `aniket.ashtikar@wipro.com` | Aniket Ashtikar | superadmin | platform | `QuantnikAdmin1!@#` |
| `ravi.kumar@wipro.com` | Ravi Kumar | pm | org | `PMPassword1!@#` |
| `priya.sharma@wipro.com` | Priya Sharma | developer | project | `DevPassword1!@#` |
| `arun.patel@wipro.com` | Arun Patel | mlops | project | `MLOpsPass1!@#$` |
| `meera.nair@wipro.com` | Meera Nair | tester | project | `TesterPass1!@#` |

### Creating Users via API

**Org-tier user (PM):**
```bash
curl -X POST http://localhost:8090/api/users \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "pm@wipro.com",
    "display_name": "Test PM",
    "role_assignments": [{"role_name": "pm", "scope_type": "org"}]
  }'
```

**Project-tier user (developer):**
```bash
curl -X POST http://localhost:8090/api/users \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dev@wipro.com",
    "display_name": "Test Developer",
    "role_assignments": [{"role_name": "developer", "scope_type": "project", "scope_id": "PROJECT_UUID"}]
  }'
```

---

## 4. Testing Checklist

### 4.1 Activation Flow
- [ ] Activation token link works (open in browser)
- [ ] Password policy enforced (min 12 chars, upper + lower + digit + special)
- [ ] After activation, redirect to login
- [ ] Activation link is single-use (reuse returns error)
- [ ] Expired tokens are rejected (48h TTL)

### 4.2 Login & Session
- [ ] Login with valid credentials → access token + refresh cookie set
- [ ] Login with wrong password → `invalid_credentials` error
- [ ] Login with non-existent email → same generic error (no user enumeration)
- [ ] Account lockout after 5 failed attempts (configurable via `LOCKOUT_THRESHOLD`)
- [ ] Locked account shows retry delay
- [ ] Session refresh works (access token auto-renews via cookie)
- [ ] Logout clears cookie and revokes session

### 4.3 Role-Based Access (Phase 3)
Log in as each role and verify:

| As | Can Manage Users? | Can Create Project? | Can Manage Team? | Execute Access? | Dashboard? |
|----|:-:|:-:|:-:|:-:|:-:|
| superadmin | ✅ | ✅ | ✅ | ✅ (11 agents) | ❌ |
| pm | ❌ | ✅ | ✅ (own team) | ✅ (3 agents) | ✅ (default landing) |
| po_sm_ba | ❌ | ❌ | ❌ | ✅ (4 agents) | ❌ |
| developer | ❌ | ❌ | ❌ | ✅ (3 agents) | ❌ |
| tester | ❌ | ❌ | ❌ | ✅ (6 agents) | ❌ |
| mlops | ❌ | ❌ | ❌ | ✅ (7 agents) | ❌ |

### 4.4 Phase 3 Specific Checks
- [ ] PM defaults to `/dashboard` after login
- [ ] Execute page gated by agent assignment (`requiresAnyAgent`), not capability
- [ ] PM sees both Dashboard + Execute in nav
- [ ] AdminFAB: SA sees ADMINISTRATION + INTEGRATIONS sections
- [ ] AdminFAB: PM sees PROJECT + TEAM + INTEGRATIONS (read-only) sections
- [ ] AdminFAB: MLOps sees INTEGRATIONS section
- [ ] One-project-per-org: second project creation returns error
- [ ] PM can only see/manage users they created (`created_by` filter)
- [ ] Project-tier roles require `scope_id` (backend validation rejects without it)
- [ ] PM read-only integrations view (no save/edit buttons)

### 4.5 Safety Rules
- [ ] SuperAdmin cannot remove their own superadmin role (self-lock protection D-27)
- [ ] Cannot remove superadmin from last remaining SuperAdmin user (D-28)
- [ ] SuperAdmin cannot deactivate their own account
- [ ] User deactivation is soft-delete (status → deactivated)

### 4.6 Password Change
- [ ] Logged-in user can change password (old password required)
- [ ] Wrong current password → rejected
- [ ] New password must meet policy
- [ ] After password change, all sessions are revoked (user must re-login)

### 4.7 Admin Password Reset
- [ ] SuperAdmin can reset another user's password
- [ ] Generates a new activation URL (user sets new password)
- [ ] Old password no longer works after reset

### 4.8 Resend Activation
- [ ] Can resend activation for PENDING users only
- [ ] Cannot resend for already-active users

---

## 5. Quick API Testing (curl)

### Health check
```bash
curl http://localhost:8090/health
```

### Login
```bash
curl -X POST http://localhost:8090/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"aniket.ashtikar@wipro.com","password":"QuantnikAdmin1!@#"}' \
  -c cookies.txt
```

### Get current user
```bash
curl http://localhost:8090/api/auth/me \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

### List users (as superadmin)
```bash
curl http://localhost:8090/api/users \
  -H "Authorization: Bearer ACCESS_TOKEN"
```

### Create an org-tier user (PM)
```bash
curl -X POST http://localhost:8090/api/users \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "pm@wipro.com",
    "display_name": "Test PM",
    "role_assignments": [{"role_name": "pm", "scope_type": "org"}]
  }'
```

### Create a project-tier user (developer)
```bash
curl -X POST http://localhost:8090/api/users \
  -H "Authorization: Bearer ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dev@wipro.com",
    "display_name": "Test Developer",
    "role_assignments": [{"role_name": "developer", "scope_type": "project", "scope_id": "PROJECT_UUID"}]
  }'
```

---

## 6. Automated Tests

```bash
cd quantnik-auth-service
pytest tests/ -v
```

**141 tests** covering:
- Authentication flows (login, refresh, activation, lockout)
- User CRUD with role validation
- Project-scoped role creation
- PM team management boundaries
- Multitenancy isolation
- Sprint 7 integration tests (E2E onboarding, internal endpoint, config/schema separation)

---

## 7. Troubleshooting

| Problem | Solution |
|---------|----------|
| `admin user not found` in bootstrap | Run `alembic upgrade head` first |
| Activation URL shows "expired or used" | Run `create_superadmin.py` again or generate a new activation token |
| CORS errors in browser | Ensure frontend runs on `localhost:3000` |
| JWT errors | Ensure keys exist: `python scripts/generate_keys.py` |
| Login returns 401 immediately | Check auth service logs for details |
| `scope_id required for project-tier roles` | Include `scope_id` in `role_assignments` for developer/tester/mlops/po_sm_ba |
| PM cannot create project-tier users | Ensure the PM has an active project first |
| Execute page shows "no agents" | Check `role_agents` table for the user's role |
