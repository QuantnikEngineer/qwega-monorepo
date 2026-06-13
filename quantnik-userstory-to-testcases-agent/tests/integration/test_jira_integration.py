"""
Integration tests for Jira REST API interactions.

Tests direct integration with Jira Cloud APIs for issue management.
"""
import pytest
import json
import responses
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestJiraAuthentication:
    """Integration tests for Jira authentication."""
    
    @responses.activate
    def test_basic_auth_success(self, jira_config):
        """Test successful Basic authentication with Jira."""
        responses.add(
            responses.GET,
            f"{jira_config['base_url']}rest/api/3/issue/TEST-123",
            json={"id": "10001", "key": "TEST-123"},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            result = get_issue_id_from_key("TEST-123", jira_config)
            
            assert result == "10001"
            # Verify auth header was sent
            assert "Authorization" in responses.calls[0].request.headers
    
    @responses.activate
    def test_auth_failure_returns_none(self, jira_config):
        """Test that authentication failure returns None."""
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
    def test_forbidden_returns_none(self, jira_config):
        """Test that 403 Forbidden returns None."""
        responses.add(
            responses.GET,
            f"{jira_config['base_url']}rest/api/3/issue/TEST-123",
            json={"errorMessages": ["Forbidden"]},
            status=403
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            result = get_issue_id_from_key("TEST-123", jira_config)
            
            assert result is None


@pytest.mark.integration
class TestJiraIssueCreation:
    """Integration tests for Jira issue creation."""
    
    @responses.activate
    def test_create_single_test_issue(self, jira_config, mock_jira_issue_response):
        """Test creating a single Test issue in Jira."""
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json=mock_jira_issue_response,
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            
            test_cases = [{
                "Test Case Name": "Login Test",
                "Test Case Description": "Test valid login"
            }]
            
            result = create_tests_in_jira_cloud("STORY-001", test_cases, jira_config)
            
            assert len(result) == 1
            assert result[0] == "TEST-100"
    
    @responses.activate
    def test_create_multiple_test_issues(self, jira_config):
        """Test creating multiple Test issues in Jira."""
        # Add multiple responses
        for i in range(3):
            responses.add(
                responses.POST,
                f"{jira_config['base_url']}rest/api/3/issue",
                json={"id": f"1000{i}", "key": f"TEST-10{i}"},
                status=201
            )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            
            test_cases = [
                {"Test Case Name": f"Test {i}", "Test Case Description": f"Description {i}"}
                for i in range(3)
            ]
            
            result = create_tests_in_jira_cloud("STORY-001", test_cases, jira_config)
            
            assert len(result) == 3
    
    @responses.activate
    def test_issue_has_correct_type(self, jira_config, mock_jira_issue_response):
        """Test that created issue has type 'Test'."""
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json=mock_jira_issue_response,
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            
            test_cases = [{"Test Case Name": "Test", "Test Case Description": "Desc"}]
            
            create_tests_in_jira_cloud("STORY-001", test_cases, jira_config)
            
            request_body = json.loads(responses.calls[0].request.body)
            assert request_body["fields"]["issuetype"]["name"] == "Test"
    
    @responses.activate
    def test_issue_has_story_label(self, jira_config, mock_jira_issue_response):
        """Test that created issue has story ID as label."""
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json=mock_jira_issue_response,
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            
            test_cases = [{"Test Case Name": "Test", "Test Case Description": "Desc"}]
            
            create_tests_in_jira_cloud("STORY-001", test_cases, jira_config)
            
            request_body = json.loads(responses.calls[0].request.body)
            assert "STORY-001" in request_body["fields"]["labels"]
    
    @responses.activate
    def test_partial_creation_failure(self, jira_config):
        """Test handling when some issues fail to create."""
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"id": "10001", "key": "TEST-100"},
            status=201
        )
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/issue",
            json={"errorMessages": ["Creation failed"]},
            status=400
        )
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
            
            # Should have 2 successful, 1 failed
            assert len(result) == 2
    
    @responses.activate
    def test_all_creation_failures(self, jira_config):
        """Test handling when all issues fail to create."""
        for _ in range(2):
            responses.add(
                responses.POST,
                f"{jira_config['base_url']}rest/api/3/issue",
                json={"errorMessages": ["Server error"]},
                status=500
            )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_tests_in_jira_cloud
            
            test_cases = [
                {"Test Case Name": f"Test {i}", "Test Case Description": f"Desc {i}"}
                for i in range(2)
            ]
            
            result = create_tests_in_jira_cloud("STORY-001", test_cases, jira_config)
            
            assert result == []


