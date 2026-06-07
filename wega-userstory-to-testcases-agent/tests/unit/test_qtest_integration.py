"""
Unit tests for qTest integration functions in userstory2TestCasesAgent.py

Tests cover:
- create_test_case_in_qtest()
- add_test_steps_in_qtest()
"""
import pytest
from unittest.mock import MagicMock, patch


class TestCreateTestCaseInQtest:
    """Tests for create_test_case_in_qtest() function."""
    
    def test_creates_test_case_successfully(self, sample_qtest_config, sample_test_cases_json):
        """Test successful test case creation in qTest."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "tc-123"}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            result = create_test_case_in_qtest("12345", sample_test_cases_json[0], sample_qtest_config)
            
            assert result["success"] is True
            assert result["test_case_id"] == "tc-123"
    
    def test_returns_error_on_failure(self, sample_qtest_config, sample_test_cases_json):
        """Test that error dict is returned on creation failure."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad request"
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            result = create_test_case_in_qtest("12345", sample_test_cases_json[0], sample_qtest_config)
            
            assert result["success"] is False
            assert "error" in result
    
    def test_returns_error_on_exception(self, sample_qtest_config, sample_test_cases_json):
        """Test that error dict is returned on exception."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_requests.post.side_effect = Exception("Network error")
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            result = create_test_case_in_qtest("12345", sample_test_cases_json[0], sample_qtest_config)
            
            assert result["success"] is False
            assert "Network error" in result["error"]
    
    def test_constructs_correct_url(self, sample_qtest_config, sample_test_cases_json):
        """Test that correct API URL is constructed."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "tc-123"}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            create_test_case_in_qtest("12345", sample_test_cases_json[0], sample_qtest_config)
            
            call_args = mock_requests.post.call_args
            url = call_args[0][0]
            assert "/projects/12345/test-cases" in url
    
    def test_uses_bearer_token_auth(self, sample_qtest_config, sample_test_cases_json):
        """Test that Bearer token authentication is used."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "tc-123"}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            create_test_case_in_qtest("12345", sample_test_cases_json[0], sample_qtest_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            assert "Bearer" in call_kwargs["headers"]["Authorization"]
    
    def test_sends_correct_payload(self, sample_qtest_config, sample_test_cases_json):
        """Test that correct payload is sent."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "tc-123"}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            create_test_case_in_qtest("12345", sample_test_cases_json[0], sample_qtest_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload["name"] == sample_test_cases_json[0]["Test Case Name"]
            assert payload["description"] == sample_test_cases_json[0]["Test Case Description"]
    
    def test_handles_missing_test_case_name(self, sample_qtest_config):
        """Test handling of test case without name."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "tc-123"}
            mock_requests.post.return_value = mock_response
            
            test_case = {"Test Case Description": "Description only"}
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            result = create_test_case_in_qtest("12345", test_case, sample_qtest_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload["name"] == "Unnamed Test Case"
    
    def test_handles_missing_description(self, sample_qtest_config):
        """Test handling of test case without description."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "tc-123"}
            mock_requests.post.return_value = mock_response
            
            test_case = {"Test Case Name": "Name only"}
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            result = create_test_case_in_qtest("12345", test_case, sample_qtest_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload["description"] == ""
    
    def test_accepts_200_status_code(self, sample_qtest_config, sample_test_cases_json):
        """Test that 200 status code is also accepted."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "tc-123"}
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            result = create_test_case_in_qtest("12345", sample_test_cases_json[0], sample_qtest_config)
            
            assert result["success"] is True
            assert result["test_case_id"] == "tc-123"
    
    def test_handles_server_error(self, sample_qtest_config, sample_test_cases_json):
        """Test handling of server error (500)."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal server error"
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            result = create_test_case_in_qtest("12345", sample_test_cases_json[0], sample_qtest_config)
            
            assert result["success"] is False
            assert "error" in result


class TestAddTestStepsInQtest:
    """Tests for add_test_steps_in_qtest() function."""
    
    def test_adds_steps_successfully(self, sample_qtest_config):
        """Test successful addition of test steps."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_requests.post.return_value = mock_response
            
            steps = [
                {"Test Case Step": "Step 1", "Expected Results": "Result 1"},
                {"Test Case Step": "Step 2", "Expected Results": "Result 2"}
            ]
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            add_test_steps_in_qtest("12345", "tc-123", steps, sample_qtest_config)
            
            mock_requests.post.assert_called_once()
    
    def test_constructs_correct_url(self, sample_qtest_config):
        """Test that correct API URL is constructed."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_requests.post.return_value = mock_response
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            add_test_steps_in_qtest("12345", "tc-123", steps, sample_qtest_config)
            
            call_args = mock_requests.post.call_args
            url = call_args[0][0]
            assert "/projects/12345/test-cases/tc-123/test-steps" in url
    
    def test_sends_correct_payload_format(self, sample_qtest_config):
        """Test that steps are sent in correct format."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_requests.post.return_value = mock_response
            
            steps = [
                {"Test Case Step": "Step 1", "Expected Results": "Result 1"},
                {"Test Case Step": "Step 2", "Expected Results": "Result 2"}
            ]
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            add_test_steps_in_qtest("12345", "tc-123", steps, sample_qtest_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            payload = call_kwargs["json"]
            
            assert len(payload) == 2
            assert payload[0]["order"] == 1
            assert payload[0]["description"] == "Step 1"
            assert payload[0]["expected_result"] == "Result 1"
            assert payload[1]["order"] == 2
    
    def test_handles_failure(self, sample_qtest_config):
        """Test handling of API failure."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_requests.post.return_value = mock_response
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            add_test_steps_in_qtest("12345", "tc-123", steps, sample_qtest_config)
    
    def test_handles_exception(self, sample_qtest_config):
        """Test handling of exception during API call."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_requests.post.side_effect = Exception("Network error")
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            add_test_steps_in_qtest("12345", "tc-123", steps, sample_qtest_config)
    
    def test_uses_bearer_token(self, sample_qtest_config):
        """Test that Bearer token is used for authentication."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_requests.post.return_value = mock_response
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            add_test_steps_in_qtest("12345", "tc-123", steps, sample_qtest_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            assert "Bearer" in call_kwargs["headers"]["Authorization"]
    
    def test_handles_empty_steps_list(self, sample_qtest_config):
        """Test handling of empty steps list."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_requests.post.return_value = mock_response
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            add_test_steps_in_qtest("12345", "tc-123", [], sample_qtest_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload == []
    
    def test_handles_missing_expected_results(self, sample_qtest_config):
        """Test handling of steps without expected results."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_requests.post.return_value = mock_response
            
            steps = [{"Test Case Step": "Step without expected result"}]
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            add_test_steps_in_qtest("12345", "tc-123", steps, sample_qtest_config)
            
            call_kwargs = mock_requests.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload[0]["expected_result"] == ""
    
    def test_accepts_200_status_code(self, sample_qtest_config):
        """Test that 200 status code is also accepted."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests') as mock_requests:
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_requests.post.return_value = mock_response
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            add_test_steps_in_qtest("12345", "tc-123", steps, sample_qtest_config)
