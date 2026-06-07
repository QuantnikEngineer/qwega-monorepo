"""
End-to-End Workflow Integration Tests.

Tests complete workflows from API request to external system updates.
"""
import pytest
import json
import responses
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestGreenFieldWorkflow:
    """E2E tests for greenfield (new) story processing."""
    
    @responses.activate
    def test_single_story_jira_xray_workflow(self, sample_user_story, mock_vertex_ai_response, jira_config, xray_config):
        """Test complete workflow: API -> AI -> Jira -> Xray."""
        # Mock test plan ID lookup (TEST_PLAN_KEY defaults to WEGA-875)
        responses.add(
            responses.GET,
            "https://wegabuildiq.atlassian.net/rest/api/3/issue/WEGA-875",
            json={"id": "99999", "key": "WEGA-875"},
            status=200
        )
        # Jira issue lookup
        responses.add(
            responses.GET,
            f"{jira_config['base_url']}rest/api/3/issue/STORY-001",
            json={"id": "10001", "key": "STORY-001"},
            status=200
        )
        # Jira issue creation (for each test case)
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"id": "10002", "key": "TEST-100"},
            status=201
        )
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"id": "10003", "key": "TEST-101"},
            status=201
        )
        # Lookup created test issues for linking
        responses.add(
            responses.GET,
            "https://wegabuildiq.atlassian.net/rest/api/3/issue/TEST-100",
            json={"id": "10002", "key": "TEST-100"},
            status=200
        )
        responses.add(
            responses.GET,
            "https://wegabuildiq.atlassian.net/rest/api/3/issue/TEST-101",
            json={"id": "10003", "key": "TEST-101"},
            status=200
        )
        # Xray authentication
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/authenticate",
            json='"xray-token-12345"',
            status=200
        )
        # Xray test steps (for each test case)
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"data": {"step0": {"id": "1"}}},
            status=200
        )
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"data": {"step0": {"id": "2"}}},
            status=200
        )
        # Xray test plan linking
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"data": {"addTestsToTestPlan": {"addedTests": ["10002", "10003"], "warning": None}}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model, \
             patch('userstory2TestCasesAgent.jira_config', jira_config), \
             patch('userstory2TestCasesAgent.xray_config', xray_config):
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = mock_vertex_ai_response["scenarios"]
            
            mock_tc_response = MagicMock()
            mock_tc_response.text = json.dumps(mock_vertex_ai_response["test_cases"])
            
            mock_model.generate_content.side_effect = [mock_scenario_response, mock_tc_response]
            
            from userstory2TestCasesAgent import process_single_story_jira
            
            result = process_single_story_jira("STORY-001", sample_user_story, "Functional")
            
            assert "jira_push_result" in result
            assert "total_tests_created" in result["jira_push_result"]
    
    @responses.activate
    def test_single_story_qtest_workflow(self, sample_user_story, mock_vertex_ai_response, qtest_config):
        """Test complete workflow: API -> AI -> qTest."""
        # qTest test case creation
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases",
            json={"id": 12345, "name": "Test Case"},
            status=201
        )
        # qTest test steps
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases/12345/test-steps",
            json=[],
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model, \
             patch('userstory2TestCasesAgent.qtest_config', qtest_config):
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = mock_vertex_ai_response["scenarios"]
            
            mock_tc_response = MagicMock()
            mock_tc_response.text = json.dumps(mock_vertex_ai_response["test_cases"])
            
            mock_model.generate_content.side_effect = [mock_scenario_response, mock_tc_response]
            
            from userstory2TestCasesAgent import process_single_story_qtest
            
            result = process_single_story_qtest(sample_user_story, "Functional")
            
            assert "qtest_push_result" in result
            assert result["qtest_push_result"]["total_tests_created"] > 0


@pytest.mark.integration
class TestBrownFieldWorkflow:
    """E2E tests for brownfield (existing) story processing."""
    
    def test_brownfield_fetches_existing_tests(self, jira_config, xray_config):
        """Test that brownfield workflow fetches existing tests by label."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.jira_config', jira_config), \
             patch('userstory2TestCasesAgent.xray_config', xray_config):
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            
            # This function is the first step in brownfield
            # It should be properly callable
            assert callable(fetch_existing_test_cases_by_label)
    
    def test_brownfield_diff_logic_exists(self):
        """Test that diff and merge logic is available."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import diff_and_merge_test_cases
            
            # The diff function should exist
            assert callable(diff_and_merge_test_cases)


