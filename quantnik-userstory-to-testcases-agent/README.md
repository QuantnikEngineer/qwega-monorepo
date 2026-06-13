# QUANTNIK User Story to Test Cases Agent

An AI Powered Agent that converts user stories into structured test scenarios and test cases, then pushes results to one of these targets:

- Jira + Xray (greenfield)
- qTest (greenfield)
- Azure DevOps Test Cases (greenfield)
- Jira + Xray (brownfield update and gap-fill)

The API is implemented with FastAPI and supports async bulk jobs with status polling and retry for failed scenarios.

## What This Service Does

1. Accepts one or more user stories plus one or more scenario types.
2. Uses an LLM (Google Vertex AI Gemini or Azure OpenAI, based on config) to generate scenarios and test cases.
3. Pushes generated test cases into your selected test management system.
4. Returns a job ID immediately for bulk operations.
5. Lets you poll status and retry failed scenarios without rerunning successful ones.

## Key Features

- Bulk async processing (up to 50 user stories per request)
- Parallel execution with thread pool workers
- 11 supported scenario types
- Retry endpoint for failed scenario-level work
- Greenfield and brownfield Jira/Xray flows
- Optional Langfuse + OpenTelemetry instrumentation
- Docker-ready deployment
- Certificate bundle support for corporate SSL environments

## Repository Layout

- `api_server.py`: FastAPI app and endpoints
- `userstory2TestCasesAgent.py`: LLM prompts, generation logic, and target integrations
- `main.py`: instrumented runtime entry point (Langfuse/OTEL)
- `langfuse_instrumentation.py`: monkey patches, middleware, metrics/spans
- `build_cert_bundle.py`: builds `combined_ca.pem` from cert sources
- `scripts/extract_metrics.py`: exports Langfuse generation metrics
- `scripts/generate_report.py`: creates text/JSON summary reports
- `envs/`: sample env files for Azure and GCP-style setups

## Prerequisites

- Python 3.11+
- Access to one LLM provider:
  - Google Vertex AI, or
  - Azure OpenAI
- Access to at least one target system you plan to push to:
  - Jira + Xray, or
  - qTest, or
  - Azure DevOps

## Local Setup

### 1. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create `.env`

You can start from one of these templates:

- `envs/gcp.env.example`
- `envs/azure.env.example`

Then ensure the runtime variables below match your chosen provider and integration targets.

## Environment Variables

### Core LLM configuration

Google Vertex AI path:

- `LLM_PROVIDER=google`
- `PROJECT_ID`
- `LOCATION` (default: `global`)
- `STAGING_BUCKET`
- `MODEL_NAME` (default: `gemini-3-flash-preview`)
- Authentication via standard Google credentials (for example `GOOGLE_APPLICATION_CREDENTIALS`)

Azure OpenAI path:

- `LLM_PROVIDER=azure`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`

### Jira + Xray (greenfield and brownfield)

- `JIRA_BASE_URL`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`
- `JIRA_PROJECT_KEY`
- `XRAY_CLIENT_ID`
- `XRAY_CLIENT_SECRET`
- `XRAY_GRAPHQL_URL` (optional, defaults to Xray Cloud GraphQL URL)
- `TEST_PLAN_KEY` (optional default exists, but set this explicitly)

### qTest

- `QTEST_BASE_URL`
- `QTEST_PROJECT_ID`
- `QTEST_TOKEN`

### Azure DevOps target

- `AZURE_DEVOPS_ORG_URL`
- `AZURE_DEVOPS_PROJECT`
- `AZURE_DEVOPS_PAT`

### API runtime

- `PORT` (default: `8080`)
- `UVICORN_RELOAD` (`1/true/yes` to enable autoreload locally)

### SSL/certificate options

- `DISABLE_SSL_VERIFY=true` (dev/testing only)
- `REQUESTS_CA_BUNDLE` (recommended for corporate CA chains)
- `SSL_CERT_FILE`
- `OTEL_CA_CERT_PATH` (used by `main.py` for combined bundle path)

### Observability (optional)

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST` (default: `https://cloud.langfuse.com`)
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_PROTOCOL` (`grpc` or `http/protobuf`)
- `OTEL_SERVICE_NAME`
- `OTEL_RESOURCE_ATTRIBUTES`

## Running the Service

### Standard API mode

```bash
python api_server.py
```

- Base URL: `http://localhost:8080`
- Swagger docs: `http://localhost:8080/docs`

### Instrumented mode (Langfuse/OTEL)

```bash
python main.py
```

Use this mode when you want tracing/metrics middleware and instrumentation enabled.

## API Endpoints

### Health and metadata

- `GET /`
- `GET /health`
- `GET /scenario-types`

### Bulk generation

- `POST /v1/generate-test-cases/bulk`
  - Greenfield push to Jira + Xray
- `POST /v1/generate-test-cases/bulk/qtest`
  - Greenfield push to qTest
- `POST /v1/generate-test-cases/bulk/ado`
  - Greenfield push to Azure DevOps Test Cases
- `POST /v1/generate-test-cases/bulk/brownfield`
  - Brownfield Jira/Xray update and gap-fill flow

### Job operations

- `GET /v1/jobs/{job_id}`
  - Poll job status and detailed per-story/per-scenario results
- `POST /v1/jobs/{job_id}/retry-failed`
  - Retries only failed scenarios in the same job

