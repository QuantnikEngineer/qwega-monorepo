"""
Integration tests for qTest Manager API interactions.

Tests direct integration with qTest for test case management.
"""
import pytest
import json
import responses
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestQtestAuthentication:
    """Integration tests for qTest authentication."""
    
    @responses.activate
    def test_bearer_token_in_request(self, qtest_config, mock_qtest_response):
        """Test that Bearer token is included in requests."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases",
            json=mock_qtest_response,
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {"Test Case Name": "Test", "Test Case Description": "Desc"}
            
            create_test_case_in_qtest(qtest_config["project_id"], test_case, qtest_config)
            
            auth_header = responses.calls[0].request.headers["Authorization"]
            assert "Bearer" in auth_header


@pytest.mark.integration
class TestQtestTestCaseCreation:
    """Integration tests for qTest test case creation."""
    
    @responses.activate
    def test_create_test_case_success(self, qtest_config, mock_qtest_response):
        """Test successful test case creation in qTest."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases",
            json=mock_qtest_response,
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {
                "Test Case Name": "Login Test",
                "Test Case Description": "Test valid login functionality"
            }
            
            result = create_test_case_in_qtest(qtest_config["project_id"], test_case, qtest_config)
            
            assert result == 12345
    
    @responses.activate
    def test_create_test_case_with_200_status(self, qtest_config, mock_qtest_response):
        """Test that 200 status is also accepted for creation."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases",
            json=mock_qtest_response,
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {"Test Case Name": "Test", "Test Case Description": "Desc"}
            
            result = create_test_case_in_qtest(qtest_config["project_id"], test_case, qtest_config)
            
            assert result is not None
    
    @responses.activate
    def test_create_test_case_payload_structure(self, qtest_config, mock_qtest_response):
        """Test that request payload has correct structure."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases",
            json=mock_qtest_response,
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {
                "Test Case Name": "My Test Case",
                "Test Case Description": "My Description"
            }
            
            create_test_case_in_qtest(qtest_config["project_id"], test_case, qtest_config)
            
            request_body = json.loads(responses.calls[0].request.body)
            assert request_body["name"] == "My Test Case"
            assert request_body["description"] == "My Description"
    
    @responses.activate
    def test_create_test_case_missing_name(self, qtest_config, mock_qtest_response):
        """Test handling of test case without name."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases",
            json=mock_qtest_response,
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {"Test Case Description": "Only description"}
            
            create_test_case_in_qtest(qtest_config["project_id"], test_case, qtest_config)
            
            request_body = json.loads(responses.calls[0].request.body)
            assert request_body["name"] == "Unnamed Test Case"
    
    @responses.activate
    def test_create_test_case_failure(self, qtest_config):
        """Test handling of creation failure."""
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
    def test_create_test_case_server_error(self, qtest_config):
        """Test handling of server error."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases",
            json={"error": "Internal server error"},
            status=500
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {"Test Case Name": "Test", "Test Case Description": "Desc"}
            
            result = create_test_case_in_qtest(qtest_config["project_id"], test_case, qtest_config)
            
            assert result is None
    
    def test_create_test_case_network_error(self, qtest_config):
        """Test handling of network error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests.post') as mock_post:
            
            mock_post.side_effect = Exception("Connection refused")
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {"Test Case Name": "Test", "Test Case Description": "Desc"}
            
            result = create_test_case_in_qtest(qtest_config["project_id"], test_case, qtest_config)
            
            assert result is None


@pytest.mark.integration
class TestQtestTestStepsAddition:
    """Integration tests for adding test steps in qTest."""
    
    @responses.activate
    def test_add_steps_success(self, qtest_config):
        """Test successful addition of test steps."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases/12345/test-steps",
            json=[],
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            
            steps = [
                {"Test Case Step": "Step 1", "Expected Results": "Result 1"},
                {"Test Case Step": "Step 2", "Expected Results": "Result 2"}
            ]
            
            add_test_steps_in_qtest(qtest_config["project_id"], "12345", steps, qtest_config)
            
            assert len(responses.calls) == 1
    
    @responses.activate
    def test_add_steps_payload_structure(self, qtest_config):
        """Test that steps payload has correct structure."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases/12345/test-steps",
            json=[],
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            
            steps = [
                {"Test Case Step": "Click button", "Expected Results": "Button clicked"},
                {"Test Case Step": "Enter text", "Expected Results": "Text entered"}
            ]
            
            add_test_steps_in_qtest(qtest_config["project_id"], "12345", steps, qtest_config)
            
            request_body = json.loads(responses.calls[0].request.body)
            
            assert len(request_body) == 2
            assert request_body[0]["order"] == 1
            assert request_body[0]["description"] == "Click button"
            assert request_body[0]["expected_result"] == "Button clicked"
            assert request_body[1]["order"] == 2
    
    @responses.activate
    def test_add_steps_with_200_status(self, qtest_config):
        """Test that 200 status is also accepted for adding steps."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases/12345/test-steps",
            json=[],
            status=200
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            # Should not raise
            add_test_steps_in_qtest(qtest_config["project_id"], "12345", steps, qtest_config)
    
    @responses.activate
    def test_add_steps_missing_expected_results(self, qtest_config):
        """Test handling of steps without expected results."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases/12345/test-steps",
            json=[],
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            
            steps = [{"Test Case Step": "Step without expected result"}]
            
            add_test_steps_in_qtest(qtest_config["project_id"], "12345", steps, qtest_config)
            
            request_body = json.loads(responses.calls[0].request.body)
            assert request_body[0]["expected_result"] == ""
    
    @responses.activate
    def test_add_empty_steps_list(self, qtest_config):
        """Test adding empty steps list."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases/12345/test-steps",
            json=[],
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            
            add_test_steps_in_qtest(qtest_config["project_id"], "12345", [], qtest_config)
            
            request_body = json.loads(responses.calls[0].request.body)
            assert request_body == []
    
    @responses.activate
    def test_add_steps_failure(self, qtest_config):
        """Test handling of steps addition failure."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases/12345/test-steps",
            json={"error": "Bad request"},
            status=400
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            # Should not raise, just log error
            add_test_steps_in_qtest(qtest_config["project_id"], "12345", steps, qtest_config)
    
    def test_add_steps_network_error(self, qtest_config):
        """Test handling of network error when adding steps."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.requests.post') as mock_post:
            
            mock_post.side_effect = Exception("Network error")
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            # Should not raise, just log error
            add_test_steps_in_qtest(qtest_config["project_id"], "12345", steps, qtest_config)


