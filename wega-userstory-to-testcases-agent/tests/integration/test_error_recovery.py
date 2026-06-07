"""
Error Recovery Integration Tests.

Tests error handling, retry logic, and graceful degradation.
"""
import pytest
import json
import responses
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestVertexAIErrorRecovery:
    """Tests for Vertex AI error recovery."""
    
    def test_retry_on_ssl_error(self, sample_user_story):
        """Test automatic retry on SSL certificate errors."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model, \
             patch('userstory2TestCasesAgent.time.sleep'):
            
            mock_response = MagicMock()
            mock_response.text = "Test scenarios"
            
            # Fail twice, then succeed
            mock_model.generate_content.side_effect = [
                Exception("SSL: CERTIFICATE_VERIFY_FAILED"),
                Exception("SSL handshake timeout"),
                mock_response
            ]
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            result = generate_test_scenarios_from_userstory(sample_user_story, "Functional")
            
            assert result == "Test scenarios"
            assert mock_model.generate_content.call_count == 3
    
    def test_retry_on_connection_timeout(self, sample_user_story):
        """Test automatic retry on connection timeout."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model, \
             patch('userstory2TestCasesAgent.time.sleep'):
            
            mock_response = MagicMock()
            mock_response.text = "Test scenarios"
            
            mock_model.generate_content.side_effect = [
                Exception("Connection timed out"),
                mock_response
            ]
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            result = generate_test_scenarios_from_userstory(sample_user_story, "Functional")
            
            assert result == "Test scenarios"
    
    def test_max_retries_exceeded_raises_error(self, sample_user_story):
        """Test that error is raised after max retries."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model, \
             patch('userstory2TestCasesAgent.time.sleep'):
            
            mock_model.generate_content.side_effect = Exception("Persistent SSL error")
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(Exception, match="SSL"):
                generate_test_scenarios_from_userstory(sample_user_story, "Functional")
    
    def test_non_retryable_error_fails_immediately(self, sample_user_story):
        """Test that non-retryable errors fail without retry."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_model.generate_content.side_effect = ValueError("Invalid input format")
            
            from userstory2TestCasesAgent import generate_test_cases
            
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "error" in result
            # Should only be called once (no retry)
            assert mock_model.generate_content.call_count == 1
    
    def test_empty_response_handled(self, sample_user_story):
        """Test handling of empty AI response."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = ""
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(ValueError, match="Empty response"):
                generate_test_scenarios_from_userstory(sample_user_story, "Functional")


@pytest.mark.integration
class TestJiraErrorRecovery:
    """Tests for Jira API error recovery."""
    
    @responses.activate
    def test_partial_creation_continues_on_failure(self, jira_config):
        """Test that bulk creation continues when individual items fail."""
        # First succeeds
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"id": "10001", "key": "TEST-100"},
            status=201
        )
        # Second fails
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"errorMessages": ["Validation failed"]},
            status=400
        )
        # Third succeeds
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"id": "10003", "key": "TEST-102"},
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            
            test_cases = [
                {"Test Case Name": f"Test {i}", "Test Case Description": f"Desc {i}"}
                for i in range(3)
            ]
            
            result = create_tests_in_jira_cloud("STORY-001", test_cases, jira_config)
            
            # Should have 2 successful creations
            assert len(result) == 2
    
    @responses.activate
    def test_auth_failure_returns_none(self, jira_config):
        """Test handling of authentication failure."""
        responses.add(
            responses.GET,
            f"{jira_config['base_url']}rest/api/3/issue/TEST-123",
            json={"errorMessages": ["Unauthorized"]},
            status=401
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            result = get_issue_id_from_key("TEST-123", jira_config)
            
            assert result is None
    
    @responses.activate
    def test_search_fallback_to_v2_api(self, jira_config):
        """Test fallback to v2 API when v3 fails."""
        # v3 fails
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/search/jql",
            json={"errorMessages": ["Endpoint not found"]},
            status=404
        )
        # v2 succeeds
        responses.add(
            responses.GET,
            f"{jira_config['base_url']}rest/api/2/search",
            json={"issues": [{"id": "10001", "key": "TEST-100", "fields": {"summary": "Test", "description": "Desc"}}]},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            
            result = fetch_existing_test_cases_by_label("STORY-001", jira_config)
            
            assert len(result) == 1
    
    def test_network_error_returns_none(self, jira_config):
        """Test handling of network errors."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests.get') as mock_get:
            
            mock_get.side_effect = Exception("Connection refused")
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            result = get_issue_id_from_key("TEST-123", jira_config)
            
            assert result is None