@pytest.mark.integration
class TestJiraIssueRetrieval:
    """Integration tests for Jira issue retrieval."""
    
    @responses.activate
    def test_get_issue_numeric_id(self, jira_config):
        """Test retrieving numeric ID from issue key."""
        responses.add(
            responses.GET,
            f"{jira_config['base_url']}rest/api/3/issue/TEST-123",
            json={"id": "10001", "key": "TEST-123"},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            result = get_issue_id_from_key("TEST-123", jira_config)
            
            assert result == "10001"
    
    @responses.activate
    def test_issue_not_found(self, jira_config):
        """Test handling non-existent issue."""
        responses.add(
            responses.GET,
            f"{jira_config['base_url']}rest/api/3/issue/INVALID-999",
            json={"errorMessages": ["Issue does not exist"]},
            status=404
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            result = get_issue_id_from_key("INVALID-999", jira_config)
            
            assert result is None


@pytest.mark.integration
class TestJiraIssueUpdate:
    """Integration tests for Jira issue updates."""
    
    @responses.activate
    def test_update_issue_success(self, jira_config):
        """Test successful issue update."""
        responses.add(
            responses.PUT,
            f"{jira_config['base_url']}rest/api/3/issue/TEST-123",
            status=204
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import update_jira_test_issue
            
            # Should not raise exception
            update_jira_test_issue("TEST-123", "New Name", "New Description", jira_config)
            
            # Verify request was made
            assert len(responses.calls) == 1
    
    @responses.activate
    def test_update_issue_payload(self, jira_config):
        """Test that update payload has correct structure."""
        responses.add(
            responses.PUT,
            f"{jira_config['base_url']}rest/api/3/issue/TEST-123",
            status=204
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import update_jira_test_issue
            
            update_jira_test_issue("TEST-123", "Updated Name", "Updated Desc", jira_config)
            
            request_body = json.loads(responses.calls[0].request.body)
            assert request_body["fields"]["summary"] == "Updated Name"
            assert "description" in request_body["fields"]
    
    @responses.activate
    def test_update_issue_failure_handling(self, jira_config):
        """Test handling of update failure."""
        responses.add(
            responses.PUT,
            f"{jira_config['base_url']}rest/api/3/issue/TEST-123",
            json={"errorMessages": ["Update failed"]},
            status=400
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import update_jira_test_issue
            
            # Should not raise, just log error
            update_jira_test_issue("TEST-123", "Name", "Desc", jira_config)


@pytest.mark.integration
class TestJiraSearch:
    """Integration tests for Jira search (JQL)."""
    
    @responses.activate
    def test_search_by_label_v3_endpoint(self, jira_config, mock_jira_search_response):
        """Test searching for issues by label using v3 endpoint."""
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/search/jql",
            json=mock_jira_search_response,
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            
            result = fetch_existing_test_cases_by_label("STORY-001", jira_config)
            
            assert len(result) == 1
            assert result[0]["key"] == "TEST-100"
    
    @responses.activate
    def test_search_fallback_to_v2_endpoint(self, jira_config, mock_jira_search_response):
        """Test fallback to v2 endpoint when v3 fails."""
        # v3 fails
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/search/jql",
            json={"errorMessages": ["Not found"]},
            status=404
        )
        # v2 succeeds
        responses.add(
            responses.GET,
            f"{jira_config['base_url']}rest/api/2/search",
            json=mock_jira_search_response,
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            
            result = fetch_existing_test_cases_by_label("STORY-001", jira_config)
            
            assert len(result) == 1
    
    @responses.activate
    def test_search_no_results(self, jira_config):
        """Test search returning no results."""
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/search/jql",
            json={"issues": [], "total": 0},
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            
            result = fetch_existing_test_cases_by_label("STORY-NONE", jira_config)
            
            assert result == []
    
    @responses.activate
    def test_search_parses_adf_description(self, jira_config):
        """Test parsing of Atlassian Document Format descriptions."""
        adf_response = {
            "issues": [{
                "id": "10001",
                "key": "TEST-100",
                "fields": {
                    "summary": "Test Summary",
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": "First part"},
                                    {"type": "text", "text": " second part"}
                                ]
                            }
                        ]
                    }
                }
            }]
        }
        
        responses.add(
            responses.POST,
            f"{jira_config['base_url']}rest/api/3/search/jql",
            json=adf_response,
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import fetch_existing_test_cases_by_label
            
            result = fetch_existing_test_cases_by_label("STORY-001", jira_config)
            
            assert "First part" in result[0]["description"]
            assert "second part" in result[0]["description"]


@pytest.mark.integration
class TestJiraRateLimiting:
    """Integration tests for Jira API rate limiting handling."""
    
    @responses.activate
    def test_rate_limit_response(self, jira_config):
        """Test handling of 429 rate limit response."""
        responses.add(
            responses.GET,
            f"{jira_config['base_url']}rest/api/3/issue/TEST-123",
            json={"errorMessages": ["Rate limit exceeded"]},
            status=429,
            headers={"Retry-After": "60"}
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            result = get_issue_id_from_key("TEST-123", jira_config)
            
            # Should return None on rate limit
            assert result is None


@pytest.mark.integration
class TestJiraNetworkErrors:
    """Integration tests for Jira network error handling."""
    
    def test_connection_error_returns_none(self, jira_config):
        """Test that connection errors return None."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests.get') as mock_get:
            
            mock_get.side_effect = Exception("Connection refused")
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            result = get_issue_id_from_key("TEST-123", jira_config)
            
            assert result is None
    
    def test_timeout_error_returns_none(self, jira_config):
        """Test that timeout errors return None."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests.get') as mock_get:
            
            mock_get.side_effect = Exception("Request timeout")
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            result = get_issue_id_from_key("TEST-123", jira_config)
            
            assert result is None
