"""001 — Unified schema: complete WEGA auth database.

Replaces migrations 001-012 with a single clean-slate migration.
Creates all tables, enum types, and seeds reference data
(org, superadmin user, roles, role-agent mappings, service registry).
"""

from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Alembic revision identifiers
# ---------------------------------------------------------------------------
revision: str = "001_unified_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Enum types (Postgres native enums)
# ---------------------------------------------------------------------------
USER_STATUS_ENUM = sa.Enum(
    "PENDING", "ACTIVE", "SUSPENDED", "DEACTIVATED", name="userstatus"
)
AUTH_METHOD_TYPE_ENUM = sa.Enum(
    "PASSWORD", "SSO_OIDC", "SSO_SAML", name="authmethodtype"
)

# ---------------------------------------------------------------------------
# Fixed UUIDs — seed data
# ---------------------------------------------------------------------------
ORG_ID = "00000000-0000-4000-8000-000000000001"
ADMIN_USER_ID = "00000000-0000-4000-8000-000000000002"

SUPERADMIN_ROLE_ID = "00000000-0000-4000-8000-000000000010"
PM_ROLE_ID = "00000000-0000-4000-8000-000000000012"
POSMBA_ROLE_ID = "00000000-0000-4000-8000-000000000013"
DEVELOPER_ROLE_ID = "00000000-0000-4000-8000-000000000016"
TESTER_ROLE_ID = "00000000-0000-4000-8000-000000000017"
MLOPS_ROLE_ID = "00000000-0000-4000-8000-000000000018"

ADMIN_USER_ROLE_ID = "00000000-0000-4000-8000-000000000021"

# Service-registry UUIDs
_SVC_JIRA = "00000000-0000-4000-9000-000000000001"
_SVC_GITHUB = "00000000-0000-4000-9000-000000000002"
_SVC_SHAREPOINT = "00000000-0000-4000-9000-000000000003"
_SVC_CONFLUENCE = "00000000-0000-4000-9000-000000000004"
_SVC_HARNESS_R = "00000000-0000-4000-9000-000000000005"
_SVC_HARNESS_P = "00000000-0000-4000-9000-000000000006"
_SVC_QTEST = "00000000-0000-4000-9000-000000000007"
_SVC_SONARQUBE = "00000000-0000-4000-9000-000000000008"
_SVC_SNYK = "00000000-0000-4000-9000-000000000009"
_SVC_TRIVY = "00000000-0000-4000-9000-000000000010"