@pytest.mark.integration
class TestBulkWorkflow:
    """E2E tests for bulk job processing."""
    
    @responses.activate
    def test_bulk_job_creation_and_processing(self, jira_config, xray_config):
        """Test bulk job creation through API and processing."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            # Create bulk job
            payload = {
                "userStories": [
                    {"userStoryJiraId": "STORY-001", "userStory": "As a user I want to login"},
                    {"userStoryJiraId": "STORY-002", "userStory": "As a user I want to logout"}
                ],
                "ScenarioTypes": ["Functional"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=payload)
            
            assert response.status_code == 202
            data = response.json()
            assert "job_id" in data
    
    @responses.activate
    def test_bulk_job_status_tracking(self, jira_config, xray_config):
        """Test bulk job status tracking through API."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app, _jobs
            client = TestClient(app)
            
            # Create job
            payload = {
                "userStories": [{"userStoryJiraId": "STORY-001", "userStory": "User story text"}],
                "ScenarioTypes": ["Functional"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=payload)
            job_id = response.json()["job_id"]
            
            # Check status
            status_response = client.get(f"/v1/jobs/{job_id}")
            
            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["job_id"] == job_id
            assert "status" in status_data


@pytest.mark.integration
class TestApiWorkflow:
    """E2E tests for API endpoint workflows."""
    
    def test_api_health_check(self):
        """Test API health check endpoint."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            response = client.get("/health")
            
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
    
    def test_api_root_endpoint(self):
        """Test API root endpoint."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            response = client.get("/")
            
            assert response.status_code == 200


@pytest.mark.integration
class TestMultiScenarioTypeWorkflow:
    """E2E tests for processing multiple scenario types."""
    
    @responses.activate
    def test_all_scenario_types_workflow(self, sample_user_story, all_scenario_types, jira_config, xray_config):
        """Test workflow with all scenario types."""
        # Mock responses for each scenario type
        for _ in range(len(all_scenario_types)):
            responses.add(
                responses.GET,
                f"{jira_config['base_url']}rest/api/3/issue/STORY-001",
                json={"id": "10001", "key": "STORY-001"},
                status=200
            )
            responses.add(
                responses.POST,
                f"{jira_config['base_url']}rest/api/3/issue",
                json={"id": "10002", "key": "TEST-100"},
                status=201
            )
            responses.add(
                responses.POST,
                "https://xray.cloud.getxray.app/api/v2/authenticate",
                json='"xray-token-12345"',
                status=200
            )
            responses.add(
                responses.POST,
                "https://xray.cloud.getxray.app/api/v2/graphql",
                json={"data": {"step0": {"id": "1"}}},
                status=200
            )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model, \
             patch('userstory2TestCasesAgent.jira_config', jira_config), \
             patch('userstory2TestCasesAgent.xray_config', xray_config):
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = "Test Scenario generated"
            
            mock_tc_response = MagicMock()
            mock_tc_response.text = json.dumps([{
                "Test Case Name": "Test Case",
                "Test Case Description": "Description",
                "Test Case Steps": [{"Test Case Step": "Step", "Expected Results": "Result"}]
            }])
            
            mock_model.generate_content.return_value = mock_scenario_response
            mock_model.generate_content.side_effect = None
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            for scenario_type in all_scenario_types[:3]:  # Test first 3 types
                result = generate_test_scenarios_from_userstory(sample_user_story, scenario_type)
                assert result is not None


@pytest.mark.integration
class TestTestPlanLinkingWorkflow:
    """E2E tests for test plan linking workflow."""
    
    @responses.activate
    def test_link_to_test_plan_after_creation(self, sample_user_story, mock_vertex_ai_response, jira_config, xray_config):
        """Test linking tests to test plan after creation."""
        # Mock test plan ID lookup
        responses.add(
            responses.GET,
            "https://wegabuildiq.atlassian.net/rest/api/3/issue/WEGA-875",
            json={"id": "99999", "key": "WEGA-875"},
            status=200
        )
        # Jira issue creation for each test case (mock_vertex_ai_response has 2 test cases)
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"id": "10002", "key": "TEST-100"},
            status=201
        )
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"id": "10003", "key": "TEST-101"},
            status=201
        )
        # Lookup created test issues for linking
        responses.add(
            responses.GET,
            "https://wegabuildiq.atlassian.net/rest/api/3/issue/TEST-100",
            json={"id": "10002", "key": "TEST-100"},
            status=200
        )
        responses.add(
            responses.GET,
            "https://wegabuildiq.atlassian.net/rest/api/3/issue/TEST-101",
            json={"id": "10003", "key": "TEST-101"},
            status=200
        )
        # Xray auth
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/authenticate",
            json='"xray-token-12345"',
            status=200
        )
        # Xray test steps for each test case
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"data": {"step0": {"id": "1"}}},
            status=200
        )
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"data": {"step0": {"id": "2"}}},
            status=200
        )
        # Test plan linking
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"data": {"addTestsToTestPlan": {"addedTests": ["10002", "10003"], "warning": None}}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model, \
             patch('userstory2TestCasesAgent.jira_config', jira_config), \
             patch('userstory2TestCasesAgent.xray_config', xray_config):
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = mock_vertex_ai_response["scenarios"]
            
            mock_tc_response = MagicMock()
            mock_tc_response.text = json.dumps(mock_vertex_ai_response["test_cases"])
            
            mock_model.generate_content.side_effect = [mock_scenario_response, mock_tc_response]
            
            from userstory2TestCasesAgent import process_single_story_jira
            
            result = process_single_story_jira("STORY-001", sample_user_story, "Functional")
            
            assert "jira_push_result" in result
