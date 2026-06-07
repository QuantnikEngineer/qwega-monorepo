"""
Integration tests for Xray Cloud GraphQL API interactions.

Tests direct integration with Xray Cloud for test management.
"""
import pytest
import json
import responses
from unittest.mock import patch, MagicMock


XRAY_AUTH_URL = "https://xray.cloud.getxray.app/api/v2/authenticate"
XRAY_GRAPHQL_URL = "https://xray.cloud.getxray.app/api/v2/graphql"


@pytest.mark.integration
class TestXrayAuthentication:
    """Integration tests for Xray authentication."""
    
    @responses.activate
    def test_authenticate_success(self, xray_config, mock_xray_token_response):
        """Test successful Xray authentication."""
        responses.add(
            responses.POST,
            XRAY_AUTH_URL,
            json=mock_xray_token_response,
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_xray_token
            
            token = get_xray_token(xray_config["client_id"], xray_config["client_secret"])
            
            assert token is not None
            assert len(token) > 0
    
    @responses.activate
    def test_authenticate_strips_quotes(self, xray_config):
        """Test that surrounding quotes are stripped from token."""
        responses.add(
            responses.POST,
            XRAY_AUTH_URL,
            json='"token-with-quotes"',
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_xray_token
            
            token = get_xray_token(xray_config["client_id"], xray_config["client_secret"])
            
            assert not token.startswith('"')
            assert not token.endswith('"')
    
    @responses.activate
    def test_authenticate_failure(self, xray_config):
        """Test Xray authentication failure."""
        responses.add(
            responses.POST,
            XRAY_AUTH_URL,
            json={"error": "Invalid credentials"},
            status=401
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_xray_token
            
            with pytest.raises(Exception):
                get_xray_token(xray_config["client_id"], xray_config["client_secret"])
    
    @responses.activate
    def test_authenticate_sends_correct_payload(self, xray_config, mock_xray_token_response):
        """Test that authentication sends correct payload."""
        responses.add(
            responses.POST,
            XRAY_AUTH_URL,
            json=mock_xray_token_response,
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_xray_token
            
            get_xray_token("my-client-id", "my-client-secret")
            
            request_body = json.loads(responses.calls[0].request.body)
            assert request_body["client_id"] == "my-client-id"
            assert request_body["client_secret"] == "my-client-secret"


@pytest.mark.integration
class TestXrayTestStepsAddition:
    """Integration tests for adding test steps via GraphQL."""
    
    @responses.activate
    def test_add_single_step(self):
        """Test adding a single test step."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"data": {"step0": {"id": "step-1", "action": "Click", "result": "Success"}}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            
            steps = [{"Test Case Step": "Click button", "Expected Results": "Button clicked"}]
            
            # Should not raise exception
            add_test_steps_graphql("10001", steps, "test-token")
            
            assert len(responses.calls) == 1
    
    @responses.activate
    def test_add_multiple_steps(self):
        """Test adding multiple test steps."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"data": {"step0": {"id": "1"}, "step1": {"id": "2"}, "step2": {"id": "3"}}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            
            steps = [
                {"Test Case Step": f"Step {i}", "Expected Results": f"Result {i}"}
                for i in range(3)
            ]
            
            add_test_steps_graphql("10001", steps, "test-token", batch_size=10)
            
            # Single batch call
            assert len(responses.calls) == 1
    
    @responses.activate
    def test_steps_batching(self):
        """Test that steps are batched correctly."""
        # Two batches expected
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"data": {}},
            status=200
        )
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"data": {}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            
            steps = [
                {"Test Case Step": f"Step {i}", "Expected Results": f"Result {i}"}
                for i in range(15)
            ]
            
            add_test_steps_graphql("10001", steps, "test-token", batch_size=10)
            
            # Should be 2 batch calls
            assert len(responses.calls) == 2
    
    @responses.activate
    def test_bearer_token_in_header(self):
        """Test that Bearer token is included in Authorization header."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"data": {}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            add_test_steps_graphql("10001", steps, "my-bearer-token")
            
            auth_header = responses.calls[0].request.headers["Authorization"]
            assert auth_header == "Bearer my-bearer-token"
    
    @responses.activate
    def test_graphql_error_handling(self):
        """Test handling of GraphQL errors."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"errors": [{"message": "Invalid issue ID"}]},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_graphql
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            # Should not raise, just log warning
            add_test_steps_graphql("invalid-id", steps, "test-token")


@pytest.mark.integration
class TestXrayTestStepsRetrieval:
    """Integration tests for retrieving test steps via GraphQL."""
    
    @responses.activate
    def test_fetch_test_steps(self, mock_xray_steps_response):
        """Test fetching test steps for an issue."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json=mock_xray_steps_response,
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}):
            
            from userstory2TestCasesAgent import fetch_test_steps_graphql
            
            result = fetch_test_steps_graphql("10001", "test-token")
            
            assert len(result) == 2
            assert result[0]["id"] == "step-1"
    
    @responses.activate
    def test_fetch_steps_empty_result(self):
        """Test fetching steps when none exist."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"data": {"getTest": {"issueId": "10001", "steps": []}}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}):
            
            from userstory2TestCasesAgent import fetch_test_steps_graphql
            
            result = fetch_test_steps_graphql("10001", "test-token")
            
            assert result == []
    
    @responses.activate
    def test_fetch_steps_error(self):
        """Test handling errors when fetching steps."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"errors": [{"message": "Issue not found"}]},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}):
            
            from userstory2TestCasesAgent import fetch_test_steps_graphql
            
            result = fetch_test_steps_graphql("invalid-id", "test-token")
            
            assert result == []
    
    @responses.activate
    def test_fetch_steps_paginated_response(self):
        """Test handling paginated response format."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={
                "data": {
                    "getTest": {
                        "issueId": "10001",
                        "steps": {
                            "results": [
                                {"id": "1", "action": "Step 1", "result": "Result 1"},
                                {"id": "2", "action": "Step 2", "result": "Result 2"}
                            ]
                        }
                    }
                }
            },
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}):
            
            from userstory2TestCasesAgent import fetch_test_steps_graphql
            
            result = fetch_test_steps_graphql("10001", "test-token")
            
            assert len(result) == 2


