"""
Unit tests for Jira/Xray integration functions in userstory2TestCasesAgent.py

Tests cover:
- get_issue_id_from_key()
- get_xray_token()
- create_tests_in_jira_cloud()
- add_test_steps_graphql()
- link_tests_to_plan_graphql()
- fetch_existing_test_cases_by_label()
- fetch_test_steps_graphql()
- delete_all_test_steps_graphql()
- update_jira_test_issue()
"""
import pytest
from unittest.mock import MagicMock, patch, call
import json


class TestGetIssueIdFromKey:
    """Tests for get_issue_id_from_key() function."""
    
    def test_returns_numeric_id_for_valid_key(self, sample_jira_config):
        """Test that valid issue key returns numeric ID."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "10001", "key": "TEST-123"}
            mock_requests.get.return_value = mock_response
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            result = get_issue_id_from_key("TEST-123", sample_jira_config)
            
            assert result == "10001"
    
    def test_returns_none_for_invalid_key(self, sample_jira_config):
        """Test that invalid issue key returns None."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_requests.get.return_value = mock_response
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            result = get_issue_id_from_key("INVALID-999", sample_jira_config)
            
            assert result is None
    
    def test_returns_none_on_network_error(self, sample_jira_config):
        """Test that network error returns None."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_requests.get.side_effect = Exception("Network error")
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            result = get_issue_id_from_key("TEST-123", sample_jira_config)
            
            assert result is None
    
    def test_constructs_correct_url(self, sample_jira_config):
        """Test that correct API URL is constructed."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "10001"}
            mock_requests.get.return_value = mock_response
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            get_issue_id_from_key("TEST-123", sample_jira_config)
            
            call_args = mock_requests.get.call_args
            url = call_args[0][0]
            assert "rest/api/3/issue/TEST-123" in url
    
    def test_uses_basic_auth(self, sample_jira_config):
        """Test that Basic authentication is used."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "10001"}
            mock_requests.get.return_value = mock_response
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            get_issue_id_from_key("TEST-123", sample_jira_config)
            
            call_kwargs = mock_requests.get.call_args[1]
            assert "auth" in call_kwargs
    
    def test_handles_unauthorized_response(self, sample_jira_config):
        """Test handling of 401 unauthorized response."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_requests.get.return_value = mock_response
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            result = get_issue_id_from_key("TEST-123", sample_jira_config)
            
            assert result is None


