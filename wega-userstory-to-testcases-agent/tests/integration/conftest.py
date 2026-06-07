"""
Pytest configuration and shared fixtures for integration tests.

Integration tests can run in different modes:
- MOCK: Use responses library to simulate external APIs (default)
- SANDBOX: Run against sandbox/test instances
- LIVE: Run against production APIs with test projects

Set INTEGRATION_TEST_MODE environment variable to control mode.
"""
import pytest
import os
import json
import threading
import responses
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List
from datetime import datetime


# ============================================================================
# Test Mode Configuration
# ============================================================================

TEST_MODE = os.getenv("INTEGRATION_TEST_MODE", "MOCK").upper()

def is_mock_mode():
    return TEST_MODE == "MOCK"

def is_sandbox_mode():
    return TEST_MODE == "SANDBOX"

def is_live_mode():
    return TEST_MODE == "LIVE"


# ============================================================================
# Skip Decorators
# ============================================================================

skip_if_mock = pytest.mark.skipif(
    is_mock_mode(),
    reason="Skipped in MOCK mode - requires real external services"
)

skip_if_live = pytest.mark.skipif(
    is_live_mode(),
    reason="Skipped in LIVE mode - uses mocked responses"
)

requires_jira_credentials = pytest.mark.skipif(
    not os.getenv("JIRA_API_TOKEN"),
    reason="Requires JIRA_API_TOKEN environment variable"
)

requires_xray_credentials = pytest.mark.skipif(
    not os.getenv("XRAY_CLIENT_ID") or not os.getenv("XRAY_CLIENT_SECRET"),
    reason="Requires XRAY_CLIENT_ID and XRAY_CLIENT_SECRET environment variables"
)

requires_qtest_credentials = pytest.mark.skipif(
    not os.getenv("QTEST_TOKEN"),
    reason="Requires QTEST_TOKEN environment variable"
)

requires_vertex_ai = pytest.mark.skipif(
    not os.getenv("PROJECT_ID"),
    reason="Requires PROJECT_ID environment variable for Vertex AI"
)


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def jira_config():
    """Jira configuration from environment or defaults for testing."""
    return {
        "base_url": os.getenv("JIRA_BASE_URL", "https://test-jira.atlassian.net/"),
        "username": os.getenv("JIRA_USERNAME", "test@example.com"),
        "api_token": os.getenv("JIRA_API_TOKEN", "test-token"),
        "project_key": os.getenv("JIRA_PROJECT_KEY", "TEST"),
    }


@pytest.fixture
def xray_config():
    """Xray configuration from environment or defaults for testing."""
    return {
        "client_id": os.getenv("XRAY_CLIENT_ID", "test-client-id"),
        "client_secret": os.getenv("XRAY_CLIENT_SECRET", "test-client-secret"),
    }


@pytest.fixture
def qtest_config():
    """qTest configuration from environment or defaults for testing."""
    return {
        "base_url": os.getenv("QTEST_BASE_URL", "https://test.qtestnet.com/api/v3"),
        "project_id": os.getenv("QTEST_PROJECT_ID", "12345"),
        "token": os.getenv("QTEST_TOKEN", "test-token"),
    }


@pytest.fixture
def vertex_ai_config():
    """Vertex AI configuration from environment or defaults."""
    return {
        "project_id": os.getenv("PROJECT_ID", "test-project"),
        "location": os.getenv("LOCATION", "us-central1"),
        "model_name": os.getenv("MODEL_NAME", "gemini-1.5-flash"),
    }


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_user_story():
    """Sample user story for integration testing."""
    return """
    As a registered user, I want to be able to reset my password via email
    so that I can regain access to my account if I forget my password.

    Acceptance Criteria:
    1. User can click "Forgot Password" link on login page
    2. User enters their registered email address
    3. System sends a password reset email with a secure link
    4. Link expires after 24 hours
    5. User can set a new password meeting security requirements
    6. User receives confirmation email after successful reset
    7. Old password no longer works after reset
    """


@pytest.fixture
def sample_user_stories():
    """Multiple sample user stories for bulk testing."""
    return [
        {
            "userStoryJiraId": "STORY-001",
            "userStory": """
            As a user, I want to login with my email and password
            so that I can access my personalized dashboard.
            
            Acceptance Criteria:
            1. User can enter email in email field
            2. User can enter password in password field
            3. System validates credentials
            4. User is redirected to dashboard on success
            5. Error message shown on invalid credentials
            """
        },
        {
            "userStoryJiraId": "STORY-002",
            "userStory": """
            As a user, I want to view my profile information
            so that I can verify my account details are correct.
            
            Acceptance Criteria:
            1. User can navigate to profile page
            2. Profile displays name, email, phone
            3. User can see account creation date
            4. User can see last login time
            """
        },
        {
            "userStoryJiraId": "STORY-003",
            "userStory": """
            As a user, I want to update my profile picture
            so that other users can recognize me.
            
            Acceptance Criteria:
            1. User can click on profile picture to change it
            2. User can upload JPG, PNG, or GIF files
            3. Maximum file size is 5MB
            4. Image is cropped to square format
            5. Previous picture is replaced
            """
        }
    ]


@pytest.fixture
def sample_scenario_types():
    """Common scenario types for testing."""
    return ["Functional", "Boundary & Negative"]


@pytest.fixture
def all_scenario_types():
    """All available scenario types."""
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


# ============================================================================
# Mock Response Fixtures
# ============================================================================

