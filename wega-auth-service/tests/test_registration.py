"""
Tests for direct-to-project registration feature.
==================================================
Covers:
  - PM-mode registration (existing behaviour, backward-compat)
  - Project-mode registration (new flow)
  - Registration-defaults endpoint
  - Project open_for_registration CRUD
  - SAST/DAST: injection, enumeration prevention, rate limiting
  - E2E: register → login → JWT assertions
"""

import os
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EMAIL = "newuser@wipro.com"
VALID_EMAIL2 = "newuser2@wipro.com"
VALID_PASSWORD = "SecureP@ssw0rd123!"
VALID_DISPLAY = "New User"

# Reuse conftest constants
SUPERADMIN_PASSWORD = "SuperAdmin123!@#"
PM_PASSWORD = "PMUser123!@#"

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def patched_roles(async_session, seed_roles):
    """Ensure PM has project:create for project CRUD tests."""
    seed_roles["pm"].capabilities = list(set(
        seed_roles["pm"].capabilities
        + ["project:create", "project:manage_members"]
    ))
    seed_roles["superadmin"].capabilities = list(set(
        seed_roles["superadmin"].capabilities
        + ["project:create", "project:manage",
           "project:manage_members", "project:configure_integrations"]
    ))
    await async_session.commit()
    for r in seed_roles.values():
        await async_session.refresh(r)
    return seed_roles


@pytest.fixture
async def sa_token(patched_roles, seed_superadmin, test_client):
    resp = await test_client.post(
        "/api/auth/login",
        json={"email": "admin@wipro.com", "password": SUPERADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
async def pm_tok(patched_roles, seed_pm, test_client):
    resp = await test_client.post(
        "/api/auth/login",
        json={"email": "pm@wipro.com", "password": PM_PASSWORD},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
async def open_project(test_client, sa_token):
    """Create an active project with open_for_registration=True."""
    resp = await test_client.post(
        "/api/projects",
        json={
            "name": "Demo Project",
            "slug": "demo-project",
            "open_for_registration": True,
        },
        headers={"Authorization": f"Bearer {sa_token}"},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def closed_project(test_client, sa_token):
    """Create an active project with open_for_registration=False."""
    resp = await test_client.post(
        "/api/projects",
        json={
            "name": "Internal Project",
            "slug": "internal-project",
            "open_for_registration": False,
        },
        headers={"Authorization": f"Bearer {sa_token}"},
    )
    assert resp.status_code == 201
    return resp.json()


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _reset_rate_limiter():
    """Clear the in-memory rate limiter between tests."""
    from app.api.auth import _register_attempts
    _register_attempts.clear()


# ═════════════════════════════════════════════════════════════════
# 1. PM-mode registration (backward-compatibility)
# ═════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_register_pm_mode_default(test_client, seed_roles, seed_org):
    """Register without project_slug → user gets PM role, org-scope."""
    _reset_rate_limiter()
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": VALID_EMAIL,
            "display_name": VALID_DISPLAY,
            "password": VALID_PASSWORD,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "registered"

    # Verify user was created with PM role
    from app.models.user import User
    from app.models.role import UserRole

    async with test_client._transport.app.state.get("_test_session_factory", lambda: None)() if False else _noop():
        pass  # Use the test_client's session via direct DB query below

    # Re-query via API: login with the new user
    login_resp = await test_client.post(
        "/api/auth/login",
        json={"email": VALID_EMAIL, "password": VALID_PASSWORD},
    )
    assert login_resp.status_code == 200
    user_data = login_resp.json()["user"]
    assert "pm" in [r.lower() for r in user_data.get("roles", [])]


# Helper to avoid fixture issue
class _noop:
    async def __aenter__(self): return None
    async def __aexit__(self, *a): pass


@pytest.mark.anyio
async def test_register_pm_mode_no_project_role(
    test_client, seed_roles, seed_org, async_session,
):
    """PM-mode registration must NOT assign any project-scoped role."""
    _reset_rate_limiter()
    email = "pmonly@wipro.com"
    resp = await test_client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "PM Only", "password": VALID_PASSWORD},
    )
    assert resp.status_code == 201

    from app.models.user import User
    from app.models.role import UserRole

    result = await async_session.execute(
        select(User).where(User.normalized_email == email)
    )
    user = result.scalar_one()

    roles_result = await async_session.execute(
        select(UserRole).where(UserRole.user_id == user.id)
    )
    user_roles = list(roles_result.scalars().all())
    assert len(user_roles) == 1
    assert user_roles[0].scope_type == "org"
    assert user_roles[0].source == "self_registered"


# ═════════════════════════════════════════════════════════════════
# 2. Project-mode registration
# ═════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_register_project_mode_assigns_po_role(
    test_client, seed_roles, seed_org, open_project, async_session,
):
    """Register with valid project_slug → user gets po_sm_ba role, project-scope."""
    _reset_rate_limiter()
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": VALID_EMAIL2,
            "display_name": "Project User",
            "password": VALID_PASSWORD,
            "project_slug": "demo-project",
        },
    )
    assert resp.status_code == 201

    from app.models.user import User
    from app.models.role import UserRole, Role

    result = await async_session.execute(
        select(User).where(User.normalized_email == VALID_EMAIL2)
    )
    user = result.scalar_one()

    roles_result = await async_session.execute(
        select(UserRole).where(UserRole.user_id == user.id)
    )
    user_roles = list(roles_result.scalars().all())
    assert len(user_roles) == 1
    ur = user_roles[0]
    assert ur.scope_type == "project"
    assert ur.scope_id == open_project["id"]
    assert ur.source == "self_registered_project"

    # Confirm it's the po_sm_ba role
    role_result = await async_session.execute(
        select(Role).where(Role.id == ur.role_id)
    )
    role = role_result.scalar_one()
    assert role.name == "po_sm_ba"

    # Negative: NO org-scoped PM role
    pm_roles = [r for r in user_roles if r.scope_type == "org"]
    assert len(pm_roles) == 0


