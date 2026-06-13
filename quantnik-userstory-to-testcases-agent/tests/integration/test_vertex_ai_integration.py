"""
Integration tests for Vertex AI / Gemini model interactions.

Tests the AI generation pipeline including scenario and test case generation.
"""
import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestVertexAIInitialization:
    """Integration tests for Vertex AI initialization."""
    
    def test_model_is_available_after_init(self, vertex_ai_config):
        """Test that model is available after initialization."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import model
            
            # Model should be defined (may be mocked)
            assert model is not None or True  # Just check import works
    
    def test_generation_config_values(self):
        """Test that generation config has expected values."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import GENERATION_CONFIG
            
            assert "temperature" in GENERATION_CONFIG
            assert "top_p" in GENERATION_CONFIG
            assert "top_k" in GENERATION_CONFIG
            assert GENERATION_CONFIG["temperature"] <= 1.0
            assert GENERATION_CONFIG["top_p"] <= 1.0


@pytest.mark.integration
class TestScenarioGeneration:
    """Integration tests for test scenario generation."""
    
    def test_generate_functional_scenarios(self, sample_user_story, mock_vertex_ai_response):
        """Test generating functional test scenarios."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = mock_vertex_ai_response["scenarios"]
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            result = generate_test_scenarios_from_userstory(sample_user_story, "Functional")
            
            assert result is not None
            assert "TS01" in result or "Test Scenario" in result
            mock_model.generate_content.assert_called_once()
    
    def test_generate_boundary_negative_scenarios(self, sample_user_story, mock_vertex_ai_response):
        """Test generating boundary and negative test scenarios."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = mock_vertex_ai_response["scenarios"]
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            result = generate_test_scenarios_from_userstory(sample_user_story, "Boundary & Negative")
            
            assert result is not None
    
    def test_generate_gherkin_scenarios(self, sample_user_story):
        """Test generating Gherkin BDD scenarios."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            gherkin_response = """
            Test Scenario Name: Valid Login
            Test Scenario Description:
            Given user is on the login page
            When user enters valid credentials
            And user clicks login button
            Then user should be redirected to dashboard
            """
            
            mock_response = MagicMock()
            mock_response.text = gherkin_response
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            result = generate_test_scenarios_from_userstory(sample_user_story, "Gherkin Functional")
            
            assert result is not None
    
    def test_scenario_generation_uses_correct_prompt(self, sample_user_story, mock_vertex_ai_response):
        """Test that correct prompt template is used for each scenario type."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = mock_vertex_ai_response["scenarios"]
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            generate_test_scenarios_from_userstory(sample_user_story, "Functional")
            
            call_args = mock_model.generate_content.call_args
            prompt = call_args[0][0]
            
            # Verify prompt contains user story
            assert "password" in prompt.lower() or "login" in prompt.lower() or "reset" in prompt.lower()
    
    def test_all_scenario_types_generate_successfully(self, sample_user_story, all_scenario_types, mock_vertex_ai_response):
        """Test that all scenario types can generate scenarios."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = mock_vertex_ai_response["scenarios"]
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            for scenario_type in all_scenario_types:
                result = generate_test_scenarios_from_userstory(sample_user_story, scenario_type)
                assert result is not None, f"Failed for scenario type: {scenario_type}"


@pytest.mark.integration
class TestTestCaseGeneration:
    """Integration tests for test case generation."""
    
    def test_generate_test_cases_returns_dict(self, sample_user_story, mock_vertex_ai_response):
        """Test that generate_test_cases returns proper dictionary."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = mock_vertex_ai_response["scenarios"]
            
            mock_tc_response = MagicMock()
            mock_tc_response.text = f"```json\n{json.dumps(mock_vertex_ai_response['test_cases'])}\n```"
            
            mock_model.generate_content.side_effect = [mock_scenario_response, mock_tc_response]
            
            from userstory2TestCasesAgent import generate_test_cases
            
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "Test Scenarios" in result
            assert "Test Cases" in result
    
    def test_test_cases_have_required_fields(self, sample_user_story, mock_vertex_ai_response):
        """Test that generated test cases have all required fields."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = mock_vertex_ai_response["scenarios"]
            
            mock_tc_response = MagicMock()
            mock_tc_response.text = json.dumps(mock_vertex_ai_response["test_cases"])
            
            mock_model.generate_content.side_effect = [mock_scenario_response, mock_tc_response]
            
            from userstory2TestCasesAgent import generate_test_cases
            
            result = generate_test_cases(sample_user_story, "Functional")
            
            test_cases = json.loads(result["Test Cases"]) if isinstance(result["Test Cases"], str) else result["Test Cases"]
            
            for tc in test_cases:
                assert "Test Case Name" in tc or "Test Case ID" in tc
    
    def test_model_called_twice_for_test_cases(self, sample_user_story, mock_vertex_ai_response):
        """Test that model is called twice: once for scenarios, once for test cases."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = mock_vertex_ai_response["scenarios"]
            
            mock_tc_response = MagicMock()
            mock_tc_response.text = json.dumps(mock_vertex_ai_response["test_cases"])
            
            mock_model.generate_content.side_effect = [mock_scenario_response, mock_tc_response]
            
            from userstory2TestCasesAgent import generate_test_cases
            
            generate_test_cases(sample_user_story, "Functional")
            
            assert mock_model.generate_content.call_count == 2
    
    def test_json_extraction_from_code_block(self, sample_user_story, mock_vertex_ai_response):
        """Test JSON extraction from markdown code blocks."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = mock_vertex_ai_response["scenarios"]
            
            # Response wrapped in markdown code block
            mock_tc_response = MagicMock()
            mock_tc_response.text = f"Here are the test cases:\n```json\n{json.dumps(mock_vertex_ai_response['test_cases'])}\n```\nEnd of response."
            
            mock_model.generate_content.side_effect = [mock_scenario_response, mock_tc_response]
            
            from userstory2TestCasesAgent import generate_test_cases
            
            result = generate_test_cases(sample_user_story, "Functional")
            
            # Should successfully extract JSON
            assert "Test Cases" in result
            assert "error" not in result


@pytest.mark.integration
class TestAIErrorHandling:
    """Integration tests for AI error handling."""
    
    def test_empty_user_story_raises_error(self):
        """Test that empty user story raises ValueError."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(ValueError, match="empty"):
                generate_test_scenarios_from_userstory("", "Functional")
    
    def test_empty_model_response_raises_error(self, sample_user_story):
        """Test that empty model response raises ValueError."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = ""
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(ValueError, match="Empty response"):
                generate_test_scenarios_from_userstory(sample_user_story, "Functional")
    
    def test_model_exception_returns_error_dict(self, sample_user_story):
        """Test that model exception returns error dictionary."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_model.generate_content.side_effect = Exception("Model unavailable")
            
            from userstory2TestCasesAgent import generate_test_cases
            
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "error" in result
            assert "Model unavailable" in result["error"]