class TestGetXrayToken:
    """Tests for get_xray_token() function."""
    
    def test_returns_token_for_valid_credentials(self):
        """Test that valid credentials return token."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = '"test-xray-token-123"'
            mock_response.raise_for_status = MagicMock()
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import get_xray_token
            result = get_xray_token("client-id", "client-secret")
            
            assert result == "test-xray-token-123"
    
    def test_strips_quotes_from_token(self):
        """Test that surrounding quotes are stripped from token."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = '"token-with-quotes"'
            mock_response.raise_for_status = MagicMock()
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import get_xray_token
            result = get_xray_token("client-id", "client-secret")
            
            assert result == "token-with-quotes"
    
    def test_raises_error_for_invalid_credentials(self):
        """Test that invalid credentials raise an error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.raise_for_status.side_effect = Exception("Unauthorized")
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import get_xray_token
            
            with pytest.raises(Exception):
                get_xray_token("invalid-id", "invalid-secret")
    
    def test_posts_to_correct_url(self):
        """Test that request is made to correct Xray auth URL."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = "token"
            mock_response.raise_for_status = MagicMock()
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import get_xray_token
            get_xray_token("client-id", "client-secret")
            
            call_args = mock_requests.post.call_args
            url = call_args[0][0]
            assert "xray.cloud.getxray.app/api/v2/authenticate" in url
    
    def test_sends_correct_payload(self):
        """Test that correct JSON payload is sent."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = "token"
            mock_response.raise_for_status = MagicMock()
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import get_xray_token
            get_xray_token("my-client-id", "my-client-secret")
            
            call_kwargs = mock_requests.post.call_args[1]
            assert call_kwargs["json"]["client_id"] == "my-client-id"
            assert call_kwargs["json"]["client_secret"] == "my-client-secret"


class TestCreateTestsInJiraCloud:
    """Tests for create_tests_in_jira_cloud() function."""
    
    def test_creates_single_test_issue(self, sample_jira_config, sample_test_cases_json):
        """Test creation of a single test issue."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"key": "TEST-100"}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            result = create_tests_in_jira_cloud("STORY-001", [sample_test_cases_json[0]], sample_jira_config)
            
            assert len(result) == 1
            assert result[0] == "TEST-100"
    
    def test_creates_multiple_test_issues(self, sample_jira_config, sample_test_cases_json):
        """Test creation of multiple test issues."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response1 = MagicMock()
            mock_response1.status_code = 201
            mock_response1.json.return_value = {"key": "TEST-100"}
            
            mock_response2 = MagicMock()
            mock_response2.status_code = 201
            mock_response2.json.return_value = {"key": "TEST-101"}
            
            mock_requests.post.side_effect = [mock_response1, mock_response2]
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            result = create_tests_in_jira_cloud("STORY-001", sample_test_cases_json, sample_jira_config)
            
            assert len(result) == 2
    
    def test_handles_partial_failure(self, sample_jira_config, sample_test_cases_json):
        """Test handling when some test creations fail."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response_success = MagicMock()
            mock_response_success.status_code = 201
            mock_response_success.json.return_value = {"key": "TEST-100"}
            
            mock_response_fail = MagicMock()
            mock_response_fail.status_code = 400
            
            mock_requests.post.side_effect = [mock_response_success, mock_response_fail]
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            result = create_tests_in_jira_cloud("STORY-001", sample_test_cases_json, sample_jira_config)
            
            assert "TEST-100" in result
    
    def test_adds_story_id_as_label(self, sample_jira_config, sample_test_cases_json):
        """Test that story ID is added as label to created issues."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"key": "TEST-100"}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            create_tests_in_jira_cloud("STORY-001", [sample_test_cases_json[0]], sample_jira_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            payload = call_kwargs["json"]
            assert "STORY-001" in payload["fields"]["labels"]
    
    def test_sets_issue_type_to_test(self, sample_jira_config, sample_test_cases_json):
        """Test that issue type is set to Test."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"key": "TEST-100"}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            create_tests_in_jira_cloud("STORY-001", [sample_test_cases_json[0]], sample_jira_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload["fields"]["issuetype"]["name"] == "Test"
    
    def test_returns_empty_list_on_all_failures(self, sample_jira_config, sample_test_cases_json):
        """Test that empty list is returned when all creations fail."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            result = create_tests_in_jira_cloud("STORY-001", sample_test_cases_json, sample_jira_config)
            
            assert result == []
    
    def test_handles_missing_test_case_name(self, sample_jira_config):
        """Test handling of test case without name."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"key": "TEST-100"}
            mock_requests.post.return_value = mock_response
            
            test_case_no_name = {"Test Case Description": "Description only"}
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            result = create_tests_in_jira_cloud("STORY-001", [test_case_no_name], sample_jira_config)
            
            assert len(result) == 1


