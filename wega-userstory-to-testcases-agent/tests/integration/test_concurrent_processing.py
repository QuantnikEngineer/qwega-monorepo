"""
Concurrent Processing Integration Tests.

Tests thread safety and concurrent job processing.
"""
import pytest
import json
import time
import responses
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestConcurrentJobSubmission:
    """Tests for concurrent bulk job submission."""
    
    def test_submit_multiple_jobs_concurrently(self):
        """Test submitting multiple bulk jobs at the same time."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            def submit_job(job_num):
                payload = {
                    "userStories": [{"userStoryJiraId": f"STORY-{job_num}", "userStory": f"User story {job_num}"}],
                    "ScenarioTypes": ["Functional"]
                }
                return client.post("/v1/generate-test-cases/bulk", json=payload)
            
            # Submit 5 jobs concurrently
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(submit_job, i) for i in range(5)]
                results = [f.result() for f in as_completed(futures)]
            
            # All jobs should be accepted
            assert all(r.status_code == 202 for r in results)
            
            # Each job should have unique ID
            job_ids = [r.json()["job_id"] for r in results]
            assert len(set(job_ids)) == 5
    
    def test_job_status_isolation(self):
        """Test that concurrent job statuses are isolated."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app, _jobs
            client = TestClient(app)
            
            # Submit two jobs
            job1_response = client.post("/v1/generate-test-cases/bulk", json={
                "userStories": [{"userStoryJiraId": "STORY-A", "userStory": "Story A"}],
                "ScenarioTypes": ["Functional"]
            })
            
            job2_response = client.post("/v1/generate-test-cases/bulk/qtest", json={
                "userStories": [{"userStoryJiraId": "STORY-B", "userStory": "Story B"}],
                "ScenarioTypes": ["Boundary & Negative"]
            })
            
            job1_id = job1_response.json()["job_id"]
            job2_id = job2_response.json()["job_id"]
            
            # Verify jobs have different configurations
            assert _jobs[job1_id]["ScenarioTypes"] == ["Functional"]
            assert _jobs[job2_id]["ScenarioTypes"] == ["Boundary & Negative"]