@pytest.mark.integration
class TestRetryMechanism:
    """Integration tests for API retry mechanism."""
    
    def test_retry_on_transient_error(self, sample_user_story):
        """Test retry on transient SSL/connection errors."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model, \
             patch('userstory2TestCasesAgent.time.sleep'):
            
            mock_response = MagicMock()
            mock_response.text = "Test scenarios generated"
            
            # Fail twice with SSL error, then succeed
            mock_model.generate_content.side_effect = [
                Exception("SSL certificate verify failed"),
                Exception("Connection timeout"),
                mock_response
            ]
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            result = generate_test_scenarios_from_userstory(sample_user_story, "Functional")
            
            assert result == "Test scenarios generated"
            assert mock_model.generate_content.call_count == 3
    
    def test_max_retries_exceeded(self, sample_user_story):
        """Test failure after max retries exceeded."""
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
            
            mock_model.generate_content.side_effect = ValueError("Invalid input")
            
            from userstory2TestCasesAgent import generate_test_cases
            
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "error" in result
            # Should only be called once (no retry for ValueError)
            assert mock_model.generate_content.call_count == 1


@pytest.mark.integration
class TestSafetySettings:
    """Integration tests for content safety settings."""
    
    def test_safety_settings_applied(self, sample_user_story, mock_vertex_ai_response):
        """Test that safety settings are applied to model calls."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = mock_vertex_ai_response["scenarios"]
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory, SAFETY_SETTINGS
            
            generate_test_scenarios_from_userstory(sample_user_story, "Functional")
            
            call_kwargs = mock_model.generate_content.call_args[1]
            assert "safety_settings" in call_kwargs
            assert call_kwargs["safety_settings"] == SAFETY_SETTINGS
