"""
E2E demo setup — follows the correct WEGA onboarding hierarchy:

  SuperAdmin → creates PM
  PM → activates, creates project, adds MLOps to team
  MLOps → activates, configures Jira + Confluence for the project

After running, any project member can log in and see the sidebar.

Idempotent: safe to re-run — skips resources that already exist.

Usage:
    python scripts/_setup_demo.py                           # local (localhost:8090)
    AUTH_SERVICE_URL=http://remote:8090 python scripts/_setup_demo.py  # remote
"""
import requests
import json
import os
import sys
import re

BASE = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8090")

PAT_TOKEN = (
    "ATATT3xFfGF0qkG6vx3wZp7VcuHoAYoaF6A_uAT6VLDbi5-frjVRTYfjdWw4I99LhXZ4T72SBCSDAc6u"
    "Cp5dzF__etAiMqDPPqQPDzj73KSEGBAZ98xseEJh9X3RkVzNb8nAk_QE-ztWhkOUQwxYwLz5k5YQU492a"
    "Xblxzy48r3o4WE_BoEn_Cg=50F4F372"
)


def login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        print(f"  ✗ Login failed for {email}: {r.status_code} {r.text}")
        sys.exit(1)
    data = r.json()
    print(f"  ✓ Logged in as {email}  project_id={data['user'].get('project_id')}")
    return data["access_token"], data["user"]


def activate(activation_url, password):
    """Extract token from activation URL and call activate endpoint."""
    token = activation_url.split("token=")[-1]
    r = requests.post(f"{BASE}/api/auth/activate", json={
        "token": token,
        "password": password,
        "confirm_password": password,
    })
    if r.status_code == 200:
        print(f"  ✓ Account activated")
        return r.json()
    elif r.status_code in (400, 409, 410):
        # Already activated or token expired/used — try login instead
        print(f"  ⊘ Activation returned {r.status_code} (likely already activated)")
        return None
    else:
        print(f"  ✗ Activation failed: {r.status_code} {r.text}")
        sys.exit(1)


def create_user(token, email, display_name, role_assignments):
    """Create a user; if already exists (409), return existing user info."""
    r = requests.post(f"{BASE}/api/users", headers=headers(token), json={
        "email": email,
        "display_name": display_name,
        "role_assignments": role_assignments,
    })
    if r.status_code == 201:
        data = r.json()
        print(f"  ✓ Created {email} (id={data['user']['id']})")
        return data, True  # (response, is_new)
    elif r.status_code in (400, 409):
        print(f"  ⊘ {email} already exists (status {r.status_code})")
        return None, False
    else:
        print(f"  ✗ Create user failed: {r.status_code} {r.text}")
        sys.exit(1)


def create_project(token, name, slug, description):
    """Create a project; if already exists, find it from user's project list."""
    r = requests.post(f"{BASE}/api/projects", headers=headers(token), json={
        "name": name, "slug": slug, "description": description,
    })
    if r.status_code == 201:
        project = r.json()
        print(f"  ✓ Project created: {project['name']} ({project['id']})")
        return project["id"]
    elif r.status_code in (400, 409):
        print(f"  ⊘ Project '{slug}' may already exist (status {r.status_code})")
        # Try to find it via project list
        r2 = requests.get(f"{BASE}/api/projects", headers=headers(token))
        if r2.status_code == 200:
            projects = r2.json() if isinstance(r2.json(), list) else r2.json().get("projects", [])
            for p in projects:
                if p.get("slug") == slug:
                    print(f"  ✓ Found existing project: {p['name']} ({p['id']})")
                    return p["id"]
        print(f"  ✗ Could not find existing project '{slug}'")
        sys.exit(1)
    else:
        print(f"  ✗ Create project failed: {r.status_code} {r.text}")
        sys.exit(1)


def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── Step 1: SuperAdmin creates PM user ──────────────────────────
print("=" * 60)
print("STEP 1: SuperAdmin creates PM user")
print("=" * 60)

sa_token, sa_user = login("aniket.ashtikar@wipro.com", "WegaAdmin1!@#")

pm_data, pm_is_new = create_user(sa_token, "ravi.kumar@wipro.com", "Ravi Kumar",
    [{"role_name": "pm", "scope_type": "org"}])
pm_activation_url = pm_data["activation_url"] if pm_is_new else None


# ── Step 2: PM activates account ────────────────────────────────
print("\n" + "=" * 60)
print("STEP 2: PM activates account")
print("=" * 60)

if pm_activation_url:
    activate(pm_activation_url, "PMPassword1!@#")