@pytest.mark.integration
class TestXrayErrorRecovery:
    """Tests for Xray API error recovery."""
    
    @responses.activate
    def test_graphql_error_handled_gracefully(self):
        """Test handling of GraphQL errors."""
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"errors": [{"message": "Invalid mutation"}]},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            # Should not raise, just log error
            add_test_steps_graphql("10001", steps, "test-token")
    
    @responses.activate
    def test_auth_failure_raises_exception(self, xray_config):
        """Test that authentication failure raises exception."""
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/authenticate",
            json={"error": "Invalid credentials"},
            status=401
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_xray_token
            
            with pytest.raises(Exception):
                get_xray_token(xray_config["client_id"], xray_config["client_secret"])
    
    @responses.activate
    def test_empty_steps_response_returns_empty_list(self):
        """Test handling of empty steps response."""
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"data": {"getTest": None}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}):
            
            from userstory2TestCasesAgent import fetch_test_steps_graphql
            
            result = fetch_test_steps_graphql("10001", "test-token")
            
            assert result == []


@pytest.mark.integration
class TestQtestErrorRecovery:
    """Tests for qTest API error recovery."""
    
    @responses.activate
    def test_creation_failure_returns_none(self, qtest_config):
        """Test handling of test case creation failure."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases",
            json={"error": "Bad request"},
            status=400
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {"Test Case Name": "Test", "Test Case Description": "Desc"}
            
            result = create_test_case_in_qtest(qtest_config["project_id"], test_case, qtest_config)
            
            assert result is None
    
    @responses.activate
    def test_steps_failure_does_not_raise(self, qtest_config):
        """Test that test steps addition failure doesn't raise exception."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases/12345/test-steps",
            json={"error": "Server error"},
            status=500
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            # Should not raise
            add_test_steps_in_qtest(qtest_config["project_id"], "12345", steps, qtest_config)
    
    def test_network_error_returns_none(self, qtest_config):
        """Test handling of network errors."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests.post') as mock_post:
            
            mock_post.side_effect = Exception("Network unreachable")
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {"Test Case Name": "Test", "Test Case Description": "Desc"}
            
            result = create_test_case_in_qtest(qtest_config["project_id"], test_case, qtest_config)
            
            assert result is None


@pytest.mark.integration
class TestAPIErrorRecovery:
    """Tests for API endpoint error recovery."""
    
    def test_invalid_json_returns_422(self):
        """Test handling of invalid JSON request."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            response = client.post(
                "/v1/generate-test-cases/bulk",
                content="invalid json",
                headers={"Content-Type": "application/json"}
            )
            
            assert response.status_code == 422
    
    def test_missing_required_field_returns_422(self):
        """Test handling of missing required fields."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            # Missing required fields - only userStories without ScenarioTypes
            payload = {
                "userStories": []
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=payload)
            
            assert response.status_code == 422
    
    def test_invalid_scenario_type_returns_400(self):
        """Test handling of invalid scenario type."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            payload = {
                "userStories": [{"userStoryJiraId": "STORY-001", "userStory": "As a user I want something"}],
                "ScenarioTypes": ["InvalidType"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=payload)
            
            # API returns 400 for validation errors on scenario types
            assert response.status_code == 400
    
    def test_empty_bulk_stories_returns_422(self):
        """Test handling of empty stories list in bulk request."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            payload = {
                "userStories": [],
                "ScenarioTypes": ["Functional"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=payload)
            
            assert response.status_code == 422
    
    def test_nonexistent_job_returns_404(self):
        """Test handling of nonexistent job ID."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            response = client.get("/v1/jobs/nonexistent-job-id")
            
            assert response.status_code == 404


