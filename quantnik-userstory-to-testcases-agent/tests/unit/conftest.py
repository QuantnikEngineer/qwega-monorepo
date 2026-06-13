"""
Pytest configuration and shared fixtures for unit tests.
"""
import pytest
from unittest.mock import MagicMock, patch
import json
import threading


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_user_story():
    """Sample user story for testing."""
    return """
    As a user, I want to be able to login to the application using my email and password
    so that I can access my personalized dashboard.
    
    Acceptance Criteria:
    1. User can enter email in the email field
    2. User can enter password in the password field
    3. User can click the login button to submit credentials
    4. System validates credentials and redirects to dashboard on success
    5. System shows error message on invalid credentials
    """


@pytest.fixture
def sample_user_story_empty():
    """Empty user story for negative testing."""
    return ""


@pytest.fixture
def sample_user_story_whitespace():
    """Whitespace-only user story for negative testing."""
    return "   \n\t  "


@pytest.fixture
def sample_test_scenarios_response():
    """Sample AI-generated test scenarios response."""
    return """
    Test Scenario ID: TS01
    Test Scenario Description: Verify user can successfully login with valid credentials
    Expected Results: User should be redirected to the dashboard
    Priority: P1
    Pre-Condition: User has a valid account
    
    Test Scenario ID: TS02
    Test Scenario Description: Verify error message displayed for invalid credentials
    Expected Results: Error message should be displayed
    Priority: P1
    Pre-Condition: User has invalid credentials
    """


@pytest.fixture
def sample_test_cases_json():
    """Sample AI-generated test cases in JSON format."""
    return [
        {
            "Test Case ID": "TC01",
            "Test Case Name": "Valid Login Test",
            "Test Case Description": "Verify user can login with valid credentials",
            "Steps": [
                {
                    "Step Number": "1",
                    "Test Case Step": "Navigate to login page",
                    "Expected Results": "Login page should be displayed"
                },
                {
                    "Step Number": "2",
                    "Test Case Step": "Enter valid email",
                    "Expected Results": "Email should be accepted"
                },
                {
                    "Step Number": "3",
                    "Test Case Step": "Enter valid password",
                    "Expected Results": "Password should be masked"
                },
                {
                    "Step Number": "4",
                    "Test Case Step": "Click login button",
                    "Expected Results": "User should be redirected to dashboard"
                }
            ]
        },
        {
            "Test Case ID": "TC02",
            "Test Case Name": "Invalid Login Test",
            "Test Case Description": "Verify error message for invalid credentials",
            "Steps": [
                {
                    "Step Number": "1",
                    "Test Case Step": "Navigate to login page",
                    "Expected Results": "Login page should be displayed"
                },
                {
                    "Step Number": "2",
                    "Test Case Step": "Enter invalid email",
                    "Expected Results": "Email should be accepted"
                },
                {
                    "Step Number": "3",
                    "Test Case Step": "Enter invalid password",
                    "Expected Results": "Password should be masked"
                },
                {
                    "Step Number": "4",
                    "Test Case Step": "Click login button",
                    "Expected Results": "Error message should be displayed"
                }
            ]
        }
    ]


@pytest.fixture
def sample_test_cases_json_string(sample_test_cases_json):
    """Sample test cases as JSON string."""
    return json.dumps(sample_test_cases_json)


@pytest.fixture
def sample_jira_config():
    """Sample Jira configuration."""
    return {
        "base_url": "https://test-jira.atlassian.net/",
        "username": "test@example.com",
        "api_token": "test-token-123",
        "project_key": "TEST",
    }


@pytest.fixture
def sample_xray_config():
    """Sample Xray configuration."""
    return {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
    }


@pytest.fixture
def sample_qtest_config():
    """Sample qTest configuration."""
    return {
        "base_url": "https://test-qtest.qtestnet.com/api/v3",
        "project_id": "12345",
        "token": "test-qtest-token",
    }


@pytest.fixture
def sample_jira_issue_response():
    """Sample Jira issue API response."""
    return {
        "id": "10001",
        "key": "TEST-123",
        "fields": {
            "summary": "Test Case Summary",
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Test description"}
                        ]
                    }
                ]
            },
            "labels": ["STORY-001"]
        }
    }


@pytest.fixture
def sample_jira_search_response(sample_jira_issue_response):
    """Sample Jira search API response."""
    return {
        "issues": [sample_jira_issue_response],
        "total": 1,
        "maxResults": 200
    }


@pytest.fixture
def sample_xray_steps():
    """Sample Xray test steps."""
    return [
        {"id": "step-1", "action": "Navigate to login page", "data": "", "result": "Login page displayed"},
        {"id": "step-2", "action": "Enter credentials", "data": "", "result": "Credentials entered"},
        {"id": "step-3", "action": "Click login", "data": "", "result": "User logged in"}
    ]