# ---------------------------------------------------------------------------
# Service field definitions (final state from migration 011)
# ---------------------------------------------------------------------------
SERVICE_FIELD_DEFS = {
    "jira": {
        "defaults": {"url": "", "projectKey": "", "email": "", "_auth_type": "basic"},
        "fields": [
            {"key": "url", "label": "Instance URL", "placeholder": "https://your-org.atlassian.net", "required": True},
            {"key": "projectKey", "label": "Project Key", "placeholder": "PROJ", "required": True},
            {"key": "email", "label": "Service Account Email", "placeholder": "user@company.com", "required": True, "type": "email"},
            {"key": "patToken", "label": "PAT Token", "placeholder": "Enter your Jira PAT", "isSecret": True, "required": True},
        ],
    },
    "github": {
        "defaults": {"url": "", "_auth_type": "bearer"},
        "fields": [
            {"key": "url", "label": "Repository URL", "placeholder": "https://github.com/org/repo", "required": True},
            {"key": "patToken", "label": "Personal Access Token", "placeholder": "ghp_…", "isSecret": True, "required": True},
        ],
    },
    "confluence": {
        "defaults": {"url": "", "spaceKey": "", "spaceId": "", "email": "", "_auth_type": "basic"},
        "fields": [
            {"key": "url", "label": "Instance URL", "placeholder": "https://your-org.atlassian.net", "required": True},
            {"key": "spaceKey", "label": "Space Key", "placeholder": "DOCS", "required": True},
            {"key": "spaceId", "label": "Space ID", "placeholder": "36569092", "required": True},
            {"key": "email", "label": "Service Account Email", "placeholder": "user@company.com", "required": True, "type": "email"},
            {"key": "patToken", "label": "PAT Token", "placeholder": "Enter your Confluence PAT", "isSecret": True, "required": True},
        ],
    },
    "sharepoint": {
        "defaults": {"url": "", "_auth_type": "bearer"},
        "fields": [
            {"key": "url", "label": "Site URL", "placeholder": "https://your-org.sharepoint.com/sites/...", "required": True},
            {"key": "patToken", "label": "Access Token", "placeholder": "Enter access token", "isSecret": True, "required": True},
        ],
    },
    "sonarqube": {
        "defaults": {"url": "", "_auth_type": "bearer"},
        "fields": [
            {"key": "url", "label": "Instance URL", "placeholder": "https://sonarqube.example.com", "required": True},
            {"key": "patToken", "label": "Token", "placeholder": "Enter SonarQube token", "isSecret": True, "required": True},
        ],
    },
    "qtest": {
        "defaults": {"url": "", "qtestProjectId": "", "_auth_type": "bearer"},
        "fields": [
            {"key": "url", "label": "API URL", "placeholder": "https://your-org.qtestnet.com/api/v3", "required": True},
            {"key": "qtestProjectId", "label": "Project ID", "placeholder": "123456", "required": True},
            {"key": "patToken", "label": "API Token", "placeholder": "Enter qTest API token", "isSecret": True, "required": True},
        ],
    },
    "harness-pipelines": {
        "defaults": {"url": "", "accountId": "", "orgIdentifier": "", "projectIdentifier": "", "_auth_type": "api-key"},
        "fields": [
            {"key": "url", "label": "Harness URL", "placeholder": "https://app.harness.io", "required": True},
            {"key": "accountId", "label": "Account ID", "placeholder": "abc123", "required": True},
            {"key": "orgIdentifier", "label": "Org Identifier", "placeholder": "default", "required": True},
            {"key": "projectIdentifier", "label": "Project Identifier", "placeholder": "my_project", "required": True},
            {"key": "patToken", "label": "API Key", "placeholder": "Enter Harness API key", "isSecret": True, "required": True},
        ],
    },
    "harness-repo": {
        "defaults": {"url": "", "accountId": "", "orgIdentifier": "", "repoIdentifier": "", "_auth_type": "api-key"},
        "fields": [
            {"key": "url", "label": "Harness URL", "placeholder": "https://app.harness.io", "required": True},
            {"key": "accountId", "label": "Account ID", "placeholder": "abc123", "required": True},
            {"key": "orgIdentifier", "label": "Org Identifier", "placeholder": "default", "required": True},
            {"key": "repoIdentifier", "label": "Repo Identifier", "placeholder": "my_repo", "required": True},
            {"key": "patToken", "label": "API Key", "placeholder": "Enter Harness API key", "isSecret": True, "required": True},
        ],
    },
    "snyk": {
        "defaults": {"orgId": "", "_auth_type": "token"},
        "fields": [
            {"key": "orgId", "label": "Snyk Org ID", "placeholder": "your-snyk-org-id", "required": True},
            {"key": "patToken", "label": "API Token", "placeholder": "Enter Snyk API token", "isSecret": True, "required": True},
        ],
    },
    "trivy": {
        "defaults": {"serverUrl": "", "_auth_type": "none"},
        "fields": [
            {"key": "serverUrl", "label": "Trivy Server URL", "placeholder": "http://trivy-server:4954", "required": True},
            {"key": "patToken", "label": "Token (optional)", "placeholder": "Enter token if required", "isSecret": True},
        ],
    },
}

