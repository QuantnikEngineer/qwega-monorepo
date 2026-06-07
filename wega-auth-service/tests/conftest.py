"""Shared pytest fixtures for auth service tests."""

import os
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ["WEGA_AUTH_APP_ENV"] = "testing"
os.environ["WEGA_AUTH_DATABASE_URL"] = "sqlite+aiosqlite:///./test_wega_auth.db"
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_wega_auth.db"

TEST_DB_URL = "sqlite+aiosqlite:///./test_wega_auth.db"
TEST_DB_FILE = Path("./test_wega_auth.db")


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Use asyncio backend for async pytest runs."""
    return "asyncio"


@pytest.fixture
async def async_engine():
    """Create disposable async sqlite engine."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    try:
        yield engine
    finally:
        await engine.dispose()
        if TEST_DB_FILE.exists():
            try:
                TEST_DB_FILE.unlink()
            except PermissionError:
                pass


@pytest.fixture
async def async_session(async_engine) -> AsyncSession:
    """Create async DB session with schema setup/teardown."""
    try:
        from app.database import Base
        from app import models as _models  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"App models not yet implemented (Plan 01): {exc}")

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def test_client(async_session: AsyncSession):
    """Create AsyncClient for in-process FastAPI app."""
    try:
        from app.main import app
        from app.auth.jwt_manager import JWTManager
        from app.database import get_db
    except ImportError as exc:
        pytest.skip(f"App not yet implemented (Plan 04): {exc}")

    async def _override_get_db():
        yield async_session

    app.dependency_overrides[get_db] = _override_get_db
    app.state.jwt_manager = JWTManager()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def jwt_manager():
    """Get JWT manager implementation when available."""
    try:
        from app.auth.jwt_manager import JWTManager
    except ImportError as exc:
        pytest.skip(f"JWT manager not yet implemented (Plan 03): {exc}")

    return JWTManager()


@pytest.fixture
def password_service():
    """Get password service implementation when available."""
    try:
        from app.services.password_service import PasswordService
    except ImportError as exc:
        pytest.skip(f"Password service not yet implemented (Plan 03): {exc}")

    return PasswordService()


@pytest.fixture
async def seed_user(async_session: AsyncSession):
    """Seed active user and password auth method."""
    try:
        from app.models.auth_method import AuthMethod, AuthMethodType
        from app.models.org import Org
        from app.models.user import User, UserStatus
    except ImportError as exc:
        pytest.skip(f"Models not yet implemented (Plan 01): {exc}")

    plain_password = "TestP@ssw0rd123"
    hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, hash_len=32, salt_len=16)

    org = Org(name="Test Org", slug="test-org")
    async_session.add(org)
    await async_session.flush()

    user = User(
        normalized_email="test.user@wipro.com",
        display_name="Test User",
        org_id=org.id,
        status=UserStatus.ACTIVE,
    )
    async_session.add(user)
    await async_session.flush()

    auth_method = AuthMethod(
        user_id=user.id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=hasher.hash(plain_password),
        is_primary=True,
        must_change_password=False,
    )

    async_session.add(auth_method)
    await async_session.commit()
    await async_session.refresh(user)

    return user, plain_password


@pytest.fixture
async def seed_first_login_user(async_session: AsyncSession):
    """Seed first-login user requiring password change."""
    try:
        from app.models.auth_method import AuthMethod, AuthMethodType
        from app.models.org import Org
        from app.models.user import User, UserStatus
    except ImportError as exc:
        pytest.skip(f"Models not yet implemented (Plan 01): {exc}")

    plain_password = "TempP@ss12345"
    hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1, hash_len=32, salt_len=16)

    org = Org(name="New User Org", slug="new-user-org")
    async_session.add(org)
    await async_session.flush()

    user = User(
        normalized_email="new.user@wipro.com",
        display_name="New User",
        org_id=org.id,
        status=UserStatus.PENDING,
    )
    async_session.add(user)
    await async_session.flush()

    auth_method = AuthMethod(
        user_id=user.id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=hasher.hash(plain_password),
        is_primary=True,
        must_change_password=True,
    )

    async_session.add(auth_method)
    await async_session.commit()
    await async_session.refresh(user)

    return user, plain_password


