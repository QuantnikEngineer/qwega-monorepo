"""
Unit tests for brownfield logic functions in userstory2TestCasesAgent.py

Tests cover:
- _match_existing_key()
- diff_and_merge_test_cases()
- process_brownfield_story_jira()
"""
import pytest
from unittest.mock import MagicMock, patch
import json


class TestMatchExistingKey:
    """Tests for _match_existing_key() function."""
    
    def test_matches_identical_names(self, sample_existing_issues):
        """Test matching when names are identical."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import _match_existing_key
            result = _match_existing_key("Valid Login Test Case", sample_existing_issues)
            
            assert result == "TEST-100"
    
    def test_matches_similar_names_above_threshold(self, sample_existing_issues):
        """Test matching when names have >50% word overlap."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import _match_existing_key
            result = _match_existing_key("Valid Login Test", sample_existing_issues)
            
            assert result == "TEST-100"
    
    def test_returns_none_for_no_match(self, sample_existing_issues):
        """Test that None is returned when no match is found."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import _match_existing_key
            result = _match_existing_key("Completely Different Name", sample_existing_issues)
            
            assert result is None
    
    def test_case_insensitive_matching(self, sample_existing_issues):
        """Test that matching is case-insensitive."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import _match_existing_key
            result = _match_existing_key("VALID LOGIN TEST CASE", sample_existing_issues)
            
            assert result == "TEST-100"
    
    def test_returns_best_match(self):
        """Test that best matching issue is returned."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            existing = [
                {"key": "TEST-1", "summary": "Login Test"},
                {"key": "TEST-2", "summary": "Valid Login Test Case Full"},
                {"key": "TEST-3", "summary": "Logout Test"}
            ]
            
            from userstory2TestCasesAgent import _match_existing_key
            result = _match_existing_key("Valid Login Test Case", existing)
            
            assert result == "TEST-2"
    
    def test_handles_empty_existing_list(self):
        """Test handling of empty existing issues list."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import _match_existing_key
            result = _match_existing_key("Some Test", [])
            
            assert result is None
    
    def test_handles_whitespace_in_names(self, sample_existing_issues):
        """Test handling of extra whitespace in names."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import _match_existing_key
            result = _match_existing_key("  Valid Login Test Case  ", sample_existing_issues)
            
            assert result == "TEST-100"
    
    def test_threshold_boundary_below_50_percent(self):
        """Test that matches below 50% threshold return None."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            existing = [{"key": "TEST-1", "summary": "One Two Three Four Five"}]
            
            from userstory2TestCasesAgent import _match_existing_key
            result = _match_existing_key("One Six Seven Eight Nine Ten", existing)
            
            assert result is None
    
    def test_threshold_boundary_above_50_percent(self):
        """Test that matches well above 50% Jaccard threshold are included."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            # Jaccard = intersection/union = 4/6 = 0.67 > 0.5 threshold
            existing = [{"key": "TEST-1", "summary": "login test valid user"}]
            
            from userstory2TestCasesAgent import _match_existing_key
            result = _match_existing_key("login test valid credentials", existing)
            
            assert result == "TEST-1"


class TestDiffAndMergeTestCases:
    """Tests for diff_and_merge_test_cases() function."""
    
    def test_parses_llm_response_successfully(self, sample_test_cases_json, sample_existing_issues, sample_brownfield_diff_response):
        """Test successful parsing of LLM diff response."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = json.dumps(sample_brownfield_diff_response)
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import diff_and_merge_test_cases
            result = diff_and_merge_test_cases(sample_test_cases_json, sample_existing_issues, "Functional")
            
            assert "updated_test_cases" in result
            assert "summary" in result
    
    def test_extracts_json_from_code_block(self, sample_test_cases_json, sample_existing_issues, sample_brownfield_diff_response):
        """Test extraction of JSON from markdown code block."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = f"```json\n{json.dumps(sample_brownfield_diff_response)}\n```"
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import diff_and_merge_test_cases
            result = diff_and_merge_test_cases(sample_test_cases_json, sample_existing_issues, "Functional")
            
            assert "updated_test_cases" in result
    
    def test_falls_back_to_name_matching_on_json_error(self, sample_test_cases_json, sample_existing_issues):
        """Test fallback to name-based matching when JSON parsing fails."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = "Invalid JSON response"
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import diff_and_merge_test_cases
            result = diff_and_merge_test_cases(sample_test_cases_json, sample_existing_issues, "Functional")
            
            assert "updated_test_cases" in result
            assert len(result["updated_test_cases"]) == len(sample_test_cases_json)
    
    def test_raises_error_on_empty_response(self, sample_test_cases_json, sample_existing_issues):
        """Test that empty LLM response raises ValueError or RuntimeError."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = ""
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import diff_and_merge_test_cases
            
            with pytest.raises((ValueError, RuntimeError)):
                diff_and_merge_test_cases(sample_test_cases_json, sample_existing_issues, "Functional")
    
    def test_identifies_updated_vs_new_cases(self, sample_test_cases_json, sample_existing_issues, sample_brownfield_diff_response):
        """Test that updated and new cases are correctly identified."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = json.dumps(sample_brownfield_diff_response)
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import diff_and_merge_test_cases
            result = diff_and_merge_test_cases(sample_test_cases_json, sample_existing_issues, "Functional")
            
            updated = [tc for tc in result["updated_test_cases"] if tc.get("existing_key")]
            new = [tc for tc in result["updated_test_cases"] if not tc.get("existing_key")]
            
            assert len(updated) >= 1
            assert len(new) >= 1
    
    def test_uses_low_temperature(self, sample_test_cases_json, sample_existing_issues, sample_brownfield_diff_response):
        """Test that low temperature is used for deterministic output."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = json.dumps(sample_brownfield_diff_response)
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import diff_and_merge_test_cases
            diff_and_merge_test_cases(sample_test_cases_json, sample_existing_issues, "Functional")
            
            call_kwargs = mock_model.generate_content.call_args[1]
            assert call_kwargs["generation_config"]["temperature"] == 0.1


class TestProcessBrownfieldStoryJira:
    """Tests for process_brownfield_story_jira() function."""
    
    def test_falls_back_to_greenfield_when_no_existing_tests(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test fallback to greenfield when no existing test cases."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.fetch_existing_test_cases_by_label') as mock_fetch, \
             patch('userstory2TestCasesAgent.process_single_story_jira') as mock_greenfield:
            
            mock_fetch.return_value = []
            mock_greenfield.return_value = {"scenario_type": "Functional", "created_tests": []}
            
            from userstory2TestCasesAgent import process_brownfield_story_jira
            result = process_brownfield_story_jira("STORY-001", sample_user_story, "Functional")
            
            mock_greenfield.assert_called_once()
    
    def test_fetches_existing_test_cases(self, sample_user_story, sample_existing_issues, sample_test_scenarios_response, sample_test_cases_json_string, sample_brownfield_diff_response):
        """Test that existing test cases are fetched."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.fetch_existing_test_cases_by_label') as mock_fetch, \
             patch('userstory2TestCasesAgent.get_xray_token') as mock_token, \
             patch('userstory2TestCasesAgent.fetch_test_steps_graphql') as mock_steps, \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen, \
             patch('userstory2TestCasesAgent.diff_and_merge_test_cases') as mock_diff, \
             patch('userstory2TestCasesAgent.update_jira_test_issue'), \
             patch('userstory2TestCasesAgent.delete_all_test_steps_graphql'), \
             patch('userstory2TestCasesAgent.add_test_steps_graphql'), \
             patch('userstory2TestCasesAgent.create_tests_in_jira_cloud') as mock_create, \
             patch('userstory2TestCasesAgent.get_issue_id_from_key') as mock_id, \
             patch('userstory2TestCasesAgent.link_tests_to_plan_graphql'):
            
            mock_fetch.return_value = sample_existing_issues
            mock_token.return_value = "test-token"
            mock_steps.return_value = []
            mock_gen.return_value = {"Test Scenarios": sample_test_scenarios_response, "Test Cases": sample_test_cases_json_string}
            mock_diff.return_value = sample_brownfield_diff_response
            mock_create.return_value = ["TEST-200"]
            mock_id.return_value = "10200"
            
            from userstory2TestCasesAgent import process_brownfield_story_jira
            result = process_brownfield_story_jira("STORY-001", sample_user_story, "Functional")
            
            mock_fetch.assert_called_once()
    
    def test_raises_error_on_token_failure(self, sample_user_story, sample_existing_issues):
        """Test that RuntimeError is raised when token fetch fails."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.fetch_existing_test_cases_by_label') as mock_fetch, \
             patch('userstory2TestCasesAgent.get_xray_token') as mock_token:
            
            mock_fetch.return_value = sample_existing_issues
            mock_token.return_value = None
            
            from userstory2TestCasesAgent import process_brownfield_story_jira
            
            with pytest.raises(RuntimeError, match="Failed to obtain Xray authentication token"):
                process_brownfield_story_jira("STORY-001", sample_user_story, "Functional")
    
    def test_raises_error_on_generation_failure(self, sample_user_story, sample_existing_issues):
        """Test that RuntimeError is raised when test case generation fails."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.fetch_existing_test_cases_by_label') as mock_fetch, \
             patch('userstory2TestCasesAgent.get_xray_token') as mock_token, \
             patch('userstory2TestCasesAgent.fetch_test_steps_graphql') as mock_steps, \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen:
            
            mock_fetch.return_value = sample_existing_issues
            mock_token.return_value = "test-token"
            mock_steps.return_value = []
            mock_gen.return_value = {"error": "Generation failed"}
            
            from userstory2TestCasesAgent import process_brownfield_story_jira
            
            with pytest.raises(RuntimeError, match="Test case generation failed"):
                process_brownfield_story_jira("STORY-001", sample_user_story, "Functional")
    
    def test_returns_correct_result_structure(self, sample_user_story, sample_existing_issues, sample_test_scenarios_response, sample_test_cases_json_string, sample_brownfield_diff_response):
        """Test that result has correct structure."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.fetch_existing_test_cases_by_label') as mock_fetch, \
             patch('userstory2TestCasesAgent.get_xray_token') as mock_token, \
             patch('userstory2TestCasesAgent.fetch_test_steps_graphql') as mock_steps, \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen, \
             patch('userstory2TestCasesAgent.diff_and_merge_test_cases') as mock_diff, \
             patch('userstory2TestCasesAgent.update_jira_test_issue'), \
             patch('userstory2TestCasesAgent.delete_all_test_steps_graphql'), \
             patch('userstory2TestCasesAgent.add_test_steps_graphql'), \
             patch('userstory2TestCasesAgent.create_tests_in_jira_cloud') as mock_create, \
             patch('userstory2TestCasesAgent.get_issue_id_from_key') as mock_id, \
             patch('userstory2TestCasesAgent.link_tests_to_plan_graphql'):
            
            mock_fetch.return_value = sample_existing_issues
            mock_token.return_value = "test-token"
            mock_steps.return_value = []
            mock_gen.return_value = {"Test Scenarios": sample_test_scenarios_response, "Test Cases": sample_test_cases_json_string}
            mock_diff.return_value = sample_brownfield_diff_response
            mock_create.return_value = ["TEST-200"]
            mock_id.return_value = "10200"
            
            from userstory2TestCasesAgent import process_brownfield_story_jira
            result = process_brownfield_story_jira("STORY-001", sample_user_story, "Functional")
            
            assert "scenario_type" in result
            assert "llm_summary" in result
            assert "total_existing_fetched" in result
            assert "total_updated" in result
            assert "total_created" in result
            assert "updated_test_cases" in result
            assert "created_test_cases" in result
            assert "jira_push_result" in result
    
    def test_updates_existing_test_cases(self, sample_user_story, sample_existing_issues, sample_test_scenarios_response, sample_test_cases_json_string, sample_brownfield_diff_response):
        """Test that existing test cases are updated."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.fetch_existing_test_cases_by_label') as mock_fetch, \
             patch('userstory2TestCasesAgent.get_xray_token') as mock_token, \
             patch('userstory2TestCasesAgent.fetch_test_steps_graphql') as mock_steps, \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen, \
             patch('userstory2TestCasesAgent.diff_and_merge_test_cases') as mock_diff, \
             patch('userstory2TestCasesAgent.update_jira_test_issue') as mock_update, \
             patch('userstory2TestCasesAgent.delete_all_test_steps_graphql'), \
             patch('userstory2TestCasesAgent.add_test_steps_graphql'), \
             patch('userstory2TestCasesAgent.create_tests_in_jira_cloud') as mock_create, \
             patch('userstory2TestCasesAgent.get_issue_id_from_key') as mock_id, \
             patch('userstory2TestCasesAgent.link_tests_to_plan_graphql'):
            
            mock_fetch.return_value = sample_existing_issues
            mock_token.return_value = "test-token"
            mock_steps.return_value = []
            mock_gen.return_value = {"Test Scenarios": sample_test_scenarios_response, "Test Cases": sample_test_cases_json_string}
            mock_diff.return_value = sample_brownfield_diff_response
            mock_create.return_value = ["TEST-200"]
            mock_id.return_value = "10200"
            
            from userstory2TestCasesAgent import process_brownfield_story_jira
            process_brownfield_story_jira("STORY-001", sample_user_story, "Functional")
            
            mock_update.assert_called()
    
    def test_creates_new_test_cases(self, sample_user_story, sample_existing_issues, sample_test_scenarios_response, sample_test_cases_json_string, sample_brownfield_diff_response):
        """Test that new test cases are created."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.fetch_existing_test_cases_by_label') as mock_fetch, \
             patch('userstory2TestCasesAgent.get_xray_token') as mock_token, \
             patch('userstory2TestCasesAgent.fetch_test_steps_graphql') as mock_steps, \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen, \
             patch('userstory2TestCasesAgent.diff_and_merge_test_cases') as mock_diff, \
             patch('userstory2TestCasesAgent.update_jira_test_issue'), \
             patch('userstory2TestCasesAgent.delete_all_test_steps_graphql'), \
             patch('userstory2TestCasesAgent.add_test_steps_graphql'), \
             patch('userstory2TestCasesAgent.create_tests_in_jira_cloud') as mock_create, \
             patch('userstory2TestCasesAgent.get_issue_id_from_key') as mock_id, \
             patch('userstory2TestCasesAgent.link_tests_to_plan_graphql'):
            
            mock_fetch.return_value = sample_existing_issues
            mock_token.return_value = "test-token"
            mock_steps.return_value = []
            mock_gen.return_value = {"Test Scenarios": sample_test_scenarios_response, "Test Cases": sample_test_cases_json_string}
            mock_diff.return_value = sample_brownfield_diff_response
            mock_create.return_value = ["TEST-200"]
            mock_id.return_value = "10200"
            
            from userstory2TestCasesAgent import process_brownfield_story_jira
            process_brownfield_story_jira("STORY-001", sample_user_story, "Functional")
            
            mock_create.assert_called()