# ---------------------------------------------------------------------------
# Role capabilities (final merged state)
# ---------------------------------------------------------------------------
ROLE_CAPABILITIES = {
    SUPERADMIN_ROLE_ID: [
        "platform:manage", "org:manage_users", "org:manage_settings",
        "sdlc:execute", "sdlc:view_pipelines",
        "integration:configure_tools", "integration:use_tools",
        "settings:manage_own", "admin:view_audit_log", "admin:manage_sessions",
        "project:create", "project:manage", "project:manage_members",
        "project:configure_integrations",
    ],
    PM_ROLE_ID: [
        "team:manage_users", "sdlc:execute", "sdlc:view_pipelines",
        "integration:use_tools", "settings:manage_own",
        "project:create", "project:manage_members",
    ],
    POSMBA_ROLE_ID: [
        "sdlc:execute", "sdlc:view_pipelines", "integration:use_tools",
        "settings:manage_own",
    ],
    DEVELOPER_ROLE_ID: [
        "sdlc:execute", "sdlc:view_pipelines", "integration:use_tools",
        "settings:manage_own",
    ],
    TESTER_ROLE_ID: [
        "sdlc:execute", "sdlc:view_pipelines", "integration:use_tools",
        "settings:manage_own",
    ],
    MLOPS_ROLE_ID: [
        "sdlc:execute", "sdlc:view_pipelines", "integration:use_tools",
        "settings:manage_own", "project:configure_integrations",
        "integration:configure_tools",
    ],
}