# ---------------------------------------------------------------------------
# Phase 4 — RBAC integration test fixtures
# ---------------------------------------------------------------------------

SUPERADMIN_PASSWORD = "SuperAdmin123!@#"
PM_PASSWORD = "PMUser123!@#"
PO_PASSWORD = "POUser123!@#"
DEV_PASSWORD = "DevUser123!@#"
FDE_PASSWORD = "FDEUser123!@#"


def auth_header(token: str) -> dict[str, str]:
    """Build Authorization header for test requests."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_roles(async_session: AsyncSession):
    """Seed the 5 system roles with simplified capabilities (Phase 5 D-01).

    CRITICAL: Role.capabilities is a JSON column (list[str]), NOT a relationship.
    There is NO Capability class.  Use Role(capabilities=[...]) directly.
    """
    from app.models.role import Role

    roles_data = [
        ("superadmin", "Full platform access", [
            "platform:manage", "org:manage_users", "org:manage_settings",
            "sdlc:execute", "sdlc:view_pipelines",
            "integration:configure_tools", "integration:use_tools",
            "settings:manage_own", "admin:view_audit_log", "admin:manage_sessions",
        ]),  # 10 capabilities
        ("pm", "Project manager — creates and manages team members", [
            "team:manage_users", "integration:use_tools", "settings:manage_own",
        ]),  # 3 capabilities
        ("po_sm_ba", "Product owner, scrum master, business analyst — planning and requirements", [
            "sdlc:execute", "sdlc:view_pipelines",
            "integration:use_tools", "settings:manage_own",
        ]),  # 4 capabilities
        ("developer", "Software developer — code assistance, validation, documentation", [
            "sdlc:execute", "sdlc:view_pipelines",
            "integration:use_tools", "settings:manage_own",
        ]),  # 4 capabilities
        ("tester", "QA tester — test generation, validation, end-to-end testing", [
            "sdlc:execute", "sdlc:view_pipelines",
            "integration:use_tools", "settings:manage_own",
        ]),  # 4 capabilities
        ("mlops", "ML/AI operations — testing, code analysis, validation", [
            "sdlc:execute", "sdlc:view_pipelines",
            "integration:use_tools", "settings:manage_own",
        ]),  # 4 capabilities
    ]

    role_objects: list[Role] = []
    for name, description, caps in roles_data:
        role = Role(name=name, description=description, capabilities=caps)
        async_session.add(role)
        role_objects.append(role)
    await async_session.commit()
    for r in role_objects:
        await async_session.refresh(r)
    return {r.name: r for r in role_objects}


@pytest.fixture
async def seed_org(async_session: AsyncSession):
    """Seed a test organisation."""
    from app.models.org import Org

    org = Org(name="Wipro Test Org", slug="wipro-test-org")
    async_session.add(org)
    await async_session.flush()
    return org


@pytest.fixture
async def seed_superadmin(async_session: AsyncSession, seed_roles, seed_org):
    """Create an ACTIVE SuperAdmin user with password auth method and org-scoped role."""
    from app.models.auth_method import AuthMethod, AuthMethodType
    from app.models.role import UserRole
    from app.models.user import User, UserStatus
    from app.services.password_service import PasswordService

    user = User(
        normalized_email="admin@wipro.com",
        display_name="Super Admin",
        org_id=seed_org.id,
        status=UserStatus.ACTIVE,
    )
    async_session.add(user)
    await async_session.flush()

    auth_method = AuthMethod(
        user_id=user.id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=PasswordService.hash_password(SUPERADMIN_PASSWORD),
        is_primary=True,
        must_change_password=False,
    )
    async_session.add(auth_method)

    user_role = UserRole(
        user_id=user.id,
        role_id=seed_roles["superadmin"].id,
        scope_type="org",
        scope_id=seed_org.id,
        source="admin_assigned",
    )
    async_session.add(user_role)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.fixture
async def seed_pm(async_session: AsyncSession, seed_roles, seed_org, seed_superadmin):
    """Create an ACTIVE PM user in the same org."""
    from app.models.auth_method import AuthMethod, AuthMethodType
    from app.models.role import UserRole
    from app.models.user import User, UserStatus
    from app.services.password_service import PasswordService

    user = User(
        normalized_email="pm@wipro.com",
        display_name="PM User",
        org_id=seed_org.id,
        status=UserStatus.ACTIVE,
        created_by=seed_superadmin.id,
    )
    async_session.add(user)
    await async_session.flush()

    auth_method = AuthMethod(
        user_id=user.id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=PasswordService.hash_password(PM_PASSWORD),
        is_primary=True,
        must_change_password=False,
    )
    async_session.add(auth_method)

    user_role = UserRole(
        user_id=user.id,
        role_id=seed_roles["pm"].id,
        scope_type="org",
        scope_id=seed_org.id,
        source="admin_assigned",
    )
    async_session.add(user_role)
    await async_session.commit()
    await async_session.refresh(user)
    return user


# Backward-compat alias — tests not yet migrated can still request seed_orgadmin
seed_orgadmin = seed_pm


@pytest.fixture
async def seed_project(async_session: AsyncSession, seed_org, seed_pm):
    """Create an active project in the test org, owned by PM."""
    from app.models.project import Project

    project = Project(
        name="Test Project",
        slug="test-project",
        org_id=seed_org.id,
        created_by=seed_pm.id,
        is_active=True,
    )
    async_session.add(project)
    await async_session.commit()
    await async_session.refresh(project)
    return project


@pytest.fixture
async def seed_dev_user(async_session: AsyncSession, seed_roles, seed_org, seed_superadmin):
    """Create an ACTIVE developer user with project-scoped role."""
    import uuid as _uuid
    from app.models.auth_method import AuthMethod, AuthMethodType
    from app.models.role import UserRole
    from app.models.user import User, UserStatus
    from app.services.password_service import PasswordService

    user = User(
        normalized_email="dev@wipro.com",
        display_name="Dev User",
        org_id=seed_org.id,
        status=UserStatus.ACTIVE,
    )
    async_session.add(user)
    await async_session.flush()

    auth_method = AuthMethod(
        user_id=user.id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=PasswordService.hash_password(DEV_PASSWORD),
        is_primary=True,
        must_change_password=False,
    )
    async_session.add(auth_method)

    user_role = UserRole(
        user_id=user.id,
        role_id=seed_roles["developer"].id,
        scope_type="project",
        scope_id=str(_uuid.uuid4()),  # dummy project ref; no FK constraint
        source="admin_assigned",
    )
    async_session.add(user_role)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.fixture
async def superadmin_token(seed_superadmin, test_client):
    """Obtain a valid JWT access token for the SuperAdmin user."""
    response = await test_client.post(
        "/api/auth/login",
        json={"email": "admin@wipro.com", "password": SUPERADMIN_PASSWORD},
    )
    assert response.status_code == 200, f"SuperAdmin login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture
async def pm_token(seed_pm, test_client):
    """Obtain a valid JWT access token for the PM user."""
    response = await test_client.post(
        "/api/auth/login",
        json={"email": "pm@wipro.com", "password": PM_PASSWORD},
    )
    assert response.status_code == 200, f"PM login failed: {response.text}"
    return response.json()["access_token"]


# Backward-compat alias
orgadmin_token = pm_token


@pytest.fixture
async def dev_token(seed_dev_user, test_client):
    """Obtain a valid JWT access token for the developer user."""
    response = await test_client.post(
        "/api/auth/login",
        json={"email": "dev@wipro.com", "password": DEV_PASSWORD},
    )
    assert response.status_code == 200, f"Dev login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture
async def seed_activation_token(async_session: AsyncSession, seed_superadmin, seed_org):
    """Create a PENDING user with a valid activation token.

    Returns dict with 'user' (User) and 'raw_token' (str — unhashed).
    """
    from app.models.user import User, UserStatus
    from app.services.activation_service import ActivationService

    pending_user = User(
        normalized_email="newuser@wipro.com",
        display_name="New User",
        org_id=seed_org.id,
        status=UserStatus.PENDING,
    )
    async_session.add(pending_user)
    await async_session.flush()

    raw_token = await ActivationService.create_token(
        async_session,
        user_id=pending_user.id,
        created_by=seed_superadmin.id,
    )
    await async_session.commit()
    await async_session.refresh(pending_user)
    return {"user": pending_user, "raw_token": raw_token}


@pytest.fixture
async def seed_expired_activation_token(async_session: AsyncSession, seed_superadmin, seed_org):
    """Create a PENDING user with an EXPIRED activation token."""
    import hashlib
    import secrets
    from datetime import datetime, timedelta, timezone

    from app.models.activation_token import ActivationToken
    from app.models.user import User, UserStatus

    pending_user = User(
        normalized_email="expired@wipro.com",
        display_name="Expired Token User",
        org_id=seed_org.id,
        status=UserStatus.PENDING,
    )
    async_session.add(pending_user)
    await async_session.flush()

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    activation = ActivationToken(
        user_id=pending_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        created_by=seed_superadmin.id,
    )
    async_session.add(activation)
    await async_session.commit()
    await async_session.refresh(pending_user)
    return {"user": pending_user, "raw_token": raw_token}


# ---------------------------------------------------------------------------
# Phase 5 — Additional role user fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def seed_po_user(async_session: AsyncSession, seed_roles, seed_org, seed_superadmin):
    """Create an ACTIVE PO user in the same org."""
    from app.models.auth_method import AuthMethod, AuthMethodType
    from app.models.role import UserRole
    from app.models.user import User, UserStatus
    from app.services.password_service import PasswordService

    user = User(
        normalized_email="po@wipro.com",
        display_name="PO User",
        org_id=seed_org.id,
        status=UserStatus.ACTIVE,
    )
    async_session.add(user)
    await async_session.flush()

    auth_method = AuthMethod(
        user_id=user.id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=PasswordService.hash_password(PO_PASSWORD),
        is_primary=True,
        must_change_password=False,
    )
    async_session.add(auth_method)

    import uuid as _uuid
    user_role = UserRole(
        user_id=user.id,
        role_id=seed_roles["po_sm_ba"].id,
        scope_type="project",
        scope_id=str(_uuid.uuid4()),  # dummy project ref; no FK constraint
        source="admin_assigned",
    )
    async_session.add(user_role)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.fixture
async def seed_fde_user(async_session: AsyncSession, seed_roles, seed_org, seed_superadmin):
    """Create an ACTIVE MLOps user in the same org."""
    from app.models.auth_method import AuthMethod, AuthMethodType
    from app.models.role import UserRole
    from app.models.user import User, UserStatus
    from app.services.password_service import PasswordService

    user = User(
        normalized_email="fde@wipro.com",
        display_name="MLOps User",
        org_id=seed_org.id,
        status=UserStatus.ACTIVE,
    )
    async_session.add(user)
    await async_session.flush()

    auth_method = AuthMethod(
        user_id=user.id,
        method_type=AuthMethodType.PASSWORD,
        provider="local",
        credential_hash=PasswordService.hash_password(FDE_PASSWORD),
        is_primary=True,
        must_change_password=False,
    )
    async_session.add(auth_method)

    import uuid as _uuid
    user_role = UserRole(
        user_id=user.id,
        role_id=seed_roles["mlops"].id,
        scope_type="project",
        scope_id=str(_uuid.uuid4()),  # dummy project ref; no FK constraint
        source="admin_assigned",
    )
    async_session.add(user_role)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest.fixture
async def po_token(seed_po_user, test_client):
    """Obtain a valid JWT access token for the PO user."""
    response = await test_client.post(
        "/api/auth/login",
        json={"email": "po@wipro.com", "password": PO_PASSWORD},
    )
    assert response.status_code == 200, f"PO login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture
async def fde_token(seed_fde_user, test_client):
    """Obtain a valid JWT access token for the FDE user."""
    response = await test_client.post(
        "/api/auth/login",
        json={"email": "fde@wipro.com", "password": FDE_PASSWORD},
    )
    assert response.status_code == 200, f"FDE login failed: {response.text}"
    return response.json()["access_token"]


# ---------------------------------------------------------------------------
# Convenience header fixtures for Phase 5 tests
# ---------------------------------------------------------------------------


@pytest.fixture
def superadmin_headers(superadmin_token):
    """Authorization headers for SuperAdmin."""
    return {"Authorization": f"Bearer {superadmin_token}"}


@pytest.fixture
def pm_headers(pm_token):
    """Authorization headers for PM."""
    return {"Authorization": f"Bearer {pm_token}"}


@pytest.fixture
def po_headers(po_token):
    """Authorization headers for PO."""
    return {"Authorization": f"Bearer {po_token}"}


@pytest.fixture
def devtest_headers(dev_token):
    """Authorization headers for Dev/Test."""
    return {"Authorization": f"Bearer {dev_token}"}


@pytest.fixture
def fde_headers(fde_token):
    """Authorization headers for FDE."""
    return {"Authorization": f"Bearer {fde_token}"}


# ---------------------------------------------------------------------------
# Phase 5 — Role-agent mapping fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def seed_role_agents(async_session: AsyncSession, seed_roles):
    """Seed role-agent mappings matching migration 007 (6-role model)."""
    from app.models.role import RoleAgent

    sa_id = seed_roles["superadmin"].id
    pm_id = seed_roles["pm"].id
    posmba_id = seed_roles["po_sm_ba"].id
    dev_id = seed_roles["developer"].id
    tst_id = seed_roles["tester"].id
    ml_id = seed_roles["mlops"].id

    agent_mappings = [
        # SuperAdmin: all 11 agents
        (sa_id, "brd-generator", "BRD Generator"),
        (sa_id, "brd-summary", "BRD Summary"),
        (sa_id, "user-story-generator", "User Stories Creator"),
        (sa_id, "user-story-validator", "User Stories Validator"),
        (sa_id, "test-case", "Test Case"),
        (sa_id, "test-script", "Test Script"),
        (sa_id, "test-data", "Test Data"),
        (sa_id, "test-data-generator", "Test Data Generator"),
        (sa_id, "end-to-end-test", "End-to-End Test"),
        (sa_id, "user-manual", "User Manual"),
        (sa_id, "code-assistant", "Code Analysis"),
        # PM: 3 planning agents
        (pm_id, "brd-generator", "BRD Generator"),
        (pm_id, "brd-summary", "BRD Summary"),
        (pm_id, "user-story-generator", "User Stories Creator"),
        # PO/SM/BA: 4 agents
        (posmba_id, "brd-generator", "BRD Generator"),
        (posmba_id, "brd-summary", "BRD Summary"),
        (posmba_id, "user-story-generator", "User Stories Creator"),
        (posmba_id, "user-manual", "User Manual"),
        # Developer: 3 agents
        (dev_id, "user-story-validator", "User Stories Validator"),
        (dev_id, "user-manual", "User Manual"),
        (dev_id, "code-assistant", "Code Analysis"),
        # Tester: 6 agents
        (tst_id, "user-story-validator", "User Stories Validator"),
        (tst_id, "test-case", "Test Case"),
        (tst_id, "test-script", "Test Script"),
        (tst_id, "test-data", "Test Data"),
        (tst_id, "test-data-generator", "Test Data Generator"),
        (tst_id, "end-to-end-test", "End-to-End Test"),
        # MLOps: 7 agents
        (ml_id, "user-story-validator", "User Stories Validator"),
        (ml_id, "test-case", "Test Case"),
        (ml_id, "test-script", "Test Script"),
        (ml_id, "test-data", "Test Data"),
        (ml_id, "test-data-generator", "Test Data Generator"),
        (ml_id, "end-to-end-test", "End-to-End Test"),
        (ml_id, "code-assistant", "Code Analysis"),
    ]
    for role_id, agent_id, agent_name in agent_mappings:
        async_session.add(RoleAgent(role_id=role_id, agent_id=agent_id, agent_name=agent_name))
    await async_session.commit()
