from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "WEGA User Story Estimator"


def test_sample_request_endpoint() -> None:
    response = client.get("/sample-estimation-request")
    assert response.status_code == 200
    payload = response.json()
    assert payload["team_id"] == "planning-core"
    assert payload["epics"]


def test_estimate_story_points_endpoint() -> None:
    sample_payload = client.get("/sample-estimation-request").json()
    response = client.post("/estimate-story-points", json=sample_payload)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["synthetic_history_used"] is True
    assert payload["epics"]
    first_story = payload["epics"][0]["user_stories"][0]
    assert first_story["estimated_story_points"] in {1, 2, 3, 5, 8, 13, 21}
    assert first_story["confidence"] in {"LOW", "MEDIUM", "HIGH"}
    assert first_story["similar_stories"]
    assert first_story["rationale"]