else:
    print("  ⊘ Skipping activation (user already exists)")


# ── Step 3: PM logs in and creates project ──────────────────────
print("\n" + "=" * 60)
print("STEP 3: PM creates project")
print("=" * 60)

pm_token, pm_user = login("ravi.kumar@wipro.com", "PMPassword1!@#")

PROJECT_ID = create_project(pm_token, "WEGA Platform", "wega-platform",
    "Enterprise software engineering platform powered by AI")


# ── Step 4: PM adds MLOps user to team ──────────────────────────
print("\n" + "=" * 60)
print("STEP 4: PM adds MLOps + Developer to team")
print("=" * 60)

# PM needs to re-login to get project_id in JWT after creating project
pm_token, pm_user = login("ravi.kumar@wipro.com", "PMPassword1!@#")

mlops_data, mlops_is_new = create_user(pm_token, "arun.patel@wipro.com", "Arun Patel",
    [{"role_name": "mlops", "scope_type": "project", "scope_id": PROJECT_ID}])
mlops_activation_url = mlops_data["activation_url"] if mlops_is_new else None

dev_data, dev_is_new = create_user(pm_token, "priya.sharma@wipro.com", "Priya Sharma",
    [{"role_name": "developer", "scope_type": "project", "scope_id": PROJECT_ID}])
dev_activation_url = dev_data["activation_url"] if dev_is_new else None


# ── Step 5: MLOps activates account ─────────────────────────────
print("\n" + "=" * 60)
print("STEP 5: MLOps activates account")
print("=" * 60)

if mlops_activation_url:
    activate(mlops_activation_url, "MLOpsPass1!@#$")
else:
    print("  ⊘ Skipping activation (user already exists)")


# ── Step 6: MLOps configures Jira + Confluence ──────────────────
print("\n" + "=" * 60)
print("STEP 6: MLOps configures Jira + Confluence")
print("=" * 60)

mlops_token, mlops_user = login("arun.patel@wipro.com", "MLOpsPass1!@#$")

# Get service IDs
r = requests.get(f"{BASE}/api/services", headers=headers(mlops_token))
svc_map = {s["toolId"]: s["id"] for s in r.json().get("services", [])}

# Configure Jira (PUT is idempotent)
jira_id = svc_map["jira"]
r = requests.put(
    f"{BASE}/api/projects/{PROJECT_ID}/settings/{jira_id}",
    headers=headers(mlops_token),
    json={
        "config": {
            "url": "https://wegabuildiq.atlassian.net",
            "projectKey": "WEGAAIDEMO",
            "email": "manibharathy.sekar@wipro.com",
        },
        "secrets": {"patToken": PAT_TOKEN},
        "is_enabled": True,
    },
)
print(f"  Jira: {r.status_code} -> {r.json().get('ready', r.json())}")

# Configure Confluence (PUT is idempotent)
confluence_id = svc_map["confluence"]
r = requests.put(
    f"{BASE}/api/projects/{PROJECT_ID}/settings/{confluence_id}",
    headers=headers(mlops_token),
    json={
        "config": {
            "url": "https://wegabuildiq.atlassian.net",
            "spaceKey": "WEGAAIDEMO",
            "spaceId": "36569092",
            "email": "manibharathy.sekar@wipro.com",
        },
        "secrets": {"patToken": PAT_TOKEN},
        "is_enabled": True,
    },
)
print(f"  Confluence: {r.status_code} -> {r.json().get('ready', r.json())}")

# Harness PAT (shared across harness-repo and harness-pipelines)
HARNESS_PAT = "pat.2KolbecvR0aAcgQ5uXBObA.69dd398281fc4556d2cf41ab.A5FEqOhSFUm0wE71g342"

# Configure Harness Repo
if "harness-repo" in svc_map:
    harness_repo_id = svc_map["harness-repo"]
    r = requests.put(
        f"{BASE}/api/projects/{PROJECT_ID}/settings/{harness_repo_id}",
        headers=headers(mlops_token),
        json={
            "config": {
                "url": "https://app.harness.io",
                "accountId": "2KolbecvR0aAcgQ5uXBObA",
                "orgIdentifier": "WiproPOC",
                "repoIdentifier": "Git_practice_sg",
            },
            "secrets": {"patToken": HARNESS_PAT},
            "is_enabled": True,
        },
    )
    print(f"  Harness Repo: {r.status_code} -> {r.json().get('ready', r.json())}")