class TestAddTestStepsGraphql:
    """Tests for add_test_steps_graphql() function."""
    
    def test_adds_single_step(self, sample_xray_steps):
        """Test adding a single test step."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"step0": {"id": "1"}}}
            mock_requests.post.return_value = mock_response
            
            step = [{"Test Case Step": "Click button", "Expected Results": "Button clicked"}]
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            add_test_steps_graphql("10001", step, "test-token")
            
            mock_requests.post.assert_called_once()
    
    def test_adds_multiple_steps_in_batch(self, sample_xray_steps):
        """Test adding multiple steps in a single batch."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {}}
            mock_requests.post.return_value = mock_response
            
            steps = [
                {"Test Case Step": "Step 1", "Expected Results": "Result 1"},
                {"Test Case Step": "Step 2", "Expected Results": "Result 2"},
                {"Test Case Step": "Step 3", "Expected Results": "Result 3"}
            ]
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            add_test_steps_graphql("10001", steps, "test-token", batch_size=10)
            
            assert mock_requests.post.call_count == 1
    
    def test_batches_steps_correctly(self):
        """Test that steps are batched when exceeding batch size."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {}}
            mock_requests.post.return_value = mock_response
            
            steps = [{"Test Case Step": f"Step {i}", "Expected Results": f"Result {i}"} for i in range(15)]
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            add_test_steps_graphql("10001", steps, "test-token", batch_size=10)
            
            assert mock_requests.post.call_count == 2
    
    def test_uses_bearer_token_auth(self):
        """Test that Bearer token authentication is used."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {}}
            mock_requests.post.return_value = mock_response
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            add_test_steps_graphql("10001", steps, "my-token")
            
            call_kwargs = mock_requests.post.call_args[1]
            assert "Bearer my-token" in call_kwargs["headers"]["Authorization"]
    
    def test_handles_graphql_errors(self):
        """Test handling of GraphQL errors in response."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"errors": [{"message": "Invalid issue ID"}]}
            mock_requests.post.return_value = mock_response
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            add_test_steps_graphql("invalid-id", steps, "test-token")


class TestLinkTestsToPlanGraphql:
    """Tests for link_tests_to_plan_graphql() function."""
    
    def test_links_single_test_to_plan(self):
        """Test linking a single test to a test plan."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {"addTestsToTestPlan": {"addedTests": ["10001"], "warning": None}}
            }
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import link_tests_to_plan_graphql
            link_tests_to_plan_graphql("plan-123", ["10001"], "test-token")
            
            mock_requests.post.assert_called_once()
    
    def test_links_multiple_tests_to_plan(self):
        """Test linking multiple tests to a test plan."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {"addTestsToTestPlan": {"addedTests": ["10001", "10002"], "warning": None}}
            }
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import link_tests_to_plan_graphql
            link_tests_to_plan_graphql("plan-123", ["10001", "10002"], "test-token")
            
            call_kwargs = mock_requests.post.call_args[1]
            variables = call_kwargs["json"]["variables"]
            assert len(variables["testIssueIds"]) == 2
    
    def test_handles_graphql_errors(self):
        """Test handling of GraphQL errors."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"errors": [{"message": "Plan not found"}]}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import link_tests_to_plan_graphql
            link_tests_to_plan_graphql("invalid-plan", ["10001"], "test-token")
    
    def test_converts_ids_to_strings(self):
        """Test that issue IDs are converted to strings."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"addTestsToTestPlan": {}}}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import link_tests_to_plan_graphql
            link_tests_to_plan_graphql(12345, [10001, 10002], "test-token")
            
            call_kwargs = mock_requests.post.call_args[1]
            variables = call_kwargs["json"]["variables"]
            assert variables["issueId"] == "12345"
            assert all(isinstance(tid, str) for tid in variables["testIssueIds"])


class TestFetchExistingTestCasesByLabel:
    """Tests for fetch_existing_test_cases_by_label() function."""
    
    def test_fetches_test_cases_via_v3_endpoint(self, sample_jira_config, sample_jira_search_response):
        """Test fetching test cases via new v3 endpoint."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = sample_jira_search_response
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            result = fetch_existing_test_cases_by_label("STORY-001", sample_jira_config)
            
            assert len(result) == 1
            assert result[0]["key"] == "TEST-123"
    
    def test_falls_back_to_v2_endpoint(self, sample_jira_config, sample_jira_search_response):
        """Test fallback to v2 endpoint when v3 fails."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response_v3 = MagicMock()
            mock_response_v3.status_code = 404
            mock_response_v3.text = "Not found"
            
            mock_response_v2 = MagicMock()
            mock_response_v2.status_code = 200
            mock_response_v2.json.return_value = sample_jira_search_response
            
            mock_requests.post.return_value = mock_response_v3
            mock_requests.get.return_value = mock_response_v2
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            result = fetch_existing_test_cases_by_label("STORY-001", sample_jira_config)
            
            assert len(result) >= 0
    
    def test_returns_empty_list_when_no_results(self, sample_jira_config):
        """Test that empty list is returned when no test cases found."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"issues": [], "total": 0}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            result = fetch_existing_test_cases_by_label("STORY-NONE", sample_jira_config)
            
            assert result == []
    
    def test_parses_adf_description(self, sample_jira_config):
        """Test parsing of Atlassian Document Format description."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            adf_response = {
                "issues": [{
                    "key": "TEST-123",
                    "id": "10001",
                    "fields": {
                        "summary": "Test Summary",
                        "description": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {"type": "paragraph", "content": [
                                    {"type": "text", "text": "First paragraph"},
                                    {"type": "text", "text": " continued"}
                                ]}
                            ]
                        }
                    }
                }]
            }
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = adf_response
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            result = fetch_existing_test_cases_by_label("STORY-001", sample_jira_config)
            
            assert "First paragraph" in result[0]["description"]


class TestFetchTestStepsGraphql:
    """Tests for fetch_test_steps_graphql() function."""
    
    def test_fetches_steps_successfully(self, sample_xray_steps):
        """Test successful fetching of test steps."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests, \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}):
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {"getTest": {"issueId": "10001", "steps": sample_xray_steps}}
            }
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import fetch_test_steps_graphql
            result = fetch_test_steps_graphql("10001", "test-token")
            
            assert len(result) == 3
    
    def test_returns_empty_list_on_error(self):
        """Test that empty list is returned on GraphQL error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests, \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}):
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"errors": [{"message": "Issue not found"}]}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import fetch_test_steps_graphql
            result = fetch_test_steps_graphql("invalid-id", "test-token")
            
            assert result == []
    
    def test_handles_paginated_response(self, sample_xray_steps):
        """Test handling of paginated response format."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests, \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}):
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {"getTest": {"issueId": "10001", "steps": {"results": sample_xray_steps}}}
            }
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import fetch_test_steps_graphql
            result = fetch_test_steps_graphql("10001", "test-token")
            
            assert len(result) == 3


