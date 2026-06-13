"""
Unit tests for bulk job processing functions in userstory2TestCasesAgent.py

Tests cover:
- update_story_status()
- run_bulk_job_jira()
- run_bulk_job_qtest()
- run_bulk_brownfield_job_jira()
- _finalise_job()
"""
import pytest
from unittest.mock import MagicMock, patch
import threading
import json


class TestUpdateStoryStatus:
    """Tests for update_story_status() function."""
    
    def test_sets_pending_when_no_scenarios_started(self, job_store, jobs_lock, sample_job_entry):
        """Test that status is 'pending' when no scenarios have started."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            job_store["test-job"] = sample_job_entry.copy()
            job_store["test-job"]["stories"][0]["results_by_scenario"] = {}
            
            from userstory2TestCasesAgent import update_story_status
            update_story_status(job_store, jobs_lock, "test-job", 0, ["Functional", "Boundary & Negative"])
            
            assert job_store["test-job"]["stories"][0]["status"] == "pending"
    
    def test_sets_processing_when_some_scenarios_done(self, job_store, jobs_lock, sample_job_entry):
        """Test that status is 'processing' when some scenarios are done."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            job_store["test-job"] = sample_job_entry.copy()
            job_store["test-job"]["stories"][0]["results_by_scenario"] = {
                "Functional": {"status": "passed"},
            }
            
            from userstory2TestCasesAgent import update_story_status
            update_story_status(job_store, jobs_lock, "test-job", 0, ["Functional", "Boundary & Negative"])
            
            assert job_store["test-job"]["stories"][0]["status"] == "processing"
    
    def test_sets_passed_when_all_scenarios_succeed(self, job_store, jobs_lock, sample_job_entry):
        """Test that status is 'passed' when all scenarios succeed."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            job_store["test-job"] = sample_job_entry.copy()
            job_store["test-job"]["stories"][0]["results_by_scenario"] = {
                "Functional": {"status": "passed"},
                "Boundary & Negative": {"status": "passed"}
            }
            
            from userstory2TestCasesAgent import update_story_status
            update_story_status(job_store, jobs_lock, "test-job", 0, ["Functional", "Boundary & Negative"])
            
            assert job_store["test-job"]["stories"][0]["status"] == "passed"
    
    def test_sets_failed_when_all_scenarios_fail(self, job_store, jobs_lock, sample_job_entry):
        """Test that status is 'failed' when all scenarios fail."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            job_store["test-job"] = sample_job_entry.copy()
            job_store["test-job"]["stories"][0]["results_by_scenario"] = {
                "Functional": {"status": "failed"},
                "Boundary & Negative": {"status": "failed"}
            }
            
            from userstory2TestCasesAgent import update_story_status
            update_story_status(job_store, jobs_lock, "test-job", 0, ["Functional", "Boundary & Negative"])
            
            assert job_store["test-job"]["stories"][0]["status"] == "failed"
    
    def test_sets_partial_passed_when_mixed_results(self, job_store, jobs_lock, sample_job_entry):
        """Test that status is 'partial_passed' when some scenarios pass and some fail."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            job_store["test-job"] = sample_job_entry.copy()
            job_store["test-job"]["stories"][0]["results_by_scenario"] = {
                "Functional": {"status": "passed"},
                "Boundary & Negative": {"status": "failed"}
            }
            
            from userstory2TestCasesAgent import update_story_status
            update_story_status(job_store, jobs_lock, "test-job", 0, ["Functional", "Boundary & Negative"])
            
            assert job_store["test-job"]["stories"][0]["status"] == "partial_passed"


class TestFinaliseJob:
    """Tests for _finalise_job() function."""
    
    def test_sets_passed_when_all_stories_succeed(self, job_store, jobs_lock):
        """Test that job status is 'passed' when all stories succeed."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "processing",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"status": "passed", "results_by_scenario": {}},
                    {"status": "passed", "results_by_scenario": {}}
                ]
            }
            
            stories = [MagicMock(), MagicMock()]
            scenario_types = ["Functional"]
            
            from userstory2TestCasesAgent import _finalise_job
            _finalise_job("test-job", stories, scenario_types, job_store, jobs_lock)
            
            assert job_store["test-job"]["status"] == "passed"
            assert job_store["test-job"]["completed_count"] == 2
            assert job_store["test-job"]["failed_count"] == 0
    
    def test_sets_failed_when_all_stories_fail(self, job_store, jobs_lock):
        """Test that job status is 'failed' when all stories fail."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "processing",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"status": "failed", "results_by_scenario": {}},
                    {"status": "failed", "results_by_scenario": {}}
                ]
            }
            
            stories = [MagicMock(), MagicMock()]
            scenario_types = ["Functional"]
            
            from userstory2TestCasesAgent import _finalise_job
            _finalise_job("test-job", stories, scenario_types, job_store, jobs_lock)
            
            assert job_store["test-job"]["status"] == "failed"
            assert job_store["test-job"]["failed_count"] == 2
    
    def test_sets_partial_passed_when_mixed_results(self, job_store, jobs_lock):
        """Test that job status is 'partial_passed' when some stories pass and some fail."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "processing",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"status": "passed", "results_by_scenario": {}},
                    {"status": "failed", "results_by_scenario": {}}
                ]
            }
            
            stories = [MagicMock(), MagicMock()]
            scenario_types = ["Functional"]
            
            from userstory2TestCasesAgent import _finalise_job
            _finalise_job("test-job", stories, scenario_types, job_store, jobs_lock)
            
            assert job_store["test-job"]["status"] == "partial_passed"
    
    def test_sets_completed_at_timestamp(self, job_store, jobs_lock):
        """Test that completed_at timestamp is set."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "processing",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [{"status": "passed", "results_by_scenario": {}}]
            }
            
            stories = [MagicMock()]
            scenario_types = ["Functional"]
            
            from userstory2TestCasesAgent import _finalise_job
            _finalise_job("test-job", stories, scenario_types, job_store, jobs_lock)
            
            assert job_store["test-job"]["completed_at"] is not None
            assert job_store["test-job"]["completed_at"].endswith("Z")


class TestRunBulkJobJira:
    """Tests for run_bulk_job_jira() function."""
    
    def test_processes_all_story_scenario_combinations(self, job_store, jobs_lock):
        """Test that all story × scenario combinations are processed."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.process_single_story_jira') as mock_process:
            
            mock_process.return_value = {"scenario_type": "Functional", "result": "success"}
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "pending",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}},
                    {"index": 1, "userStoryJiraId": "STORY-2", "status": "pending", "results_by_scenario": {}}
                ]
            }
            
            story1 = MagicMock()
            story1.userStoryJiraId = "STORY-1"
            story1.userStory = "User story 1"
            
            story2 = MagicMock()
            story2.userStoryJiraId = "STORY-2"
            story2.userStory = "User story 2"
            
            stories = [story1, story2]
            scenario_types = ["Functional", "Boundary & Negative"]
            
            from userstory2TestCasesAgent import run_bulk_job_jira
            run_bulk_job_jira("test-job", stories, scenario_types, job_store, jobs_lock)
            
            assert mock_process.call_count == 4
    
    def test_sets_job_status_to_processing(self, job_store, jobs_lock):
        """Test that job status is set to 'processing' at start."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.process_single_story_jira') as mock_process:
            
            mock_process.return_value = {"scenario_type": "Functional", "result": "success"}
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "pending",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}}
                ]
            }
            
            story = MagicMock()
            story.userStoryJiraId = "STORY-1"
            story.userStory = "User story 1"
            
            from userstory2TestCasesAgent import run_bulk_job_jira
            run_bulk_job_jira("test-job", [story], ["Functional"], job_store, jobs_lock)
    
    def test_handles_processing_failure(self, job_store, jobs_lock):
        """Test handling of processing failure for a story."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.process_single_story_jira') as mock_process:
            
            mock_process.side_effect = Exception("Processing failed")
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "pending",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}}
                ]
            }
            
            story = MagicMock()
            story.userStoryJiraId = "STORY-1"
            story.userStory = "User story 1"
            
            from userstory2TestCasesAgent import run_bulk_job_jira
            run_bulk_job_jira("test-job", [story], ["Functional"], job_store, jobs_lock)
            
            assert job_store["test-job"]["stories"][0]["results_by_scenario"]["Functional"]["status"] == "failed"
    
    def test_increments_completed_count_on_success(self, job_store, jobs_lock):
        """Test that completed_count is incremented on success."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.process_single_story_jira') as mock_process:
            
            mock_process.return_value = {"scenario_type": "Functional"}
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "pending",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}}
                ]
            }
            
            story = MagicMock()
            story.userStoryJiraId = "STORY-1"
            story.userStory = "User story 1"
            
            from userstory2TestCasesAgent import run_bulk_job_jira
            run_bulk_job_jira("test-job", [story], ["Functional"], job_store, jobs_lock)


class TestRunBulkJobQtest:
    """Tests for run_bulk_job_qtest() function."""
    
    def test_processes_all_story_scenario_combinations(self, job_store, jobs_lock):
        """Test that all story × scenario combinations are processed for qTest."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.process_single_story_qtest') as mock_process:
            
            mock_process.return_value = {"scenario_type": "Functional", "result": "success"}
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "pending",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}}
                ]
            }
            
            story = MagicMock()
            story.userStoryJiraId = "STORY-1"
            story.userStory = "User story 1"
            
            from userstory2TestCasesAgent import run_bulk_job_qtest
            run_bulk_job_qtest("test-job", [story], ["Functional"], job_store, jobs_lock)
            
            mock_process.assert_called_once()
    
    def test_handles_processing_failure(self, job_store, jobs_lock):
        """Test handling of processing failure for qTest."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.process_single_story_qtest') as mock_process:
            
            mock_process.side_effect = Exception("qTest processing failed")
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "pending",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}}
                ]
            }
            
            story = MagicMock()
            story.userStoryJiraId = "STORY-1"
            story.userStory = "User story 1"
            
            from userstory2TestCasesAgent import run_bulk_job_qtest
            run_bulk_job_qtest("test-job", [story], ["Functional"], job_store, jobs_lock)
            
            assert job_store["test-job"]["stories"][0]["results_by_scenario"]["Functional"]["status"] == "failed"


class TestRunBulkBrownfieldJobJira:
    """Tests for run_bulk_brownfield_job_jira() function."""
    
    def test_processes_brownfield_stories(self, job_store, jobs_lock):
        """Test that brownfield processing is called for each story."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.process_brownfield_story_jira') as mock_process:
            
            mock_process.return_value = {
                "scenario_type": "Functional",
                "total_updated": 1,
                "total_created": 1
            }
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "pending",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}}
                ]
            }
            
            story = MagicMock()
            story.userStoryJiraId = "STORY-1"
            story.userStory = "User story 1"
            
            from userstory2TestCasesAgent import run_bulk_brownfield_job_jira
            run_bulk_brownfield_job_jira("test-job", [story], ["Functional"], job_store, jobs_lock)
            
            mock_process.assert_called_once()
    
    def test_handles_brownfield_processing_failure(self, job_store, jobs_lock):
        """Test handling of brownfield processing failure."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.process_brownfield_story_jira') as mock_process:
            
            mock_process.side_effect = Exception("Brownfield processing failed")
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "pending",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}}
                ]
            }
            
            story = MagicMock()
            story.userStoryJiraId = "STORY-1"
            story.userStory = "User story 1"
            
            from userstory2TestCasesAgent import run_bulk_brownfield_job_jira
            run_bulk_brownfield_job_jira("test-job", [story], ["Functional"], job_store, jobs_lock)
            
            assert job_store["test-job"]["stories"][0]["results_by_scenario"]["Functional"]["status"] == "failed"
            assert "Brownfield processing failed" in job_store["test-job"]["stories"][0]["results_by_scenario"]["Functional"]["error"]
    
    def test_sets_job_status_to_processing(self, job_store, jobs_lock):
        """Test that job status is set to 'processing' at start."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.process_brownfield_story_jira') as mock_process:
            
            mock_process.return_value = {"scenario_type": "Functional"}
            
            job_store["test-job"] = {
                "job_id": "test-job",
                "status": "pending",
                "completed_count": 0,
                "failed_count": 0,
                "stories": [
                    {"index": 0, "userStoryJiraId": "STORY-1", "status": "pending", "results_by_scenario": {}}
                ]
            }
            
            story = MagicMock()
            story.userStoryJiraId = "STORY-1"
            story.userStory = "User story 1"
            
            from userstory2TestCasesAgent import run_bulk_brownfield_job_jira
            run_bulk_brownfield_job_jira("test-job", [story], ["Functional"], job_store, jobs_lock)


