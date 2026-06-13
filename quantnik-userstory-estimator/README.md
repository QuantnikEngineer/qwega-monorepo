# QUANTNIK User Story Estimator

FastAPI service for estimating story points from direct lists of epics and user stories when orchestrators are unavailable locally. The service mirrors the QUANTNIK BRD and QUANTNIK User Story project structure while providing a direct estimation API backed by synthetic historical data.

## What this service does

- Accepts direct epics and user stories over HTTP
- Estimates story points on the Fibonacci scale
- Returns explainable AI style output with confidence and rationale
- Uses synthetic historical backlog data locally so the service can run without orchestrators or external systems
- Supports optional Gemini ADK explanations when credentials are available

## Project structure

```text
QUANTNIK-UserStory-Estimator/
  main.py
  models/
  tools/
  estimator/
  data/
  tests/
```

## Quick start

```bash
cd QUANTNIK-UserStory-Estimator
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

## API endpoints

- `GET /health`
- `GET /sample-estimation-request`
- `POST /estimate-story-points`

## Local sample flow

1. Start the API.
2. Open `GET /sample-estimation-request` to retrieve a synthetic request payload.
3. Send that payload to `POST /estimate-story-points`.
4. Review the estimated stories, confidence scores, similar references, and rationale.

## Security and dependency notes

- Dependency ranges were selected to avoid older unsupported releases while still remaining compatible with enterprise scanners and internal mirrors.
- Before production deployment, validate the resolved lock set through your organization's SonarQube, SCA, and container scanning pipelines.
- The service is designed so numeric estimation does not depend on the LLM. If Gemini is unavailable, the estimator still functions with deterministic explanations.
