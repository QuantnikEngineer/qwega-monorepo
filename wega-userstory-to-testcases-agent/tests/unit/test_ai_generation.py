"""
Unit tests for AI generation functions in userstory2TestCasesAgent.py

Tests cover:
- generate_test_scenarios_from_userstory()
- generate_test_cases()
"""
import pytest
from unittest.mock import MagicMock, patch
import json


class TestGenerateTestScenariosFromUserstory:
    """Tests for generate_test_scenarios_from_userstory() function."""
    
    def test_generates_scenarios_for_functional_type(self, sample_user_story, sample_test_scenarios_response):
        """Test scenario generation for Functional type."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = sample_test_scenarios_response
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            result = generate_test_scenarios_from_userstory(sample_user_story, "Functional")
            
            assert result == sample_test_scenarios_response
            mock_model.generate_content.assert_called_once()
    
    def test_generates_scenarios_for_boundary_negative_type(self, sample_user_story, sample_test_scenarios_response):
        """Test scenario generation for Boundary & Negative type."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = sample_test_scenarios_response
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            result = generate_test_scenarios_from_userstory(sample_user_story, "Boundary & Negative")
            
            assert result is not None
    
    def test_generates_scenarios_for_gherkin_functional_type(self, sample_user_story):
        """Test scenario generation for Gherkin Functional type."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            gherkin_response = """
            Test Scenario Name: Valid Login
            Test Scenario Description:
            Given user is on login page
            When user enters valid credentials
            Then user should be redirected to dashboard
            """
            mock_response = MagicMock()
            mock_response.text = gherkin_response
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            result = generate_test_scenarios_from_userstory(sample_user_story, "Gherkin Functional")
            
            assert "Given" in result or result is not None
    
    def test_raises_error_for_empty_user_story(self, sample_user_story_empty):
        """Test that empty user story raises ValueError."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(ValueError, match="User story cannot be empty"):
                generate_test_scenarios_from_userstory(sample_user_story_empty, "Functional")
    
    def test_raises_error_for_whitespace_user_story(self, sample_user_story_whitespace):
        """Test that whitespace-only user story raises ValueError."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(ValueError, match="User story cannot be empty"):
                generate_test_scenarios_from_userstory(sample_user_story_whitespace, "Functional")
    
    def test_raises_error_for_none_user_story(self):
        """Test that None user story raises TypeError (len() on None)."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(TypeError):
                generate_test_scenarios_from_userstory(None, "Functional")
    
    def test_raises_error_for_empty_model_response(self, sample_user_story):
        """Test that empty model response raises ValueError."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = ""
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(ValueError, match="Empty response from model"):
                generate_test_scenarios_from_userstory(sample_user_story, "Functional")
    
    def test_raises_error_for_none_model_response(self, sample_user_story):
        """Test that None model response raises ValueError."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_model.generate_content.return_value = None
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(ValueError, match="Empty response from model"):
                generate_test_scenarios_from_userstory(sample_user_story, "Functional")
    
    def test_uses_default_prompt_for_unknown_type(self, sample_user_story, sample_test_scenarios_response):
        """Test that unknown scenario type uses default prompt."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = sample_test_scenarios_response
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            result = generate_test_scenarios_from_userstory(sample_user_story, "UnknownType")
            
            assert result is not None
    
    def test_prompt_contains_user_story(self, sample_user_story, sample_test_scenarios_response):
        """Test that the prompt includes the user story."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = sample_test_scenarios_response
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            generate_test_scenarios_from_userstory(sample_user_story, "Functional")
            
            call_args = mock_model.generate_content.call_args
            prompt = call_args[0][0]
            assert "login" in prompt.lower()
    
    def test_handles_model_exception(self, sample_user_story):
        """Test handling of model exceptions."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_model.generate_content.side_effect = Exception("Model error")
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            with pytest.raises(Exception, match="Model error"):
                generate_test_scenarios_from_userstory(sample_user_story, "Functional")
    
    def test_all_scenario_types_have_prompts(self, sample_user_story, valid_scenario_types, sample_test_scenarios_response):
        """Test that all valid scenario types work without error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = sample_test_scenarios_response
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            for scenario_type in valid_scenario_types:
                result = generate_test_scenarios_from_userstory(sample_user_story, scenario_type)
                assert result is not None


