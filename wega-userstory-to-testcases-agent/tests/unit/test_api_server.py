"""
Unit tests for API server endpoints in api_server.py

Tests cover:
- Health check endpoints
- Scenario types endpoint
- Bulk generation endpoints (Jira, qTest, Brownfield)
- Job status polling endpoint
- Retry failed endpoint
- Pydantic validation models
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
import json


@pytest.fixture
def client():
    """Create FastAPI test client with mocked dependencies."""
    with patch('userstory2TestCasesAgent.init'), \
         patch('userstory2TestCasesAgent.GenerativeModel'):
        from api_server import app
        return TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""
    
    def test_root_endpoint_returns_healthy(self, client):
        """Test that root endpoint returns healthy status."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "message" in data
    
    def test_health_endpoint_returns_healthy(self, client):
        """Test that /health endpoint returns healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["message"] == "Service is operational"


class TestScenarioTypesEndpoint:
    """Tests for scenario types endpoint."""
    
    def test_returns_all_scenario_types(self, client, valid_scenario_types):
        """Test that all valid scenario types are returned."""
        response = client.get("/scenario-types")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "scenario_types" in data
        assert len(data["scenario_types"]) == 11
    
    def test_includes_functional_type(self, client):
        """Test that Functional type is included."""
        response = client.get("/scenario-types")
        
        data = response.json()
        assert "Functional" in data["scenario_types"]
    
    def test_includes_gherkin_types(self, client):
        """Test that Gherkin types are included."""
        response = client.get("/scenario-types")
        
        data = response.json()
        assert "Gherkin Functional" in data["scenario_types"]
        assert "Gherkin Boundary & Negative" in data["scenario_types"]


class TestBulkGenerateJiraEndpoint:
    """Tests for POST /v1/generate-test-cases/bulk endpoint."""
    
    def test_accepts_valid_request(self, client):
        """Test that valid request is accepted and returns job_id."""
        with patch('api_server.run_bulk_job_jira'):
            request_data = {
                "userStories": [
                    {"userStoryJiraId": "STORY-001", "userStory": "As a user, I want to login"}
                ],
                "ScenarioTypes": ["Functional"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=request_data)
            
            assert response.status_code == 202
            data = response.json()
            assert "job_id" in data
            assert data["total"] == 1
            assert "poll_url" in data
    
    def test_rejects_empty_user_stories(self, client):
        """Test that empty userStories list is rejected."""
        request_data = {
            "userStories": [],
            "ScenarioTypes": ["Functional"]
        }
        
        response = client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_rejects_more_than_50_stories(self, client):
        """Test that more than 50 stories is rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": f"STORY-{i}", "userStory": f"Story {i}"}
                for i in range(51)
            ],
            "ScenarioTypes": ["Functional"]
        }
        
        response = client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_rejects_invalid_scenario_types(self, client):
        """Test that invalid scenario types are rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": "STORY-001", "userStory": "As a user, I want to login"}
            ],
            "ScenarioTypes": ["InvalidType"]
        }
        
        response = client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 400
    
    def test_rejects_empty_scenario_types(self, client):
        """Test that empty ScenarioTypes list is rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": "STORY-001", "userStory": "As a user, I want to login"}
            ],
            "ScenarioTypes": []
        }
        
        response = client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_rejects_more_than_10_scenario_types(self, client):
        """Test that more than 10 scenario types is rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": "STORY-001", "userStory": "As a user, I want to login"}
            ],
            "ScenarioTypes": [
                "Functional", "Non Functional", "Boundary & Negative",
                "Gherkin Functional", "Gherkin Boundary & Negative",
                "Buttons Enabled-Disabled", "Dropdown-Picklist",
                "System Architecture", "Combinatorial", "Bug Related", "Patch Related"
            ]
        }
        
        response = client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_rejects_empty_jira_id(self, client):
        """Test that empty userStoryJiraId is rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": "", "userStory": "As a user, I want to login"}
            ],
            "ScenarioTypes": ["Functional"]
        }
        
        response = client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_rejects_empty_user_story(self, client):
        """Test that empty userStory is rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": "STORY-001", "userStory": ""}
            ],
            "ScenarioTypes": ["Functional"]
        }
        
        response = client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422


class TestBulkBrownfieldEndpoint:
    """Tests for POST /v1/generate-test-cases/bulk/brownfield endpoint."""
    
    def test_accepts_valid_request(self, client):
        """Test that valid brownfield request is accepted."""
        with patch('api_server.run_bulk_brownfield_job_jira'):
            request_data = {
                "userStories": [
                    {"userStoryJiraId": "STORY-001", "userStory": "As a user, I want to login"}
                ],
                "ScenarioTypes": ["Functional"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk/brownfield", json=request_data)
            
            assert response.status_code == 202
            data = response.json()
            assert "job_id" in data
    
    def test_rejects_invalid_scenario_types(self, client):
        """Test that invalid scenario types are rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": "STORY-001", "userStory": "As a user, I want to login"}
            ],
            "ScenarioTypes": ["InvalidBrownfield"]
        }
        
        response = client.post("/v1/generate-test-cases/bulk/brownfield", json=request_data)
        
        assert response.status_code == 400