## Request Shape (Bulk)

Typical request body:

```json
{
  "userStories": [
    {
      "userStoryJiraId": "QUANTNIK-123",
      "userStory": "As a user, I want to reset my password so I can regain access"
    }
  ],
  "ScenarioTypes": ["Functional", "Boundary & Negative"]
}
```

Response (202 Accepted):

```json
{
  "job_id": "7f9f4d6d-7a06-4ea9-9e8d-6f6a2f10f0bb",
  "total": 1,
  "message": "Job submitted ...",
  "poll_url": "/v1/jobs/7f9f4d6d-7a06-4ea9-9e8d-6f6a2f10f0bb"
}
```

## cURL Examples

### Jira + Xray greenfield

```bash
curl -X POST "http://localhost:8080/v1/generate-test-cases/bulk" \
  -H "Content-Type: application/json" \
  -d '{
    "userStories": [
      {"userStoryJiraId": "QUANTNIK-123", "userStory": "As a user, I want to login"}
    ],
    "ScenarioTypes": ["Functional"]
  }'
```

### qTest greenfield

```bash
curl -X POST "http://localhost:8080/v1/generate-test-cases/bulk/qtest" \
  -H "Content-Type: application/json" \
  -d '{
    "userStories": [
      {"userStoryJiraId": "QUANTNIK-124", "userStory": "As a user, I want to logout"}
    ],
    "ScenarioTypes": ["Functional", "Non Functional"]
  }'
```

### Azure DevOps greenfield

```bash
curl -X POST "http://localhost:8080/v1/generate-test-cases/bulk/ado" \
  -H "Content-Type: application/json" \
  -d '{
    "userStories": [
      {"userStoryJiraId": "QUANTNIK-125", "userStory": "As an admin, I want role-based access control"}
    ],
    "ScenarioTypes": ["Functional"]
  }'
```

### Brownfield Jira + Xray

```bash
curl -X POST "http://localhost:8080/v1/generate-test-cases/bulk/brownfield" \
  -H "Content-Type: application/json" \
  -d '{
    "userStories": [
      {"userStoryJiraId": "QUANTNIK-126", "userStory": "As a user, I want MFA at sign-in"}
    ],
    "ScenarioTypes": ["Boundary & Negative", "Bug Related"]
  }'
```

### Poll job status

```bash
curl "http://localhost:8080/v1/jobs/<job_id>"
```

### Retry failed scenarios

```bash
curl -X POST "http://localhost:8080/v1/jobs/<job_id>/retry-failed"
```

## Scenario Types Supported

1. Functional
2. Non Functional
3. Boundary & Negative
4. Gherkin Functional
5. Gherkin Boundary & Negative
6. Buttons Enabled-Disabled
7. Dropdown-Picklist
8. System Architecture
9. Combinatorial
10. Bug Related
11. Patch Related

## Job Status Model

Job-level status:

- `pending`
- `processing`
- `completed`
- `failed`
- `partial_success`

Story-level status:

- `pending`
- `processing`
- `success`
- `failed`
- `partial_success`

## Docker

Build image:

```bash
docker build -t quantnik-userstory-to-testcases-agent:latest .
```

Run container:

```bash
docker run --rm -p 8080:8080 --env-file .env quantnik-userstory-to-testcases-agent:latest
```

Health check endpoint:

```bash
curl http://localhost:8080/health
```

## SSL and Corporate CA Bundle

If your environment requires custom trust chains:

1. Place cert material under `cert/` and/or set `LANGFUSE_CA_CERT_PATH`.
2. Build a combined CA bundle:

```bash
python build_cert_bundle.py
```

3. Set:

- `REQUESTS_CA_BUNDLE=/path/to/combined_ca.pem`
- `SSL_CERT_FILE=/path/to/combined_ca.pem`

Prefer CA bundle configuration over disabling SSL verification.

## Observability and Reporting

### Enable runtime instrumentation

Start using instrumented entry point:

```bash
python main.py
```

### Export Langfuse generation metrics

```bash
python scripts/extract_metrics.py
```

Produces:

- `scripts/metrics_report.json`
- `scripts/cost_summary.txt`

### Generate human-readable report

```bash
python scripts/generate_report.py
```

Produces:

- `scripts/testdata_metrics_report.txt`
- `scripts/testdata_metrics_report.json`

## Troubleshooting

### 1. Invalid ScenarioTypes error

Call `GET /scenario-types` and ensure your request values match exactly.

### 2. Job stuck in processing

Check server logs for external API timeouts (LLM, Jira/Xray, qTest, ADO) and retry failed scenarios with `/v1/jobs/{job_id}/retry-failed`.

### 3. Jira/Xray failures

- Verify Jira credentials and project permissions.
- Verify Xray client credentials.
- Confirm `TEST_PLAN_KEY` exists when linking to plan is expected.

### 4. qTest failures

- Validate base URL format and token validity.
- Confirm project ID is correct.

### 5. ADO failures

- Verify `AZURE_DEVOPS_ORG_URL`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT`.
- Ensure PAT has work item write permissions.

### 6. TLS/SSL handshake errors

Build and use `combined_ca.pem`, and set `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` accordingly.

## Security Notes

- Never commit `.env` with real secrets.
- Use least-privilege API tokens.
- Keep `DISABLE_SSL_VERIFY=false` in production.

## License

Add your license details here.