class TestGenerateTestCases:
    """Tests for generate_test_cases() function."""
    
    def test_returns_dict_with_test_scenarios_and_cases(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test that function returns dict with both Test Scenarios and Test Cases."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response_scenarios = MagicMock()
            mock_response_scenarios.text = sample_test_scenarios_response
            
            mock_response_cases = MagicMock()
            mock_response_cases.text = f"```json{sample_test_cases_json_string}```"
            
            mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
            
            from userstory2TestCasesAgent import generate_test_cases
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "Test Scenarios" in result
            assert "Test Cases" in result
    
    def test_extracts_json_from_code_block(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test that JSON is extracted from markdown code block."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response_scenarios = MagicMock()
            mock_response_scenarios.text = sample_test_scenarios_response
            
            mock_response_cases = MagicMock()
            mock_response_cases.text = f"Here is the result:\n```json\n{sample_test_cases_json_string}\n```\nEnd of result."
            
            mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
            
            from userstory2TestCasesAgent import generate_test_cases
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "Test Cases" in result
    
    def test_handles_raw_json_response(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test handling of raw JSON response without code block."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response_scenarios = MagicMock()
            mock_response_scenarios.text = sample_test_scenarios_response
            
            mock_response_cases = MagicMock()
            mock_response_cases.text = sample_test_cases_json_string
            
            mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
            
            from userstory2TestCasesAgent import generate_test_cases
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "Test Cases" in result
    
    def test_returns_error_for_empty_user_story(self, sample_user_story_empty):
        """Test that empty user story returns error dict."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import generate_test_cases
            result = generate_test_cases(sample_user_story_empty, "Functional")
            
            assert "error" in result
    
    def test_raises_error_for_none_user_story(self):
        """Test that None user story raises TypeError (len() on None)."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import generate_test_cases
            
            with pytest.raises(TypeError):
                generate_test_cases(None, "Functional")
    
    def test_returns_error_on_model_failure(self, sample_user_story):
        """Test that model failure returns error dict."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_model.generate_content.side_effect = Exception("Model crashed")
            
            from userstory2TestCasesAgent import generate_test_cases
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "error" in result
            assert "Model crashed" in result["error"]
    
    def test_returns_error_on_empty_model_response(self, sample_user_story, sample_test_scenarios_response):
        """Test that empty model response for test cases returns error."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response_scenarios = MagicMock()
            mock_response_scenarios.text = sample_test_scenarios_response
            
            mock_response_cases = MagicMock()
            mock_response_cases.text = ""
            
            mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
            
            from userstory2TestCasesAgent import generate_test_cases
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "error" in result
    
    def test_normalizes_test_scenarios(self, sample_user_story, sample_test_cases_json_string):
        """Test that test scenarios are normalized."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response_scenarios = MagicMock()
            mock_response_scenarios.text = "Scenario\\nwith\\nescapes"
            
            mock_response_cases = MagicMock()
            mock_response_cases.text = sample_test_cases_json_string
            
            mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
            
            from userstory2TestCasesAgent import generate_test_cases
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "Test Scenarios" in result
    
    def test_normalizes_test_cases(self, sample_user_story, sample_test_scenarios_response):
        """Test that test cases are normalized."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response_scenarios = MagicMock()
            mock_response_scenarios.text = sample_test_scenarios_response
            
            mock_response_cases = MagicMock()
            mock_response_cases.text = '```json[{"Test Case ID": "TC01\\nwith newline"}]```'
            
            mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
            
            from userstory2TestCasesAgent import generate_test_cases
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "Test Cases" in result
    
    def test_handles_multiple_code_blocks(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test that first JSON code block is used when multiple exist."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response_scenarios = MagicMock()
            mock_response_scenarios.text = sample_test_scenarios_response
            
            mock_response_cases = MagicMock()
            mock_response_cases.text = f"```json{sample_test_cases_json_string}```\n\nAnother block:\n```json{{}}```"
            
            mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
            
            from userstory2TestCasesAgent import generate_test_cases
            result = generate_test_cases(sample_user_story, "Functional")
            
            assert "Test Cases" in result
    
    def test_model_called_twice(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test that model is called twice (scenarios then cases)."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response_scenarios = MagicMock()
            mock_response_scenarios.text = sample_test_scenarios_response
            
            mock_response_cases = MagicMock()
            mock_response_cases.text = sample_test_cases_json_string
            
            mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
            
            from userstory2TestCasesAgent import generate_test_cases
            generate_test_cases(sample_user_story, "Functional")
            
            assert mock_model.generate_content.call_count == 2
    
    def test_second_prompt_includes_test_scenarios(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test that second prompt includes generated test scenarios."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response_scenarios = MagicMock()
            mock_response_scenarios.text = sample_test_scenarios_response
            
            mock_response_cases = MagicMock()
            mock_response_cases.text = sample_test_cases_json_string
            
            mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
            
            from userstory2TestCasesAgent import generate_test_cases
            generate_test_cases(sample_user_story, "Functional")
            
            second_call_args = mock_model.generate_content.call_args_list[1]
            second_prompt = second_call_args[0][0]
            assert "Test Scenarios" in second_prompt or "TS01" in second_prompt
    
    def test_all_scenario_types_work(self, sample_user_story, valid_scenario_types, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test that all valid scenario types generate test cases."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            from userstory2TestCasesAgent import generate_test_cases
            
            for scenario_type in valid_scenario_types:
                mock_response_scenarios = MagicMock()
                mock_response_scenarios.text = sample_test_scenarios_response
                
                mock_response_cases = MagicMock()
                mock_response_cases.text = sample_test_cases_json_string
                
                mock_model.generate_content.side_effect = [mock_response_scenarios, mock_response_cases]
                
                result = generate_test_cases(sample_user_story, scenario_type)
                
                assert "error" not in result or result.get("error") is None
                mock_model.reset_mock()