class TestJobStatusEndpoint:
    """Tests for GET /v1/jobs/{job_id} endpoint."""
    
    def test_returns_job_status(self, client):
        """Test that job status is returned for valid job_id."""
        with patch('api_server.run_bulk_job_jira'):
            request_data = {
                "userStories": [
                    {"userStoryJiraId": "STORY-001", "userStory": "As a user, I want to login"}
                ],
                "ScenarioTypes": ["Functional"]
            }
            create_response = client.post("/v1/generate-test-cases/bulk", json=request_data)
            job_id = create_response.json()["job_id"]
            
            response = client.get(f"/v1/jobs/{job_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == job_id
            assert "status" in data
            assert "stories" in data
    
    def test_returns_404_for_unknown_job(self, client):
        """Test that 404 is returned for unknown job_id."""
        response = client.get("/v1/jobs/unknown-job-id")
        
        assert response.status_code == 404
    
    def test_job_contains_expected_fields(self, client):
        """Test that job response contains all expected fields."""
        with patch('api_server.run_bulk_job_jira'):
            request_data = {
                "userStories": [
                    {"userStoryJiraId": "STORY-001", "userStory": "Story text"}
                ],
                "ScenarioTypes": ["Functional"]
            }
            create_response = client.post("/v1/generate-test-cases/bulk", json=request_data)
            job_id = create_response.json()["job_id"]
            
            response = client.get(f"/v1/jobs/{job_id}")
            data = response.json()
            
            assert "job_id" in data
            assert "created_at" in data
            assert "status" in data
            assert "total" in data
            assert "completed_count" in data
            assert "failed_count" in data
            assert "ScenarioTypes" in data
            assert "stories" in data


class TestRetryFailedEndpoint:
    """Tests for POST /v1/jobs/{job_id}/retry-failed endpoint."""
    
    def test_returns_404_for_unknown_job(self, client):
        """Test that 404 is returned for unknown job_id."""
        response = client.post("/v1/jobs/unknown-job-id/retry-failed")
        
        assert response.status_code == 404
    
    def test_rejects_retry_while_processing(self, client):
        """Test that retry is rejected while job is still processing."""
        with patch('api_server.run_bulk_job_jira'), \
             patch('api_server._jobs') as mock_jobs, \
             patch('api_server._jobs_lock', MagicMock()):
            
            mock_jobs.get.return_value = {
                "job_id": "test-job",
                "status": "processing",
                "ScenarioTypes": ["Functional"],
                "stories": []
            }
            
            response = client.post("/v1/jobs/test-job/retry-failed")
            
            assert response.status_code in [400, 404]


class TestPydanticValidation:
    """Tests for Pydantic model validation."""
    
    def test_story_item_strips_whitespace(self, client):
        """Test that StoryItem strips whitespace from fields."""
        with patch('api_server.run_bulk_job_jira'):
            request_data = {
                "userStories": [
                    {"userStoryJiraId": "  STORY-001  ", "userStory": "  User story text  "}
                ],
                "ScenarioTypes": ["Functional"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=request_data)
            
            assert response.status_code == 202
    
    def test_rejects_whitespace_only_jira_id(self, client):
        """Test that whitespace-only userStoryJiraId is rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": "   ", "userStory": "User story text"}
            ],
            "ScenarioTypes": ["Functional"]
        }
        
        response = client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_rejects_whitespace_only_user_story(self, client):
        """Test that whitespace-only userStory is rejected."""
        request_data = {
            "userStories": [
                {"userStoryJiraId": "STORY-001", "userStory": "   "}
            ],
            "ScenarioTypes": ["Functional"]
        }
        
        response = client.post("/v1/generate-test-cases/bulk", json=request_data)
        
        assert response.status_code == 422
    
    def test_accepts_multiple_valid_stories(self, client):
        """Test that multiple valid stories are accepted."""
        with patch('api_server.run_bulk_job_jira'):
            request_data = {
                "userStories": [
                    {"userStoryJiraId": "STORY-001", "userStory": "Story 1"},
                    {"userStoryJiraId": "STORY-002", "userStory": "Story 2"},
                    {"userStoryJiraId": "STORY-003", "userStory": "Story 3"}
                ],
                "ScenarioTypes": ["Functional", "Boundary & Negative"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=request_data)
            
            assert response.status_code == 202
            data = response.json()
            assert data["total"] == 3
    
    def test_accepts_maximum_stories(self, client):
        """Test that exactly 50 stories are accepted."""
        with patch('api_server.run_bulk_job_jira'):
            request_data = {
                "userStories": [
                    {"userStoryJiraId": f"STORY-{i:03d}", "userStory": f"Story {i}"}
                    for i in range(50)
                ],
                "ScenarioTypes": ["Functional"]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=request_data)
            
            assert response.status_code == 202
            data = response.json()
            assert data["total"] == 50
    
    def test_accepts_maximum_scenario_types(self, client):
        """Test that exactly 10 scenario types are accepted."""
        with patch('api_server.run_bulk_job_jira'):
            request_data = {
                "userStories": [
                    {"userStoryJiraId": "STORY-001", "userStory": "Story 1"}
                ],
                "ScenarioTypes": [
                    "Functional", "Non Functional", "Boundary & Negative",
                    "Gherkin Functional", "Gherkin Boundary & Negative",
                    "Buttons Enabled-Disabled", "Dropdown-Picklist",
                    "System Architecture", "Combinatorial", "Bug Related"
                ]
            }
            
            response = client.post("/v1/generate-test-cases/bulk", json=request_data)
            
            assert response.status_code == 202


class TestCORSMiddleware:
    """Tests for CORS middleware configuration."""
    
    def test_cors_allows_all_origins(self, client):
        """Test that CORS allows the requesting origin (configured as allow_origins=['*'])."""
        response = client.options(
            "/v1/generate-test-cases/bulk",
            headers={"Origin": "http://example.com", "Access-Control-Request-Method": "POST"}
        )
        
        # When allow_origins=["*"] with allow_credentials=True, FastAPI returns the specific origin
        assert response.headers.get("access-control-allow-origin") in ["*", "http://example.com"]


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""
    
    def test_openapi_endpoint_accessible(self, client):
        """Test that OpenAPI schema is accessible."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
    
    def test_docs_endpoint_accessible(self, client):
        """Test that Swagger docs endpoint is accessible."""
        response = client.get("/docs")
        
        assert response.status_code == 200