# Configure Harness Pipelines
if "harness-pipelines" in svc_map:
    harness_pipe_id = svc_map["harness-pipelines"]
    r = requests.put(
        f"{BASE}/api/projects/{PROJECT_ID}/settings/{harness_pipe_id}",
        headers=headers(mlops_token),
        json={
            "config": {
                "url": "https://app.harness.io",
                "accountId": "2KolbecvR0aAcgQ5uXBObA",
                "orgIdentifier": "WiproPOC",
                "projectIdentifier": "Harness_POC",
            },
            "secrets": {"patToken": HARNESS_PAT},
            "is_enabled": True,
        },
    )
    print(f"  Harness Pipelines: {r.status_code} -> {r.json().get('ready', r.json())}")

# Configure QTest (URL + project ID known, no real token)
if "qtest" in svc_map:
    qtest_id = svc_map["qtest"]
    r = requests.put(
        f"{BASE}/api/projects/{PROJECT_ID}/settings/{qtest_id}",
        headers=headers(mlops_token),
        json={
            "config": {
                "url": "https://wipro123.qtestnet.com/api/v3",
                "qtestProjectId": "123959",
            },
            "secrets": {"patToken": "placeholder-obtain-from-qtest-admin"},
            "is_enabled": False,
        },
    )
    print(f"  QTest: {r.status_code} -> {r.json().get('ready', r.json())}")

# Configure remaining tools with placeholder configs (disabled)
PLACEHOLDER_TOOLS = {
    "sonarqube": {"config": {"url": "https://sonarqube.wega-infra.com"}, "secrets": {"patToken": ""}},
    "snyk": {"config": {"orgId": "wega-org"}, "secrets": {"patToken": ""}},
    "trivy": {"config": {"serverUrl": "https://trivy.wega-infra.com"}, "secrets": {}},
    "github": {"config": {"url": "https://github.com/wega-platform"}, "secrets": {"patToken": ""}},
    "sharepoint": {"config": {"url": "https://wega.sharepoint.com"}, "secrets": {"patToken": ""}},
}
for tool_id, tool_cfg in PLACEHOLDER_TOOLS.items():
    if tool_id in svc_map:
        r = requests.put(
            f"{BASE}/api/projects/{PROJECT_ID}/settings/{svc_map[tool_id]}",
            headers=headers(mlops_token),
            json={**tool_cfg, "is_enabled": False},
        )
        status = r.json().get("ready", r.json()) if r.status_code == 200 else r.text[:80]
        print(f"  {tool_id:20s}: {r.status_code} -> {status}")


# ── Step 7: Activate Developer too ──────────────────────────────
print("\n" + "=" * 60)
print("STEP 7: Activate Developer account")
print("=" * 60)

if dev_activation_url:
    activate(dev_activation_url, "DevPassword1!@#")
else:
    print("  ⊘ Skipping activation (user already exists)")


# ── Step 8: Verify settings from MLOps perspective ──────────────
print("\n" + "=" * 60)
print("STEP 8: Verify project tool settings")
print("=" * 60)

r = requests.get(f"{BASE}/api/projects/{PROJECT_ID}/settings", headers=headers(mlops_token))
print(f"  Settings response: {r.status_code}")
data = r.json()
if isinstance(data, dict) and "tools" in data:
    tools = data["tools"]
    if isinstance(tools, dict):
        for name, info in tools.items():
            print(f"    {name:20s}  ready={info.get('ready')}  enabled={info.get('projectEnabled')}")
    elif isinstance(tools, list):
        for t in tools:
            tid = t.get("toolId", t.get("id", "?"))
            print(f"    {tid:20s}  enabled={t.get('isEnabled')}")
else:
    print(f"  Raw: {json.dumps(data, indent=2)[:500]}")


# ── Summary ─────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SETUP COMPLETE")
print("=" * 60)
print(f"""
  Auth Service: {BASE}
  Project:      WEGA Platform ({PROJECT_ID})

  Users:
    SuperAdmin  aniket.ashtikar@wipro.com  WegaAdmin1!@#
    PM          ravi.kumar@wipro.com       PMPassword1!@#
    MLOps       arun.patel@wipro.com       MLOpsPass1!@#$
    Developer   priya.sharma@wipro.com     DevPassword1!@#

  Tools configured: Jira, Confluence, Harness Repo, Harness Pipelines (by MLOps)
  Tools registered (disabled): QTest, SonarQube, Snyk, Trivy, GitHub, SharePoint

  To verify sidebar:
    1. Open http://localhost:3000
    2. Log in as Developer (priya.sharma@wipro.com / DevPassword1!@#)
    3. Sidebar should show Jira + Confluence panels
""")