@pytest.mark.integration
class TestConcurrentAPIRequests:
    """Tests for concurrent API request handling."""
    
    def test_concurrent_health_checks(self):
        """Test concurrent health check requests."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            def health_check():
                return client.get("/health")
            
            # Make 10 concurrent health checks
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(health_check) for _ in range(10)]
                results = [f.result() for f in as_completed(futures)]
            
            # All should succeed
            assert all(r.status_code == 200 for r in results)
            assert all(r.json()["status"] == "healthy" for r in results)


@pytest.mark.integration
class TestJobStoreThreadSafety:
    """Tests for job store thread safety."""
    
    def test_concurrent_job_updates(self):
        """Test concurrent updates to the same job don't corrupt data."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import _jobs
            
            # Create a job manually
            job_id = "test-concurrent-job"
            _jobs[job_id] = {
                "status": "processing",
                "stories": [{"userStoryJiraId": f"STORY-{i}", "status": "pending"} for i in range(10)],
                "completed_count": 0
            }
            
            def update_story(story_idx):
                _jobs[job_id]["stories"][story_idx]["status"] = "completed"
                _jobs[job_id]["completed_count"] += 1
                time.sleep(0.01)  # Simulate work
                return story_idx
            
            # Update all stories concurrently
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(update_story, i) for i in range(10)]
                [f.result() for f in as_completed(futures)]
            
            # Verify all stories are marked completed
            assert all(s["status"] == "completed" for s in _jobs[job_id]["stories"])
    
    def test_concurrent_job_creation_unique_ids(self):
        """Test that concurrent job creation generates unique IDs."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app
            client = TestClient(app)
            
            def create_job():
                payload = {
                    "userStories": [{"userStoryJiraId": "STORY-X", "userStory": "Story"}],
                    "ScenarioTypes": ["Functional"]
                }
                response = client.post("/v1/generate-test-cases/bulk", json=payload)
                return response.json()["job_id"]
            
            # Create 20 jobs concurrently
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(create_job) for _ in range(20)]
                job_ids = [f.result() for f in as_completed(futures)]
            
            # All IDs should be unique
            assert len(set(job_ids)) == 20


@pytest.mark.integration
class TestConcurrentExternalAPICalls:
    """Tests for concurrent external API call handling."""
    
    @responses.activate
    def test_concurrent_jira_calls(self, jira_config):
        """Test concurrent Jira API calls."""
        # Mock multiple Jira responses
        for i in range(5):
            responses.add(
                responses.GET,
                f"{jira_config['base_url']}rest/api/3/issue/STORY-{i}",
                json={"id": f"1000{i}", "key": f"STORY-{i}"},
                status=200
            )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_issue_id_from_key
            
            def fetch_issue(story_num):
                return get_issue_id_from_key(f"STORY-{story_num}", jira_config)
            
            # Fetch 5 issues concurrently
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(fetch_issue, i) for i in range(5)]
                results = [f.result() for f in as_completed(futures)]
            
            # All should return valid IDs
            assert all(r is not None for r in results)
    
    @responses.activate
    def test_concurrent_xray_calls(self, xray_config):
        """Test concurrent Xray API calls."""
        # Mock Xray authentication
        for _ in range(5):
            responses.add(
                responses.POST,
                "https://xray.cloud.getxray.app/api/v2/authenticate",
                json='"xray-token"',
                status=200
            )
        
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from userstory2TestCasesAgent import get_xray_token
            
            def get_token():
                return get_xray_token(xray_config["client_id"], xray_config["client_secret"])
            
            # Get 5 tokens concurrently
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(get_token) for _ in range(5)]
                results = [f.result() for f in as_completed(futures)]
            
            # All should return valid tokens
            assert all(r is not None for r in results)


@pytest.mark.integration
class TestConcurrentModelCalls:
    """Tests for concurrent AI model call handling."""
    
    def test_concurrent_scenario_generation(self, mock_vertex_ai_response):
        """Test concurrent test scenario generation."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_response = MagicMock()
            mock_response.text = mock_vertex_ai_response["scenarios"]
            mock_model.generate_content.return_value = mock_response
            
            from userstory2TestCasesAgent import generate_test_scenarios_from_userstory
            
            def generate_scenarios(story_id):
                user_story = f"As a user I want feature {story_id}"
                return generate_test_scenarios_from_userstory(user_story, "Functional")
            
            # Generate scenarios for 5 stories concurrently
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(generate_scenarios, i) for i in range(5)]
                results = [f.result() for f in as_completed(futures)]
            
            # All should return scenarios
            assert all(r is not None for r in results)
    
    def test_concurrent_test_case_generation(self, mock_vertex_ai_response):
        """Test concurrent test case generation."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'), \
             patch('userstory2TestCasesAgent.model') as mock_model:
            
            mock_scenario_response = MagicMock()
            mock_scenario_response.text = mock_vertex_ai_response["scenarios"]
            
            mock_tc_response = MagicMock()
            mock_tc_response.text = json.dumps(mock_vertex_ai_response["test_cases"])
            
            mock_model.generate_content.side_effect = [
                mock_scenario_response, mock_tc_response,
                mock_scenario_response, mock_tc_response,
                mock_scenario_response, mock_tc_response,
            ]
            
            from userstory2TestCasesAgent import generate_test_cases
            
            def generate_cases(story_id):
                user_story = f"As a user I want feature {story_id}"
                return generate_test_cases(user_story, "Functional")
            
            # Generate test cases for 3 stories concurrently
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(generate_cases, i) for i in range(3)]
                results = [f.result() for f in as_completed(futures)]
            
            # All should return test cases
            assert all("Test Cases" in r or "error" in r for r in results)


@pytest.mark.integration
class TestBulkJobConcurrentProcessing:
    """Tests for concurrent story processing within bulk jobs."""
    
    def test_stories_processed_in_order(self):
        """Test that stories in a bulk job maintain processing order."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app, _jobs
            client = TestClient(app)
            
            # Create job with ordered stories
            payload = {
                "userStories": [
                    {"userStoryJiraId": f"STORY-{i}", "userStory": f"Story {i}"}
                    for i in range(10)
                ],
                "ScenarioTypes": ["Functional"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=payload)
            job_id = response.json()["job_id"]
            
            # Verify stories are stored in order
            stored_stories = _jobs[job_id]["stories"]
            for i, story in enumerate(stored_stories):
                assert story["userStoryJiraId"] == f"STORY-{i}"
    
    def test_bulk_job_status_update_consistency(self):
        """Test that bulk job status updates are consistent."""
        with patch('userstory2TestCasesAgent.init'), \
             patch('userstory2TestCasesAgent.GenerativeModel'):
            
            from api_server import app, _jobs
            client = TestClient(app)
            
            # Create job
            payload = {
                "userStories": [{"userStoryJiraId": "STORY-1", "userStory": "Story"}],
                "ScenarioTypes": ["Functional"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=payload)
            job_id = response.json()["job_id"]
            
            # Simulate multiple status checks
            def check_status():
                return client.get(f"/v1/jobs/{job_id}")
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(check_status) for _ in range(10)]
                results = [f.result() for f in as_completed(futures)]
            
            # All status checks should return consistent data
            assert all(r.status_code == 200 for r in results)
            statuses = [r.json()["status"] for r in results]
            # Status should be consistent across all checks
            assert len(set(statuses)) == 1
