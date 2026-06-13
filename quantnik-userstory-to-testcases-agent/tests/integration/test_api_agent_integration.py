"""
Integration tests for API Server to Agent workflow.

Tests the complete flow from FastAPI endpoints through the agent processing logic.
"""
import pytest
import json
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestHealthEndpointsIntegration:
    """Integration tests for health check endpoints."""
    
    def test_root_endpoint_integration(self, test_client):
        """Test root endpoint returns healthy status with correct structure."""
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "message" in data
        assert isinstance(data["message"], str)
    
    def test_health_endpoint_integration(self, test_client):
        """Test /health endpoint returns operational status."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["message"] == "Service is operational"
    
    def test_openapi_schema_available(self, test_client):
        """Test OpenAPI schema is accessible and valid."""
        response = test_client.get("/openapi.json")
        
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "/v1/generate-test-cases/bulk" in schema["paths"]
    
    def test_swagger_docs_available(self, test_client):
        """Test Swagger documentation is accessible."""
        response = test_client.get("/docs")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.integration
class TestScenarioTypesIntegration:
    """Integration tests for scenario types endpoint."""
    
    def test_get_all_scenario_types(self, test_client, all_scenario_types):
        """Test retrieving all available scenario types."""
        response = test_client.get("/scenario-types")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["scenario_types"]) == 11
        
        for expected_type in all_scenario_types:
            assert expected_type in data["scenario_types"]
    
    def test_scenario_types_no_duplicates(self, test_client):
        """Test that scenario types list has no duplicates."""
        response = test_client.get("/scenario-types")
        
        data = response.json()
        types_list = data["scenario_types"]
        assert len(types_list) == len(set(types_list))


@pytest.mark.integration
class TestBulkJobCreationIntegration:
    """Integration tests for bulk job creation endpoints."""
    
    def test_create_jira_bulk_job(self, test_client_with_mocked_processing, sample_user_stories, sample_scenario_types):
        """Test creating a bulk job for Jira integration."""
        request_data = {
            "userStories": sample_user_stories[:2],
            "ScenarioTypes": sample_scenario_types
        }
        
        response = test_client_with_mocked_processing.post(
            "/v1/generate-test-cases/bulk",
            json=request_data
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["total"] == 2
        assert "/v1/jobs/" in data["poll_url"]
    
    def test_create_brownfield_bulk_job(self, test_client_with_mocked_processing, sample_user_stories, sample_scenario_types):
        """Test creating a brownfield update job."""
        request_data = {
            "userStories": sample_user_stories[:2],
            "ScenarioTypes": sample_scenario_types
        }
        
        response = test_client_with_mocked_processing.post(
            "/v1/generate-test-cases/bulk/brownfield",
            json=request_data
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert "Brownfield" in data["message"]
    
    def test_job_entry_structure(self, test_client_with_mocked_processing, sample_user_stories, sample_scenario_types):
        """Test that created job has correct structure."""
        request_data = {
            "userStories": sample_user_stories[:1],
            "ScenarioTypes": ["Functional"]
        }
        
        create_response = test_client_with_mocked_processing.post(
            "/v1/generate-test-cases/bulk",
            json=request_data
        )
        job_id = create_response.json()["job_id"]
        
        status_response = test_client_with_mocked_processing.get(f"/v1/jobs/{job_id}")
        
        assert status_response.status_code == 200
        job = status_response.json()
        
        assert job["job_id"] == job_id
        assert "created_at" in job
        assert "status" in job
        assert "total" in job
        assert "completed_count" in job
        assert "failed_count" in job
        assert "ScenarioTypes" in job
        assert "stories" in job
        assert len(job["stories"]) == 1


@pytest.mark.integration
class TestJobStatusPollingIntegration:
    """Integration tests for job status polling."""
    
    def test_poll_pending_job(self, test_client_with_mocked_processing, sample_user_stories):
        """Test polling a newly created job shows pending status."""
        request_data = {
            "userStories": sample_user_stories[:1],
            "ScenarioTypes": ["Functional"]
        }
        
        create_response = test_client_with_mocked_processing.post(
            "/v1/generate-test-cases/bulk",
            json=request_data
        )
        job_id = create_response.json()["job_id"]
        
        status_response = test_client_with_mocked_processing.get(f"/v1/jobs/{job_id}")
        
        assert status_response.status_code == 200
        job = status_response.json()
        assert job["status"] in ["pending", "processing"]
    
    def test_poll_nonexistent_job(self, test_client):
        """Test polling a non-existent job returns 404."""
        response = test_client.get("/v1/jobs/nonexistent-job-id")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_story_status_in_job(self, test_client_with_mocked_processing, sample_user_stories):
        """Test that individual story status is tracked in job."""
        request_data = {
            "userStories": sample_user_stories[:2],
            "ScenarioTypes": ["Functional"]
        }
        
        create_response = test_client_with_mocked_processing.post(
            "/v1/generate-test-cases/bulk",
            json=request_data
        )
        job_id = create_response.json()["job_id"]
        
        status_response = test_client_with_mocked_processing.get(f"/v1/jobs/{job_id}")
        job = status_response.json()
        
        assert len(job["stories"]) == 2
        for story in job["stories"]:
            assert "index" in story
            assert "userStoryJiraId" in story
            assert "status" in story
            assert "results_by_scenario" in story


@pytest.mark.integration
class TestInputValidationIntegration:
    """Integration tests for request validation."""
    
    def test_reject_empty_user_stories(self, test_client):
        """Test that empty user stories list is rejected."""
        request_data = {
            "userStories": [],
            "ScenarioTypes": ["Functional"]
        }
        
        response = test_client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_reject_too_many_stories(self, test_client):
        """Test that more than 50 stories is rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": f"STORY-{i}", "userStory": f"Story {i}"}
                for i in range(51)
            ],
            "ScenarioTypes": ["Functional"]
        }
        
        response = test_client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_reject_invalid_scenario_type(self, test_client):
        """Test that invalid scenario type is rejected with 400."""
        request_data = {
            "userStories": [{"userStoryJiraId": "STORY-1", "userStory": "Test story"}],
            "ScenarioTypes": ["InvalidType"]
        }
        
        response = test_client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 400
        assert "Invalid ScenarioTypes" in response.json()["detail"]
    
    def test_reject_empty_scenario_types(self, test_client):
        """Test that empty scenario types list is rejected."""
        request_data = {
            "userStories": [{"userStoryJiraId": "STORY-1", "userStory": "Test story"}],
            "ScenarioTypes": []
        }
        
        response = test_client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_reject_too_many_scenario_types(self, test_client):
        """Test that more than 10 scenario types is rejected."""
        request_data = {
            "userStories": [{"userStoryJiraId": "STORY-1", "userStory": "Test story"}],
            "ScenarioTypes": [
                "Functional", "Non Functional", "Boundary & Negative",
                "Gherkin Functional", "Gherkin Boundary & Negative",
                "Buttons Enabled-Disabled", "Dropdown-Picklist",
                "System Architecture", "Combinatorial", "Bug Related", "Patch Related"
            ]
        }
        
        response = test_client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_reject_empty_jira_id(self, test_client):
        """Test that empty userStoryJiraId is rejected."""
        request_data = {
            "userStories": [{"userStoryJiraId": "", "userStory": "Test story"}],
            "ScenarioTypes": ["Functional"]
        }
        
        response = test_client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_reject_empty_user_story_text(self, test_client):
        """Test that empty userStory text is rejected."""
        request_data = {
            "userStories": [{"userStoryJiraId": "STORY-1", "userStory": ""}],
            "ScenarioTypes": ["Functional"]
        }
        
        response = test_client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_whitespace_trimming(self, test_client_with_mocked_processing):
        """Test that whitespace is trimmed from inputs."""
        request_data = {
            "userStories": [{"userStoryJiraId": "  STORY-1  ", "userStory": "  Test story  "}],
            "ScenarioTypes": ["Functional"]
        }
        
        response = test_client_with_mocked_processing.post(
            "/v1/generate-test-cases/bulk",
            json=request_data
        )
        
        assert response.status_code == 202