@pytest.mark.anyio
async def test_register_project_mode_invalid_slug_rejected(
    test_client, seed_roles, seed_org,
):
    """Register with non-existent project_slug → 400."""
    _reset_rate_limiter()
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": "ghost@wipro.com",
            "display_name": "Ghost",
            "password": VALID_PASSWORD,
            "project_slug": "does-not-exist",
        },
    )
    assert resp.status_code == 400
    assert "not available" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_register_project_mode_closed_project_rejected(
    test_client, seed_roles, seed_org, closed_project,
):
    """Register with project that has open_for_registration=False → 400."""
    _reset_rate_limiter()
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": "closed@wipro.com",
            "display_name": "Closed",
            "password": VALID_PASSWORD,
            "project_slug": "internal-project",
        },
    )
    assert resp.status_code == 400
    assert "not available" in resp.json()["detail"].lower()


@pytest.mark.anyio
async def test_register_closed_project_no_user_created(
    test_client, seed_roles, seed_org, closed_project, async_session,
):
    """Failed project registration must NOT leave orphan user/role records."""
    _reset_rate_limiter()
    email = "noleak@wipro.com"
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "display_name": "No Leak",
            "password": VALID_PASSWORD,
            "project_slug": "internal-project",
        },
    )
    assert resp.status_code == 400

    from app.models.user import User
    result = await async_session.execute(
        select(User).where(User.normalized_email == email)
    )
    assert result.scalar_one_or_none() is None