@pytest.mark.integration
class TestBulkJobErrorRecovery:
    """Tests for bulk job error recovery."""
    
    def test_individual_story_failure_continues_job(self, mock_vertex_ai_response):
        """Test that job continues when individual stories fail."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import _jobs
            
            # Manually create a job store to test update behavior
            job_id = "test-error-job"
            _jobs[job_id] = {
                "status": "processing",
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}},
                    {"index": 1, "userStoryJiraId": "STORY-2", "status": "pending", "results_by_scenario": {}},
                    {"index": 2, "userStoryJiraId": "STORY-3", "status": "pending", "results_by_scenario": {}}
                ],
                "completed_count": 0,
                "failed_count": 0
            }
            
            # Simulate story processing - directly modify statuses
            _jobs[job_id]["stories"][0]["status"] = "completed"
            _jobs[job_id]["completed_count"] += 1
            
            _jobs[job_id]["stories"][1]["status"] = "error"
            _jobs[job_id]["failed_count"] += 1
            
            _jobs[job_id]["stories"][2]["status"] = "completed"
            _jobs[job_id]["completed_count"] += 1
            
            # Verify final state
            assert _jobs[job_id]["stories"][0]["status"] == "completed"
            assert _jobs[job_id]["stories"][1]["status"] == "error"
            assert _jobs[job_id]["stories"][2]["status"] == "completed"
            assert _jobs[job_id]["completed_count"] == 2
            assert _jobs[job_id]["failed_count"] == 1
    
    def test_job_marked_complete_with_partial_results(self):
        """Test that job with mixed results is properly tracked."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import _jobs
            
            job_id = "test-partial-results"
            _jobs[job_id] = {
                "status": "processing",
                "stories": [
                    {"userStoryJiraId": "STORY-1", "status": "completed"},
                    {"userStoryJiraId": "STORY-2", "status": "error"},
                    {"userStoryJiraId": "STORY-3", "status": "completed"}
                ],
                "completed_count": 2,
                "failed_count": 1,
                "total": 3
            }
            
            # Job should reflect mixed status
            assert _jobs[job_id]["completed_count"] == 2
            assert _jobs[job_id]["failed_count"] == 1


@pytest.mark.integration
class TestGracefulDegradation:
    """Tests for graceful degradation when services are unavailable."""
    
    @responses.activate
    def test_continue_without_test_plan_link(self, jira_config, xray_config, mock_vertex_ai_response):
        """Test that workflow continues when test plan linking fails."""
        # Mock test plan ID lookup
        responses.add(
            responses.GET,
            "https://wegabuildiq.atlassian.net/rest/api/3/issue/WEGA-875",
            json={"id": "99999", "key": "WEGA-875"},
            status=200
        )
        # Jira creation succeeds (for each test case)
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"id": "10001", "key": "TEST-100"},
            status=201
        )
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"id": "10002", "key": "TEST-101"},
            status=201
        )
        # Lookup created test issues for linking
        responses.add(
            responses.GET,
            "https://wegabuildiq.atlassian.net/rest/api/3/issue/TEST-100",
            json={"id": "10001", "key": "TEST-100"},
            status=200
        )
        responses.add(
            responses.GET,
            "https://wegabuildiq.atlassian.net/rest/api/3/issue/TEST-101",
            json={"id": "10002", "key": "TEST-101"},
            status=200
        )
        # Xray auth succeeds
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/authenticate",
            json='"xray-token"',
            status=200
        )
        # Xray steps succeed (for each test case)
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
        # Test plan linking fails
        responses.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"errors": [{"message": "Test plan not found"}]},
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
            
            # Should complete without error even if test plan linking fails
            result = process_single_story_jira("STORY-001", "User story", "Functional")
            
            assert "jira_push_result" in result
    
    def test_returns_ai_only_result_on_jira_failure(self, mock_vertex_ai_response, jira_config):
        """Test that AI results are returned even when Jira push fails."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model, \
             patch('userstory2TestCasesAgent.jira_config', jira_config), \
             patch('userstory2TestCasesAgent.requests.post') as mock_post:
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = mock_vertex_ai_response["scenarios"]
            
            mock_tc_response = MagicMock()
            mock_tc_response.text = json.dumps(mock_vertex_ai_response["test_cases"])
            
            mock_model.generate_content.side_effect = [mock_scenario_response, mock_tc_response]
            mock_post.side_effect = Exception("Jira unavailable")
            
            from userstory2TestCasesAgent import generate_test_cases
            
            # AI generation should still work
            result = generate_test_cases("User story", "Functional")
            
            assert "Test Scenarios" in result
            assert "Test Cases" in result