@pytest.mark.integration
class TestXrayTestStepsDeletion:
    """Integration tests for deleting test steps via GraphQL."""
    
    @responses.activate
    def test_delete_all_steps(self):
        """Test deleting all steps from an issue."""
        # Fetch steps response
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={
                "data": {
                    "getTest": {
                        "issueId": "10001",
                        "steps": [
                            {"id": "step-1", "action": "Step 1", "result": "Result 1"},
                            {"id": "step-2", "action": "Step 2", "result": "Result 2"}
                        ]
                    }
                }
            },
            status=200
        )
        # Delete steps response
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"data": {"del0": {"issueId": "10001"}, "del1": {"issueId": "10001"}}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}), \
             patch('userstory2TestCasesAgent._xray_remove_step_arg_cache', {"test-token": "stepId"}), \
             patch('userstory2TestCasesAgent._xray_remove_step_return_cache', {"test-token": "issueId"}):
            
            from userstory2TestCasesAgent import delete_all_test_steps_graphql
            
            delete_all_test_steps_graphql("10001", "test-token")
            
            # Should have 2 calls: fetch + delete
            assert len(responses.calls) == 2
    
    @responses.activate
    def test_skip_deletion_when_no_steps(self):
        """Test that deletion is skipped when no steps exist."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"data": {"getTest": {"issueId": "10001", "steps": []}}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {"test-token": "steps"}):
            
            from userstory2TestCasesAgent import delete_all_test_steps_graphql
            
            delete_all_test_steps_graphql("10001", "test-token")
            
            # Only fetch call, no delete
            assert len(responses.calls) == 1


@pytest.mark.integration
class TestXrayTestPlanLinking:
    """Integration tests for linking tests to test plans."""
    
    @responses.activate
    def test_link_single_test_to_plan(self):
        """Test linking a single test to a test plan."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={
                "data": {
                    "addTestsToTestPlan": {
                        "addedTests": ["10001"],
                        "warning": None
                    }
                }
            },
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import link_tests_to_plan_graphql
            
            link_tests_to_plan_graphql("plan-123", ["10001"], "test-token")
            
            assert len(responses.calls) == 1
    
    @responses.activate
    def test_link_multiple_tests_to_plan(self):
        """Test linking multiple tests to a test plan."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={
                "data": {
                    "addTestsToTestPlan": {
                        "addedTests": ["10001", "10002", "10003"],
                        "warning": None
                    }
                }
            },
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import link_tests_to_plan_graphql
            
            link_tests_to_plan_graphql("plan-123", ["10001", "10002", "10003"], "test-token")
            
            request_body = json.loads(responses.calls[0].request.body)
            assert len(request_body["variables"]["testIssueIds"]) == 3
    
    @responses.activate
    def test_link_tests_converts_ids_to_strings(self):
        """Test that numeric IDs are converted to strings."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"data": {"addTestsToTestPlan": {"addedTests": [], "warning": None}}},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import link_tests_to_plan_graphql
            
            # Pass integers
            link_tests_to_plan_graphql(12345, [10001, 10002], "test-token")
            
            request_body = json.loads(responses.calls[0].request.body)
            assert request_body["variables"]["issueId"] == "12345"
            assert all(isinstance(tid, str) for tid in request_body["variables"]["testIssueIds"])
    
    @responses.activate
    def test_link_tests_graphql_error(self):
        """Test handling of GraphQL errors when linking."""
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={"errors": [{"message": "Test plan not found"}]},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import link_tests_to_plan_graphql
            
            # Should not raise, just log error
            link_tests_to_plan_graphql("invalid-plan", ["10001"], "test-token")


@pytest.mark.integration
class TestXraySchemaIntrospection:
    """Integration tests for Xray schema introspection."""
    
    @responses.activate
    def test_discover_step_field_name(self):
        """Test schema introspection to discover step field name."""
        # Introspection response
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={
                "data": {
                    "testType": {
                        "fields": [
                            {"name": "issueId"},
                            {"name": "testSteps"},
                            {"name": "projectId"}
                        ]
                    },
                    "mutationType": {
                        "fields": [
                            {
                                "name": "removeTestStep",
                                "args": [{"name": "issueId"}, {"name": "stepId"}],
                                "type": {"name": "TestStep", "kind": "OBJECT", "ofType": None}
                            }
                        ]
                    }
                }
            },
            status=200
        )
        # Return field introspection
        responses.add(
            responses.POST,
            XRAY_GRAPHQL_URL,
            json={
                "data": {
                    "__type": {
                        "fields": [
                            {"name": "issueId", "type": {"kind": "SCALAR"}},
                            {"name": "id", "type": {"kind": "SCALAR"}}
                        ]
                    }
                }
            },
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent._xray_step_field_cache', {}), \
             patch('userstory2TestCasesAgent._xray_remove_step_arg_cache', {}), \
             patch('userstory2TestCasesAgent._xray_remove_step_return_cache', {}):
            
            from userstory2TestCasesAgent import _introspect_xray_schema, _xray_step_field_cache
            
            _introspect_xray_schema("test-token")
            
            # Cache should be populated
            assert "test-token" in _xray_step_field_cache