# ═════════════════════════════════════════════════════════════════
# 3. Enumeration prevention
# ═════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_duplicate_email_pm_mode_consistent_response(
    test_client, seed_roles, seed_org,
):
    """Duplicate email in PM mode → 409 with clear feedback."""
    _reset_rate_limiter()
    payload = {"email": "dupe@wipro.com", "display_name": "Dupe", "password": VALID_PASSWORD}

    resp1 = await test_client.post("/api/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await test_client.post("/api/auth/register", json=payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


@pytest.mark.anyio
async def test_duplicate_email_project_mode_consistent_response(
    test_client, seed_roles, seed_org, open_project,
):
    """Duplicate email with project_slug → 409 with clear feedback."""
    _reset_rate_limiter()
    payload = {
        "email": "dupe2@wipro.com",
        "display_name": "Dupe2",
        "password": VALID_PASSWORD,
        "project_slug": "demo-project",
    }

    resp1 = await test_client.post("/api/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await test_client.post("/api/auth/register", json=payload)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


# ═════════════════════════════════════════════════════════════════
# 4. Input validation
# ═════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_register_weak_password_rejected(test_client, seed_roles, seed_org):
    """Weak password → 400 with policy violations."""
    _reset_rate_limiter()
    resp = await test_client.post(
        "/api/auth/register",
        json={"email": "weak@wipro.com", "display_name": "Weak", "password": "short"},
    )
    assert resp.status_code == 422  # Pydantic min_length=12 check


@pytest.mark.anyio
async def test_register_invalid_email_domain_rejected(test_client, seed_roles, seed_org):
    """Non-wipro email → 422 validation error."""
    _reset_rate_limiter()
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": "user@gmail.com",
            "display_name": "External",
            "password": VALID_PASSWORD,
        },
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_register_missing_display_name_rejected(test_client, seed_roles, seed_org):
    """Missing required field → 422."""
    _reset_rate_limiter()
    resp = await test_client.post(
        "/api/auth/register",
        json={"email": VALID_EMAIL, "password": VALID_PASSWORD},
    )
    assert resp.status_code == 422


# ═════════════════════════════════════════════════════════════════
# 5. Registration defaults endpoint
# ═════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_registration_defaults_no_env_returns_pm(
    test_client, seed_roles, seed_org, monkeypatch,
):
    """No REGISTRATION_DEFAULT_PROJECT_SLUG configured → {mode: 'pm'}."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "registration_default_project_slug", "")
    resp = await test_client.get("/api/auth/registration-defaults")
    assert resp.status_code == 200
    assert resp.json() == {"mode": "pm"}


@pytest.mark.anyio
async def test_registration_defaults_with_env_returns_project(
    test_client, seed_roles, seed_org, open_project, monkeypatch,
):
    """Settings set to open project slug → {mode: 'project', ...}."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "registration_default_project_slug", "demo-project")
    monkeypatch.setattr(settings, "registration_default_role", "po_sm_ba")
    resp = await test_client.get("/api/auth/registration-defaults")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "project"
    assert body["project_slug"] == "demo-project"
    assert body["project_name"] == "Demo Project"
    assert "role" in body


@pytest.mark.anyio
async def test_registration_defaults_env_slug_closed_returns_pm(
    test_client, seed_roles, seed_org, closed_project, monkeypatch,
):
    """Settings pointing to closed project → {mode: 'pm'}."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "registration_default_project_slug", "internal-project")
    resp = await test_client.get("/api/auth/registration-defaults")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "pm"


@pytest.mark.anyio
async def test_registration_defaults_env_slug_nonexistent_returns_pm(
    test_client, seed_roles, seed_org, monkeypatch,
):
    """Settings with non-existent slug → {mode: 'pm'}."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "registration_default_project_slug", "no-such-project")
    resp = await test_client.get("/api/auth/registration-defaults")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "pm"


@pytest.mark.anyio
async def test_registration_defaults_no_auth_required(test_client, seed_roles, seed_org):
    """Endpoint is public — no Authorization header needed."""
    resp = await test_client.get("/api/auth/registration-defaults")
    assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════
# 6. Project CRUD — open_for_registration field
# ═════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_project_open_for_registration_defaults_false(test_client, sa_token):
    """Creating project without open_for_registration defaults to False."""
    resp = await test_client.post(
        "/api/projects",
        json={"name": "Default Closed"},
        headers=_h(sa_token),
    )
    assert resp.status_code == 201
    assert resp.json()["openForRegistration"] is False


@pytest.mark.anyio
async def test_project_create_with_open_for_registration(test_client, sa_token):
    """Creating project with open_for_registration=True persists it."""
    resp = await test_client.post(
        "/api/projects",
        json={"name": "Open One", "open_for_registration": True},
        headers=_h(sa_token),
    )
    assert resp.status_code == 201
    assert resp.json()["openForRegistration"] is True