# ===================================================================
# upgrade
# ===================================================================
def upgrade() -> None:
    # -- 1. orgs ---------------------------------------------------
    op.create_table(
        "orgs",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("slug", sa.Text, nullable=False, unique=True),
        sa.Column("settings", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # -- 2. users --------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("normalized_email", sa.Text, nullable=False, unique=True),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("org_id", sa.Text, sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column(
            "status",
            USER_STATUS_ENUM,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("created_by", sa.Text, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 3. auth_methods -------------------------------------------
    op.create_table(
        "auth_methods",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "user_id",
            sa.Text,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method_type", AUTH_METHOD_TYPE_ENUM, nullable=False),
        sa.Column(
            "provider", sa.String(100), nullable=False, server_default="local"
        ),
        sa.Column("provider_subject_id", sa.String(500), nullable=True),
        sa.Column("credential_hash", sa.Text, nullable=True),
        sa.Column(
            "is_primary", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "must_change_password",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "failed_login_attempts",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "lockout_backoff_level",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 4. sessions -----------------------------------------------
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "user_id",
            sa.Text,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_family_id", sa.Text, nullable=False),
        sa.Column("refresh_token_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_info", sa.Text, nullable=True),
        sa.Column("ip_address", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "replaced_by", sa.Text, sa.ForeignKey("sessions.id"), nullable=True
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text, nullable=True),
    )

    # -- 5. roles --------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("capabilities", sa.JSON, nullable=False, server_default="[]"),
    )

    # -- 6. role_agents --------------------------------------------
    op.create_table(
        "role_agents",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "role_id",
            sa.Text,
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.String(100), nullable=False),
        sa.Column("agent_name", sa.Text, nullable=False),
    )

    # -- 7. user_roles ---------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "user_id",
            sa.Text,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role_id", sa.Text, sa.ForeignKey("roles.id"), nullable=False),
        sa.Column(
            "scope_type", sa.String(50), nullable=False, server_default="org"
        ),
        sa.Column("scope_id", sa.Text, nullable=True),
        sa.Column(
            "source", sa.String(50), nullable=False, server_default="admin_assigned"
        ),
        sa.Column("assigned_by", sa.Text, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
    )

    # -- 8. projects -----------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("org_id", sa.Text, sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_by", sa.Text, sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("org_id", "slug", name="uq_projects_org_slug"),
    )

    # -- 9. activation_tokens --------------------------------------
    op.create_table(
        "activation_tokens",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "user_id",
            sa.Text,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # -- 10. service_registry --------------------------------------
    op.create_table(
        "service_registry",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("tool_id", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("icon", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.Text, nullable=True),
        sa.Column("color", sa.Text, nullable=True),
        sa.Column("default_config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "enabled", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # -- 11. project_settings --------------------------------------
    op.create_table(
        "project_settings",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "project_id",
            sa.Text,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            sa.Text,
            sa.ForeignKey("service_registry.id"),
            nullable=False,
        ),
        sa.Column("config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column(
            "is_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "configured_by", sa.Text, sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "service_id", name="uq_project_service"),
    )

    # -- 12. project_secrets ---------------------------------------
    op.create_table(
        "project_secrets",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "project_id",
            sa.Text,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            sa.Text,
            sa.ForeignKey("service_registry.id"),
            nullable=False,
        ),
        sa.Column("secret_key", sa.Text, nullable=False),
        sa.Column("encrypted_value", sa.Text, nullable=False),
        sa.Column("updated_by", sa.Text, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_id", "service_id", "secret_key",
            name="uq_project_service_secret",
        ),
    )

    # -- 13. audit_log ---------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Text, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("resource_type", sa.Text, nullable=True),
        sa.Column("resource_id", sa.Text, nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.Text, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )

    # ===============================================================
    # SEED DATA
    # ===============================================================
    _now = datetime.now(timezone.utc)

    # -- Org -------------------------------------------------------
    orgs_t = sa.table(
        "orgs",
        sa.column("id", sa.Text),
        sa.column("name", sa.Text),
        sa.column("slug", sa.Text),
        sa.column("settings", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(orgs_t, [
        {
            "id": ORG_ID,
            "name": "Wipro",
            "slug": "wipro",
            "settings": {},
            "created_at": _now,
            "updated_at": _now,
        },
    ])

    # -- SuperAdmin user -------------------------------------------
    users_t = sa.table(
        "users",
        sa.column("id", sa.Text),
        sa.column("normalized_email", sa.Text),
        sa.column("display_name", sa.Text),
        sa.column("org_id", sa.Text),
        sa.column("status", USER_STATUS_ENUM),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(users_t, [
        {
            "id": ADMIN_USER_ID,
            "normalized_email": "aniket.ashtikar@wipro.com",
            "display_name": "Aniket Ashtikar",
            "org_id": ORG_ID,
            "status": "PENDING",
            "created_at": _now,
            "updated_at": _now,
        },
    ])

    # -- Roles -----------------------------------------------------
    roles_t = sa.table(
        "roles",
        sa.column("id", sa.Text),
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
        sa.column("capabilities", sa.JSON),
    )
    op.bulk_insert(roles_t, [
        {"id": SUPERADMIN_ROLE_ID, "name": "superadmin", "description": "Full platform administrator", "capabilities": ROLE_CAPABILITIES[SUPERADMIN_ROLE_ID]},
        {"id": PM_ROLE_ID, "name": "pm", "description": "Project Manager", "capabilities": ROLE_CAPABILITIES[PM_ROLE_ID]},
        {"id": POSMBA_ROLE_ID, "name": "po_sm_ba", "description": "Product Owner / Scrum Master / Business Analyst", "capabilities": ROLE_CAPABILITIES[POSMBA_ROLE_ID]},
        {"id": DEVELOPER_ROLE_ID, "name": "developer", "description": "Developer", "capabilities": ROLE_CAPABILITIES[DEVELOPER_ROLE_ID]},
        {"id": TESTER_ROLE_ID, "name": "tester", "description": "Tester / QA", "capabilities": ROLE_CAPABILITIES[TESTER_ROLE_ID]},
        {"id": MLOPS_ROLE_ID, "name": "mlops", "description": "MLOps Engineer", "capabilities": ROLE_CAPABILITIES[MLOPS_ROLE_ID]},
    ])

    # -- SA user_role assignment -----------------------------------
    user_roles_t = sa.table(
        "user_roles",
        sa.column("id", sa.Text),
        sa.column("user_id", sa.Text),
        sa.column("role_id", sa.Text),
        sa.column("scope_type", sa.String),
        sa.column("scope_id", sa.Text),
        sa.column("source", sa.String),
        sa.column("assigned_by", sa.Text),
        sa.column("assigned_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(user_roles_t, [
        {
            "id": ADMIN_USER_ROLE_ID,
            "user_id": ADMIN_USER_ID,
            "role_id": SUPERADMIN_ROLE_ID,
            "scope_type": "platform",
            "scope_id": None,
            "source": "seed",
            "assigned_by": None,
            "assigned_at": _now,
        },
    ])

    # -- Role-Agent mappings (37 rows) -----------------------------
    # Agent catalog
    AGENTS = {
        "brd-generator": "BRD Generator",
        "brd-summary": "BRD Summary",
        "user-story-generator": "User Stories Creator",
        "user-story-validator": "User Stories Validator",
        "test-case": "Test Case",
        "test-script": "Test Script",
        "test-data": "Test Data",
        "test-data-generator": "Test Data Generator",
        "end-to-end-test": "End-to-End Test",
        "user-manual": "User Manual",
        "code-assistant": "Code Analysis",
    }

    role_agents_t = sa.table(
        "role_agents",
        sa.column("id", sa.Text),
        sa.column("role_id", sa.Text),
        sa.column("agent_id", sa.String),
        sa.column("agent_name", sa.Text),
    )

    def _ra(prefix_num: int, role_id: str, agent_id: str, agent_name: str) -> dict:
        return {
            "id": f"00000000-0000-4000-8000-10000000{prefix_num:04d}",
            "role_id": role_id,
            "agent_id": agent_id,
            "agent_name": agent_name,
        }

    # SuperAdmin → 11 agents (XX = 01-11)
    sa_agents = [
        "brd-generator", "brd-summary", "user-story-generator",
        "user-story-validator", "test-case", "test-script", "test-data",
        "test-data-generator", "end-to-end-test", "user-manual",
        "code-assistant",
    ]
    ra_rows = [_ra(i, SUPERADMIN_ROLE_ID, a, AGENTS[a]) for i, a in enumerate(sa_agents, start=1)]

    # PM → all 11 agents (XX = 21-31)
    pm_agents = list(AGENTS.keys())
    ra_rows += [_ra(i, PM_ROLE_ID, a, AGENTS[a]) for i, a in enumerate(pm_agents, start=21)]

    # PO/SM/BA → all 11 agents (XX = 41-51)
    posmba_agents = list(AGENTS.keys())
    ra_rows += [_ra(i, POSMBA_ROLE_ID, a, AGENTS[a]) for i, a in enumerate(posmba_agents, start=41)]

    # Developer → 3 agents (XX = 51-53)
    dev_agents = ["user-story-validator", "user-manual", "code-assistant"]
    ra_rows += [_ra(i, DEVELOPER_ROLE_ID, a, AGENTS[a]) for i, a in enumerate(dev_agents, start=51)]

    # Tester → 6 agents (XX = 61-66)
    tst_agents = [
        "user-story-validator", "test-case", "test-script",
        "test-data", "test-data-generator", "end-to-end-test",
    ]
    ra_rows += [_ra(i, TESTER_ROLE_ID, a, AGENTS[a]) for i, a in enumerate(tst_agents, start=61)]

    # MLOps → 7 agents (XX = 71-77)
    ml_agents = [
        "user-story-validator", "test-case", "test-script",
        "test-data", "test-data-generator", "end-to-end-test",
        "code-assistant",
    ]
    ra_rows += [_ra(i, MLOPS_ROLE_ID, a, AGENTS[a]) for i, a in enumerate(ml_agents, start=71)]

    op.bulk_insert(role_agents_t, ra_rows)

    # -- Service Registry (10 tools) ------------------------------
    svc_t = sa.table(
        "service_registry",
        sa.column("id", sa.Text),
        sa.column("tool_id", sa.Text),
        sa.column("name", sa.Text),
        sa.column("icon", sa.Text),
        sa.column("description", sa.Text),
        sa.column("category", sa.Text),
        sa.column("color", sa.Text),
        sa.column("default_config", sa.JSON),
        sa.column("enabled", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    svc_rows = [
        {"id": _SVC_JIRA, "tool_id": "jira", "name": "Jira", "icon": "📋", "description": "Project Management", "category": "ALM", "color": "from-blue-500 to-blue-600", "default_config": SERVICE_FIELD_DEFS["jira"], "enabled": True, "created_at": _now},
        {"id": _SVC_GITHUB, "tool_id": "github", "name": "GitHub", "icon": "🐙", "description": "Code Repository", "category": "SCM", "color": "from-gray-700 to-gray-900", "default_config": SERVICE_FIELD_DEFS["github"], "enabled": True, "created_at": _now},
        {"id": _SVC_SHAREPOINT, "tool_id": "sharepoint", "name": "SharePoint", "icon": "📁", "description": "Document Management", "category": "WIKI", "color": "from-cyan-500 to-blue-600", "default_config": SERVICE_FIELD_DEFS["sharepoint"], "enabled": True, "created_at": _now},
        {"id": _SVC_CONFLUENCE, "tool_id": "confluence", "name": "Confluence", "icon": "📝", "description": "Documentation", "category": "WIKI", "color": "from-blue-600 to-indigo-600", "default_config": SERVICE_FIELD_DEFS["confluence"], "enabled": True, "created_at": _now},
        {"id": _SVC_HARNESS_R, "tool_id": "harness-repo", "name": "Harness Repo", "icon": "🔗", "description": "Artifact Repository", "category": "CI", "color": "from-purple-500 to-pink-500", "default_config": SERVICE_FIELD_DEFS["harness-repo"], "enabled": True, "created_at": _now},
        {"id": _SVC_HARNESS_P, "tool_id": "harness-pipelines", "name": "Harness Pipelines", "icon": "⚡", "description": "CI/CD Pipelines", "category": "CD", "color": "from-orange-500 to-red-500", "default_config": SERVICE_FIELD_DEFS["harness-pipelines"], "enabled": True, "created_at": _now},
        {"id": _SVC_QTEST, "tool_id": "qtest", "name": "QTest", "icon": "🧪", "description": "Test Management", "category": "CQ", "color": "from-emerald-500 to-green-600", "default_config": SERVICE_FIELD_DEFS["qtest"], "enabled": True, "created_at": _now},
        {"id": _SVC_SONARQUBE, "tool_id": "sonarqube", "name": "SonarQube", "icon": "🔍", "description": "Code Quality", "category": "CQ", "color": "from-green-500 to-teal-500", "default_config": SERVICE_FIELD_DEFS["sonarqube"], "enabled": True, "created_at": _now},
        {"id": _SVC_SNYK, "tool_id": "snyk", "name": "Snyk SCA", "icon": "🛡️", "description": "Security Scanning", "category": "CQ", "color": "from-purple-600 to-blue-600", "default_config": SERVICE_FIELD_DEFS["snyk"], "enabled": True, "created_at": _now},
        {"id": _SVC_TRIVY, "tool_id": "trivy", "name": "Trivy Scan", "icon": "🔒", "description": "Vulnerability Scanner", "category": "CQ", "color": "from-red-500 to-pink-500", "default_config": SERVICE_FIELD_DEFS["trivy"], "enabled": True, "created_at": _now},
    ]
    op.bulk_insert(svc_t, svc_rows)


# ===================================================================
# downgrade
# ===================================================================
def downgrade() -> None:
    # Drop tables in reverse FK order
    op.drop_table("audit_log")
    op.drop_table("project_secrets")
    op.drop_table("project_settings")
    op.drop_table("service_registry")
    op.drop_table("activation_tokens")
    op.drop_table("projects")
    op.drop_table("user_roles")
    op.drop_table("role_agents")
    op.drop_table("roles")
    op.drop_table("sessions")
    op.drop_table("auth_methods")
    op.drop_table("users")
    op.drop_table("orgs")

    # Drop enum types
    bind = op.get_bind()
    AUTH_METHOD_TYPE_ENUM.drop(bind, checkfirst=True)
    USER_STATUS_ENUM.drop(bind, checkfirst=True)