@pytest.fixture
def sample_existing_issues():
    """Sample existing Jira issues for brownfield testing."""
    return [
        {
            "key": "TEST-100",
            "id": "10100",
            "summary": "Valid Login Test Case",
            "description": "Test for valid login functionality",
            "steps": []
        },
        {
            "key": "TEST-101",
            "id": "10101",
            "summary": "Invalid Login Error Test",
            "description": "Test for invalid login error handling",
            "steps": []
        }
    ]


@pytest.fixture
def sample_brownfield_diff_response():
    """Sample LLM response for brownfield diff."""
    return {
        "updated_test_cases": [
            {
                "existing_key": "TEST-100",
                "Test Case Name": "Valid Login Test",
                "Test Case Description": "Updated description",
                "Steps": [
                    {"Step Number": "1", "Test Case Step": "Navigate", "Expected Results": "Page loads"}
                ],
                "change_reason": "Updated steps"
            },
            {
                "existing_key": None,
                "Test Case Name": "New Test Case",
                "Test Case Description": "Brand new test",
                "Steps": [
                    {"Step Number": "1", "Test Case Step": "New step", "Expected Results": "New result"}
                ],
                "change_reason": "New scenario identified"
            }
        ],
        "summary": "Updated 1 test case, created 1 new test case"
    }


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_model():
    """Mock Vertex AI GenerativeModel."""
    with patch('userstory2TestCasesAgent.model') as mock:
        yield mock


@pytest.fixture
def mock_requests():
    """Mock requests module."""
    with patch('userstory2TestCasesAgent.requests') as mock:
        yield mock


@pytest.fixture
def mock_vertex_init():
    """Mock Vertex AI initialization."""
    with patch('userstory2TestCasesAgent.init') as mock:
        yield mock


# ============================================================================
# Job Store Fixtures
# ============================================================================

@pytest.fixture
def job_store():
    """Empty job store for testing."""
    return {}


@pytest.fixture
def jobs_lock():
    """Threading lock for job store."""
    return threading.Lock()


@pytest.fixture
def sample_job_entry():
    """Sample job entry for testing."""
    return {
        "job_id": "test-job-123",
        "created_at": "2024-01-01T00:00:00Z",
        "completed_at": None,
        "status": "pending",
        "total": 2,
        "completed_count": 0,
        "failed_count": 0,
        "ScenarioTypes": ["Functional", "Boundary & Negative"],
        "stories": [
            {
                "index": 0,
                "userStoryJiraId": "STORY-001",
                "status": "pending",
                "results_by_scenario": {},
                "error": None
            },
            {
                "index": 1,
                "userStoryJiraId": "STORY-002",
                "status": "pending",
                "results_by_scenario": {},
                "error": None
            }
        ]
    }


# ============================================================================
# API Test Client Fixture
# ============================================================================

@pytest.fixture
def test_client():
    """FastAPI test client."""
    from fastapi.testclient import TestClient
    
    # Patch the agent module imports before importing api_server
    with patch('userstory2TestCasesAgent.init'), \
         patch('userstory2TestCasesAgent.GenerativeModel'):
        from api_server import app
        client = TestClient(app)
        yield client


@pytest.fixture
def mock_api_server_dependencies():
    """Mock all external dependencies for API server tests."""
    with patch('api_server.run_bulk_job_jira') as mock_jira, \
         patch('api_server.run_bulk_job_qtest') as mock_qtest, \
         patch('api_server.run_bulk_brownfield_job_jira') as mock_brownfield, \
         patch('api_server.process_single_story_jira') as mock_single_jira, \
         patch('api_server.process_single_story_qtest') as mock_single_qtest:
        yield {
            'run_bulk_job_jira': mock_jira,
            'run_bulk_job_qtest': mock_qtest,
            'run_bulk_brownfield_job_jira': mock_brownfield,
            'process_single_story_jira': mock_single_jira,
            'process_single_story_qtest': mock_single_qtest
        }


# ============================================================================
# Scenario Types Fixture
# ============================================================================

@pytest.fixture
def valid_scenario_types():
    """List of all valid scenario types."""
    return [
        "Functional",
        "Non Functional",
        "Boundary & Negative",
        "Gherkin Functional",
        "Gherkin Boundary & Negative",
        "Buttons Enabled-Disabled",
        "Dropdown-Picklist",
        "System Architecture",
        "Combinatorial",
        "Bug Related",
        "Patch Related"
    ]


@pytest.fixture
def invalid_scenario_types():
    """List of invalid scenario types for negative testing."""
    return ["InvalidType", "Random", "NotAType"]