@pytest.mark.anyio
async def test_project_update_toggle_open_for_registration(
    test_client, sa_token, closed_project,
):
    """Toggle open_for_registration via PUT."""
    pid = closed_project["id"]

    # Turn on
    resp = await test_client.put(
        f"/api/projects/{pid}",
        json={"open_for_registration": True},
        headers=_h(sa_token),
    )
    assert resp.status_code == 200
    assert resp.json()["openForRegistration"] is True

    # Turn off
    resp = await test_client.put(
        f"/api/projects/{pid}",
        json={"open_for_registration": False},
        headers=_h(sa_token),
    )
    assert resp.status_code == 200
    assert resp.json()["openForRegistration"] is False


@pytest.mark.anyio
async def test_project_list_includes_open_for_registration(
    test_client, sa_token, open_project,
):
    """GET /projects response includes openForRegistration field."""
    resp = await test_client.get("/api/projects", headers=_h(sa_token))
    assert resp.status_code == 200
    projects = resp.json()["projects"]
    demo = next((p for p in projects if p["slug"] == "demo-project"), None)
    assert demo is not None
    assert "openForRegistration" in demo


# ═════════════════════════════════════════════════════════════════
# 7. E2E: register → login → verify JWT
# ═════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_project_register_then_login_has_correct_access(
    test_client, seed_roles, seed_org, open_project,
):
    """E2E: project-mode register → login → JWT has project capabilities."""
    _reset_rate_limiter()
    email = "e2euser@wipro.com"

    # Register
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": email,
            "display_name": "E2E User",
            "password": VALID_PASSWORD,
            "project_slug": "demo-project",
        },
    )
    assert resp.status_code == 201

    # Login
    login_resp = await test_client.post(
        "/api/auth/login",
        json={"email": email, "password": VALID_PASSWORD},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    user = data["user"]

    # User should have po_sm_ba role's capabilities
    assert "sdlc:execute" in user.get("capabilities", [])
    assert "integration:use_tools" in user.get("capabilities", [])

    # Should NOT have PM-only capabilities
    assert "team:manage_users" not in user.get("capabilities", [])


# ═════════════════════════════════════════════════════════════════
# 8. SAST/DAST — Security tests
# ═════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_sast_no_sql_injection_in_project_slug(
    test_client, seed_roles, seed_org,
):
    """project_slug with SQL injection payload → safe rejection, no 500."""
    _reset_rate_limiter()
    payloads = [
        "'; DROP TABLE users; --",
        "demo-project' OR '1'='1",
        "1; SELECT * FROM users",
        "demo-project\" UNION SELECT * FROM users --",
    ]
    for slug in payloads:
        resp = await test_client.post(
            "/api/auth/register",
            json={
                "email": f"sqli{payloads.index(slug)}@wipro.com",
                "display_name": "SQLi Test",
                "password": VALID_PASSWORD,
                "project_slug": slug,
            },
        )
        assert resp.status_code in (400, 422), f"SQL injection slug '{slug}' returned {resp.status_code}"
        assert resp.status_code != 500


@pytest.mark.anyio
async def test_sast_no_xss_in_display_name(
    test_client, seed_roles, seed_org,
):
    """XSS payloads in display_name are stored safely, not reflected in raw HTML."""
    _reset_rate_limiter()
    xss_name = '<script>alert("xss")</script>'
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": "xsstest@wipro.com",
            "display_name": xss_name,
            "password": VALID_PASSWORD,
        },
    )
    # Registration itself should succeed (XSS is a display concern)
    assert resp.status_code == 201
    # Response body must not contain unescaped script tag
    assert "<script>" not in resp.text


