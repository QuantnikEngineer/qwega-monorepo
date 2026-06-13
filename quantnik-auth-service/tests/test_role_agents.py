"""Tests for role-based agent mapping (6-role model).

Validates that each role gets the correct set of allowed agents via
GET /api/roles/agents, and that the QUANTNIK Orchestrator is excluded from
all role-agent mappings (D-12).
"""

import pytest


@pytest.mark.integration
class TestRoleAgentMapping:
    """GET /api/roles/agents — role-based agent access."""

    async def test_superadmin_gets_all_agents(
        self, test_client, superadmin_headers, seed_roles, seed_role_agents,
    ):
        """SuperAdmin gets all 11 user-facing agents."""
        response = await test_client.get(
            "/api/roles/agents",
            headers=superadmin_headers,
        )
        assert response.status_code == 200
        agents = response.json()["agents"]
        assert len(agents) == 11
        assert "brd-generator" in agents
        assert "code-assistant" in agents

    async def test_po_sm_ba_gets_planning_agents(
        self, test_client, po_headers, seed_roles, seed_role_agents,
    ):
        """PO/SM/BA gets 4 planning agents."""
        response = await test_client.get(
            "/api/roles/agents",
            headers=po_headers,
        )
        assert response.status_code == 200
        agents = response.json()["agents"]
        assert len(agents) == 4
        assert set(agents) == {
            "brd-generator", "brd-summary",
            "user-story-generator", "user-manual",
        }

    async def test_developer_gets_3_agents(
        self, test_client, devtest_headers, seed_roles, seed_role_agents,
    ):
        """Developer gets 3 agents (stories validator, user manual, code assistant)."""
        response = await test_client.get(
            "/api/roles/agents",
            headers=devtest_headers,
        )
        assert response.status_code == 200
        agents = response.json()["agents"]
        assert len(agents) == 3
        assert set(agents) == {
            "user-story-validator", "user-manual", "code-assistant",
        }

    async def test_pm_gets_3_agents(
        self, test_client, pm_headers, seed_roles, seed_role_agents,
    ):
        """PM gets 3 planning agents (6-role model)."""
        response = await test_client.get(
            "/api/roles/agents",
            headers=pm_headers,
        )
        assert response.status_code == 200
        agents = response.json()["agents"]
        assert len(agents) == 3
        assert set(agents) == {
            "brd-generator", "brd-summary", "user-story-generator",
        }

    async def test_mlops_gets_7_agents(
        self, test_client, fde_headers, seed_roles, seed_role_agents,
    ):
        """MLOps gets 7 agents (testing + code analysis suite)."""
        response = await test_client.get(
            "/api/roles/agents",
            headers=fde_headers,
        )
        assert response.status_code == 200
        agents = response.json()["agents"]
        assert len(agents) == 7
        assert "test-case" in agents
        assert "code-assistant" in agents

    async def test_orchestrator_excluded(
        self, test_client, superadmin_headers, seed_roles, seed_role_agents,
    ):
        """D-12: QUANTNIK Orchestrator hidden from all users."""
        response = await test_client.get(
            "/api/roles/agents",
            headers=superadmin_headers,
        )
        agents = response.json()["agents"]
        assert "Quantnik-Orchestrator" not in agents
        assert "quantnik-orchestrator" not in agents

    async def test_agents_requires_auth(self, test_client, seed_roles, seed_org):
        """GET /api/roles/agents without token → 401."""
        response = await test_client.get("/api/roles/agents")
        assert response.status_code == 401