@pytest.fixture
def mock_vertex_ai_response():
    """Mock Vertex AI model response."""
    return {
        "scenarios": """
Test Scenario ID: TS01
Test Scenario Description: Verify user can successfully login with valid credentials
Expected Results: User should be redirected to the dashboard
Priority: P1
Pre-Condition: User has a valid registered account

Test Scenario ID: TS02
Test Scenario Description: Verify error message displayed for invalid password
Expected Results: Error message "Invalid credentials" should be displayed
Priority: P1
Pre-Condition: User has a valid registered account
        """,
        "test_cases": [
            {
                "Test Case ID": "TC01",
                "Test Case Name": "Valid Login Test",
                "Test Case Description": "Verify successful login with valid credentials",
                "Steps": [
                    {"Step Number": "1", "Test Case Step": "Navigate to login page", "Expected Results": "Login page should be displayed"},
                    {"Step Number": "2", "Test Case Step": "Enter valid email", "Expected Results": "Email should be accepted"},
                    {"Step Number": "3", "Test Case Step": "Enter valid password", "Expected Results": "Password should be masked"},
                    {"Step Number": "4", "Test Case Step": "Click login button", "Expected Results": "User should be redirected to dashboard"}
                ]
            },
            {
                "Test Case ID": "TC02",
                "Test Case Name": "Invalid Password Test",
                "Test Case Description": "Verify error message for invalid password",
                "Steps": [
                    {"Step Number": "1", "Test Case Step": "Navigate to login page", "Expected Results": "Login page should be displayed"},
                    {"Step Number": "2", "Test Case Step": "Enter valid email", "Expected Results": "Email should be accepted"},
                    {"Step Number": "3", "Test Case Step": "Enter invalid password", "Expected Results": "Password should be masked"},
                    {"Step Number": "4", "Test Case Step": "Click login button", "Expected Results": "Error message should be displayed"}
                ]
            }
        ]
    }


@pytest.fixture
def mock_jira_issue_response():
    """Mock Jira create issue response."""
    return {
        "id": "10001",
        "key": "TEST-100",
        "self": "https://test-jira.atlassian.net/rest/api/3/issue/10001"
    }


@pytest.fixture
def mock_jira_search_response():
    """Mock Jira search response."""
    return {
        "issues": [
            {
                "id": "10001",
                "key": "TEST-100",
                "fields": {
                    "summary": "Existing Test Case 1",
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Test description"}]}]
                    },
                    "labels": ["STORY-001"]
                }
            }
        ],
        "total": 1,
        "maxResults": 200
    }


@pytest.fixture
def mock_xray_token_response():
    """Mock Xray authentication response."""
    return "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-token"


@pytest.fixture
def mock_xray_steps_response():
    """Mock Xray get test steps response."""
    return {
        "data": {
            "getTest": {
                "issueId": "10001",
                "steps": [
                    {"id": "step-1", "action": "Navigate to page", "data": "", "result": "Page loads"},
                    {"id": "step-2", "action": "Click button", "data": "", "result": "Action performed"}
                ]
            }
        }
    }


@pytest.fixture
def mock_qtest_response():
    """Mock qTest create test case response."""
    return {
        "id": 12345,
        "name": "Test Case Name",
        "pid": "TC-123"
    }


# ============================================================================
# API Response Mocking
# ============================================================================

@pytest.fixture
def mock_external_apis(mock_jira_issue_response, mock_xray_token_response, mock_qtest_response):
    """Set up responses mock for all external APIs."""
    with responses.RequestsMock() as rsps:
        # Jira API mocks
        rsps.add(
            responses.POST,
            "https://test-jira.atlassian.net/rest/api/3/issue",
            json=mock_jira_issue_response,
            status=201
        )
        rsps.add(
            responses.GET,
            "https://test-jira.atlassian.net/rest/api/3/issue/TEST-100",
            json={"id": "10001", "key": "TEST-100"},
            status=200
        )
        rsps.add(
            responses.PUT,
            "https://test-jira.atlassian.net/rest/api/3/issue/TEST-100",
            status=204
        )
        
        # Xray API mocks
        rsps.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/authenticate",
            json=mock_xray_token_response,
            status=200
        )
        rsps.add(
            responses.POST,
            "https://xray.cloud.getxray.app/api/v2/graphql",
            json={"data": {"addTestStep": {"id": "step-1"}}},
            status=200
        )
        
        # qTest API mocks
        rsps.add(
            responses.POST,
            "https://test.qtestnet.com/api/v3/projects/12345/test-cases",
            json=mock_qtest_response,
            status=201
        )
        rsps.add(
            responses.POST,
            "https://test.qtestnet.com/api/v3/projects/12345/test-cases/12345/test-steps",
            json=[],
            status=201
        )
        
        yield rsps


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
        "created_at": datetime.utcnow().isoformat() + "Z",
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
# FastAPI Test Client
# ============================================================================

@pytest.fixture
def test_client():
    """FastAPI test client with mocked Vertex AI initialization."""
    with patch('userstory2TestCasesAgent.init'), \
         patch('userstory2TestCasesAgent.GenerativeModel'):
        from fastapi.testclient import TestClient
        from api_server import app
        yield TestClient(app)


@pytest.fixture
def test_client_with_mocked_processing():
    """FastAPI test client with mocked background processing."""
    with patch('userstory2TestCasesAgent.init'), \
         patch('userstory2TestCasesAgent.GenerativeModel'), \
         patch('api_server.run_bulk_job_jira'), \
         patch('api_server.run_bulk_job_qtest'), \
         patch('api_server.run_bulk_brownfield_job_jira'):
        from fastapi.testclient import TestClient
        from api_server import app
        yield TestClient(app)


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_job_store():
    """Clean up job store after each test."""
    yield
    # Reset job stores after test
    try:
        from api_server import _jobs, _job_inputs, _job_targets
        _jobs.clear()
        _job_inputs.clear()
        _job_targets.clear()
    except ImportError:
        pass


# ============================================================================
# Markers
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")
    config.addinivalue_line("markers", "requires_credentials: Tests requiring real API credentials")