@pytest.mark.integration
class TestQtestUrlConstruction:
    """Integration tests for qTest URL construction."""
    
    @responses.activate
    def test_test_case_url_construction(self, qtest_config, mock_qtest_response):
        """Test that test case URL is constructed correctly."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/12345/test-cases",
            json=mock_qtest_response,
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import create_test_case_in_qtest
            
            test_case = {"Test Case Name": "Test", "Test Case Description": "Desc"}
            
            create_test_case_in_qtest("12345", test_case, qtest_config)
            
            assert "/projects/12345/test-cases" in responses.calls[0].request.url
    
    @responses.activate
    def test_test_steps_url_construction(self, qtest_config):
        """Test that test steps URL is constructed correctly."""
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/12345/test-cases/67890/test-steps",
            json=[],
            status=201
        )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import add_test_steps_in_qtest
            
            steps = [{"Test Case Step": "Step", "Expected Results": "Result"}]
            
            add_test_steps_in_qtest("12345", "67890", steps, qtest_config)
            
            assert "/projects/12345/test-cases/67890/test-steps" in responses.calls[0].request.url


@pytest.mark.integration
class TestQtestProcessing:
    """Integration tests for qTest processing workflow."""
    
    @responses.activate
    def test_process_single_story_qtest(self, sample_user_story, mock_vertex_ai_response, qtest_config, mock_qtest_response):
        """Test processing a single story for qTest."""
        # Mock qTest test case creation
        responses.add(
            responses.POST,
            f"{qtest_config['base_url']}/projects/{qtest_config['project_id']}/test-cases",
            json=mock_qtest_response,
            status=201
        )
        # Mock qTest test steps addition
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
            
            assert "scenario_type" in result
            assert "qtest_push_result" in result
            assert result["qtest_push_result"]["total_tests_created"] > 0