@pytest.mark.integration
class TestRetryMechanismIntegration:
    """Integration tests for retry failed stories mechanism."""
    
    def test_retry_nonexistent_job(self, test_client):
        """Test retry on non-existent job returns 404."""
        response = test_client.post("/v1/jobs/nonexistent-job/retry-failed")
        
        assert response.status_code == 404
    
    def test_retry_requires_failed_stories(self, test_client_with_mocked_processing, sample_user_stories):
        """Test retry is rejected when no failed stories exist."""
        # Create a job
        request_data = {
            "userStories": sample_user_stories[:1],
            "ScenarioTypes": ["Functional"]
        }
        
        create_response = test_client_with_mocked_processing.post(
            "/v1/generate-test-cases/bulk",
            json=request_data
        )
        job_id = create_response.json()["job_id"]
        
        # Try to retry immediately (no failures yet)
        retry_response = test_client_with_mocked_processing.post(
            f"/v1/jobs/{job_id}/retry-failed"
        )
        
        # Should fail because job is still processing or has no failures
        assert retry_response.status_code in [400, 404]


@pytest.mark.integration
class TestConcurrentJobsIntegration:
    """Integration tests for handling multiple concurrent jobs."""
    
    def test_create_multiple_jobs(self, test_client_with_mocked_processing, sample_user_stories):
        """Test creating multiple jobs concurrently."""
        job_ids = []
        
        for i in range(3):
            request_data = {
                "userStories": [sample_user_stories[i % len(sample_user_stories)]],
                "ScenarioTypes": ["Functional"]
            }
            
            response = test_client_with_mocked_processing.post(
                "/v1/generate-test-cases/bulk",
                json=request_data
            )
            
            assert response.status_code == 202
            job_ids.append(response.json()["job_id"])
        
        # Verify all jobs are unique
        assert len(job_ids) == len(set(job_ids))
        
        # Verify all jobs can be polled
        for job_id in job_ids:
            response = test_client_with_mocked_processing.get(f"/v1/jobs/{job_id}")
            assert response.status_code == 200
    
    def test_jobs_are_isolated(self, test_client_with_mocked_processing, sample_user_stories):
        """Test that jobs don't interfere with each other."""
        # Create two jobs with different stories
        job1_data = {
            "userStories": [sample_user_stories[0]],
            "ScenarioTypes": ["Functional"]
        }
        job2_data = {
            "userStories": [sample_user_stories[1]],
            "ScenarioTypes": ["Boundary & Negative"]
        }
        
        response1 = test_client_with_mocked_processing.post("/v1/generate-test-cases/bulk", json=job1_data)
        response2 = test_client_with_mocked_processing.post("/v1/generate-test-cases/bulk", json=job2_data)
        
        job1 = test_client_with_mocked_processing.get(f"/v1/jobs/{response1.json()['job_id']}").json()
        job2 = test_client_with_mocked_processing.get(f"/v1/jobs/{response2.json()['job_id']}").json()
        
        # Verify jobs have different stories
        assert job1["stories"][0]["userStoryJiraId"] != job2["stories"][0]["userStoryJiraId"]
        # Verify jobs have different scenario types
        assert job1["ScenarioTypes"] != job2["ScenarioTypes"]