class TestProcessSingleStoryJira:
    """Tests for process_single_story_jira() function."""
    
    def test_generates_test_cases_and_pushes_to_jira(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test that test cases are generated and pushed to Jira."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen, \
             patch('userstory2TestCasesAgent.create_tests_in_jira_cloud') as mock_create, \
             patch('userstory2TestCasesAgent.get_xray_token') as mock_token, \
             patch('userstory2TestCasesAgent.get_issue_id_from_key') as mock_id, \
             patch('userstory2TestCasesAgent.add_test_steps_graphql'), \
             patch('userstory2TestCasesAgent.link_tests_to_plan_graphql'):
            
            mock_gen.return_value = {
                "Test Scenarios": sample_test_scenarios_response,
                "Test Cases": sample_test_cases_json_string
            }
            mock_create.return_value = ["TEST-100", "TEST-101"]
            mock_token.return_value = "test-token"
            mock_id.side_effect = ["10100", "10101", "plan-id"]
            
            from userstory2TestCasesAgent import process_single_story_jira
            result = process_single_story_jira("STORY-001", sample_user_story, "Functional")
            
            assert "scenario_type" in result
            assert "jira_push_result" in result
    
    def test_raises_error_on_generation_failure(self, sample_user_story):
        """Test that RuntimeError is raised when generation fails."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen:
            
            mock_gen.return_value = {"error": "Generation failed"}
            
            from userstory2TestCasesAgent import process_single_story_jira
            
            with pytest.raises(RuntimeError, match="Test case generation failed"):
                process_single_story_jira("STORY-001", sample_user_story, "Functional")
    
    def test_raises_error_when_no_tests_created(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test that RuntimeError is raised when no tests are created in Jira."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen, \
             patch('userstory2TestCasesAgent.create_tests_in_jira_cloud') as mock_create:
            
            mock_gen.return_value = {
                "Test Scenarios": sample_test_scenarios_response,
                "Test Cases": sample_test_cases_json_string
            }
            mock_create.return_value = []
            
            from userstory2TestCasesAgent import process_single_story_jira
            
            with pytest.raises(RuntimeError, match="Jira push failed"):
                process_single_story_jira("STORY-001", sample_user_story, "Functional")


class TestProcessSingleStoryQtest:
    """Tests for process_single_story_qtest() function."""
    
    def test_generates_test_cases_and_pushes_to_qtest(self, sample_user_story, sample_test_scenarios_response, sample_test_cases_json_string):
        """Test that test cases are generated and pushed to qTest."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen, \
             patch('userstory2TestCasesAgent.create_test_case_in_qtest') as mock_create, \
             patch('userstory2TestCasesAgent.add_test_steps_in_qtest'):
            
            mock_gen.return_value = {
                "Test Scenarios": sample_test_scenarios_response,
                "Test Cases": sample_test_cases_json_string
            }
            mock_create.return_value = {"success": True, "test_case_id": "tc-123"}
            
            from userstory2TestCasesAgent import process_single_story_qtest
            result = process_single_story_qtest(sample_user_story, "Functional")
            
            assert "scenario_type" in result
            assert "qtest_push_result" in result
    
    def test_raises_error_on_generation_failure(self, sample_user_story):
        """Test that RuntimeError is raised when generation fails."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.generate_test_cases') as mock_gen:
            
            mock_gen.return_value = {"error": "Generation failed"}
            
            from userstory2TestCasesAgent import process_single_story_qtest
            
            with pytest.raises(RuntimeError, match="Test case generation failed"):
                process_single_story_qtest(sample_user_story, "Functional")