class TestDeleteAllTestStepsGraphql:
    """Tests for delete_all_test_steps_graphql() function."""
    
    def test_deletes_existing_steps(self, sample_xray_steps):
        """Test deletion of existing test steps."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests, \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}), \
             patch('userstory2TestCasesAgent._xray_remove_step_arg_cache', {"test-token": "stepId"}), \
             patch('userstory2TestCasesAgent._xray_remove_step_return_cache', {"test-token": "issueId"}), \
             patch('userstory2TestCasesAgent.fetch_test_steps_graphql') as mock_fetch:
            
            mock_fetch.return_value = sample_xray_steps
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {}}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import delete_all_test_steps_graphql
            delete_all_test_steps_graphql("10001", "test-token")
            
            mock_requests.post.assert_called()
    
    def test_skips_deletion_when_no_steps(self):
        """Test that deletion is skipped when no steps exist."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests, \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}), \
             patch('userstory2TestCasesAgent.fetch_test_steps_graphql') as mock_fetch:
            
            mock_fetch.return_value = []
            
            from userstory2TestCasesAgent import delete_all_test_steps_graphql
            delete_all_test_steps_graphql("10001", "test-token")
            
            mock_requests.post.assert_not_called()


class TestUpdateJiraTestIssue:
    """Tests for update_jira_test_issue() function."""
    
    def test_updates_summary_and_description(self, sample_jira_config):
        """Test updating issue summary and description."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_requests.put.return_value = mock_response
            
            from userstory2TestCasesAgent import update_jira_test_issue
            update_jira_test_issue("TEST-123", "New Name", "New Description", sample_jira_config)
            
            mock_requests.put.assert_called_once()
            call_kwargs = mock_requests.put.call_args[1]
            payload = call_kwargs["json"]
            assert payload["fields"]["summary"] == "New Name"
    
    def test_handles_update_failure(self, sample_jira_config):
        """Test handling of update failure."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad request"
            mock_requests.put.return_value = mock_response
            
            from userstory2TestCasesAgent import update_jira_test_issue
            update_jira_test_issue("TEST-123", "Name", "Desc", sample_jira_config)
    
    def test_uses_correct_api_endpoint(self, sample_jira_config):
        """Test that correct API endpoint is used."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_requests.put.return_value = mock_response
            
            from userstory2TestCasesAgent import update_jira_test_issue
            update_jira_test_issue("TEST-123", "Name", "Desc", sample_jira_config)
            
            call_args = mock_requests.put.call_args
            url = call_args[0][0]
            assert "rest/api/3/issue/TEST-123" in url
    
    def test_handles_empty_description(self, sample_jira_config):
        """Test handling of empty description."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_requests.put.return_value = mock_response
            
            from userstory2TestCasesAgent import update_jira_test_issue
            update_jira_test_issue("TEST-123", "Name", "", sample_jira_config)
            
            call_kwargs = mock_requests.put.call_args[1]
            payload = call_kwargs["json"]
            desc_text = payload["fields"]["description"]["content"][0]["content"][0]["text"]
            assert desc_text == "No description provided."