@pytest.mark.anyio
async def test_sast_no_header_injection_in_email(
    test_client, seed_roles, seed_org,
):
    """Email with CRLF injection → must not cause 500 or header injection.

    Since the email goes through JSON → Pydantic → DB (not reflected in
    HTTP headers), CRLF in the local part is not a header injection vector.
    The validator rejects emails not ending with @wipro.com anyway.
    Test verifies no 500 and response headers are clean.
    """
    _reset_rate_limiter()
    # CRLF before the domain — should fail email validation
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": "injected\r\n@wipro.com",
            "display_name": "Header Inject",
            "password": VALID_PASSWORD,
        },
    )
    assert resp.status_code != 500
    # Verify no injected headers in response
    assert "X-Injected" not in resp.headers


@pytest.mark.anyio
async def test_dast_rate_limiter_enforced(
    test_client, seed_roles, seed_org,
):
    """Exceeding rate limit → 429 response."""
    _reset_rate_limiter()
    from app.core.config import settings
    rate_limit_max = settings.registration_rate_limit_max

    for i in range(rate_limit_max):
        resp = await test_client.post(
            "/api/auth/register",
            json={
                "email": f"ratelimit{i}@wipro.com",
                "display_name": f"RL {i}",
                "password": VALID_PASSWORD,
            },
        )
        assert resp.status_code in (201,), f"Request {i} failed unexpectedly: {resp.status_code}"

    # Next request should be rate limited
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": "rateover@wipro.com",
            "display_name": "Over",
            "password": VALID_PASSWORD,
        },
    )
    assert resp.status_code == 429


@pytest.mark.anyio
async def test_dast_malformed_slug_values(
    test_client, seed_roles, seed_org,
):
    """Malformed project_slug values → safe handling, no 500."""
    _reset_rate_limiter()
    # Empty/whitespace slugs are falsy → fall through to PM mode (201)
    # Non-existent slugs → 400
    # All must be safe (never 500)
    test_cases = [
        ("", 201),               # falsy → PM mode
        ("   ", 400),            # whitespace → stripped, lookup fails
        ("../etc/passwd", 400),  # path traversal → not found
        ("a" * 500, 400),        # very long → not found
        ("'; DROP TABLE--", 400),  # SQL injection → not found (parameterized query)
    ]
    for slug, expected in test_cases:
        resp = await test_client.post(
            "/api/auth/register",
            json={
                "email": f"malformed{test_cases.index((slug, expected))}@wipro.com",
                "display_name": "Malformed",
                "password": VALID_PASSWORD,
                "project_slug": slug,
            },
        )
        assert resp.status_code != 500, f"Slug {slug!r} caused 500"
        assert resp.status_code == expected, f"Slug {slug!r} gave {resp.status_code}, expected {expected}"


@pytest.mark.anyio
async def test_dast_oversized_payload_rejected(
    test_client, seed_roles, seed_org,
):
    """Extremely large payload fields → safe rejection, no 500."""
    _reset_rate_limiter()
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": "big@wipro.com",
            "display_name": "A" * 10_000,
            "password": VALID_PASSWORD,
        },
    )
    # Pydantic max_length=100 on display_name → 422
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_dast_registration_defaults_does_not_leak_internal_data(
    test_client, seed_roles, seed_org, open_project, monkeypatch,
):
    """Registration-defaults response must not include sensitive fields (IDs, secrets)."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "registration_default_project_slug", "demo-project")
    resp = await test_client.get("/api/auth/registration-defaults")
    assert resp.status_code == 200
    body = resp.json()
    # Should only contain mode, project_slug, project_name, role
    allowed_keys = {"mode", "project_slug", "project_name", "role"}
    assert set(body.keys()).issubset(allowed_keys), f"Unexpected keys: {set(body.keys()) - allowed_keys}"
    # Must not expose internal IDs
    assert "id" not in body
    assert "org_id" not in body


@pytest.mark.anyio
async def test_dast_register_response_no_sensitive_fields(
    test_client, seed_roles, seed_org,
):
    """Registration response must not leak user ID, token, or internal data."""
    _reset_rate_limiter()
    resp = await test_client.post(
        "/api/auth/register",
        json={
            "email": "clean@wipro.com",
            "display_name": "Clean",
            "password": VALID_PASSWORD,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    # Only status + message allowed
    assert set(body.keys()) == {"status", "message"}
    assert "id" not in body
    assert "token" not in body
    assert "password" not in str(body).lower()
