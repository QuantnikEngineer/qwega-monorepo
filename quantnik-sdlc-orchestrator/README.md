# Quantnik SDLC Orchestrator

Parent orchestrator for QUANTNIK SDLC workflow automation. This service intelligently routes requests to specialized child orchestrators based on intent classification.

## Architecture

```
┌─────────────────────────────────┐
│     Frontend (React/TSX)        │
└───────────────┬─────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│      SDLC Orchestrator          │  ← You are here (Port 8081)
│   (Intent Classification &      │
│         Routing)                │
└───────────────┬─────────────────┘
                │
   ┌────────────┼────────────┬────────────────────┐
   ▼            ▼            ▼                    ▼
┌──────────┐ ┌──────────┐ ┌────────────────────────┐
│ Planning │ │   Test   │ │  Common Integration    │
│  Orch    │ │   Orch   │ │      Service           │
│ (8000)   │ │ (8001)   │ │      (8002)            │
└──────────┘ └──────────┘ └────────────────────────┘
     │            │                   │
     ▼            ▼                   ▼
  BRD Agent   Test Agents        RAG Agent
  US Agent    Script Agents      (Knowledge Base)
```

## Child Orchestrators

| Orchestrator | Port | Description | Intents |
|--------------|------|-------------|---------|
| **Planning** | 8000 | BRD creation, user stories, validation | `create_brd`, `create_user_story`, `validate_user_story`, `create_user_manual`, `brd_summary` |
| **Test** | 8001 | Test scenarios, scripts, data generation | `generate_test_scenario`, `generate_test_script`, `generate_test_data` |
| **Common Integration** | 8002 | Knowledge base operations | `context_enrich_upload`, `context_enrich_ingest`, `context_enrich_feedback`, `context_enrich_query` |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat` | POST | Main chat endpoint (routes to child orchestrators) |
| `/v1/chat/simple` | POST | Simple chat with auto-generated session |
| `/v1/chat/stream` | POST | Streaming chat with SSE milestones |
| `/v1/capabilities` | GET | Get all orchestrator capabilities |
| `/api/v1/prompt/analyze` | POST | Legacy endpoint for backward compatibility |
| `/health` | GET | Health check with child orchestrator status |
| `/health/connectivity` | GET | Detailed connectivity check |
| `/v1/memory/{session_id}` | GET/DELETE | Session memory management |

## Request Format

```json
{
    "session_id": "sess_123",
    "message": "Your request here",
    "context": {
        // Intent-specific context
    },
    "history": [
        {"role": "user", "content": "Previous message"},
        {"role": "assistant", "content": "Previous response"}
    ],
    "explicit_intent": "create_brd",
    "target_orchestrator": "planning"
}
```

## Response Format

```json
{
    "session_id": "sess_123",
    "message": "Response message",
    "status": "success",
    "job_id": "job_456",
    "nextagentflow": "confirmedCreateBrd",
    "data": {
        "intent": "create_brd",
        "entities": {}
    },
    "push_results": {},
    "suggested_actions": [
        {"action": "Generate user stories", "intent": "create_user_story", "orchestrator": "planning"}
    ],
    "routed_to": "planning",
    "timestamp": "2024-01-15T10:30:00.000000"
}
```

## Intent to nextagentflow Mapping

| Intent | nextagentflow | Orchestrator |
|--------|---------------|--------------|
| `create_brd` | `confirmedCreateBrd` | planning |
| `create_user_story` | `confirmedCreateUserStory` | planning |
| `validate_user_story` | `confirmedValidateUserStory` | planning |
| `create_user_manual` | `confirmedCreateUserManual` | planning |
| `brd_summary` | `confirmedBrdSummary` | planning |
| `generate_test_scenario` | `confirmedUserStoryToTestScenario` | test |
| `generate_test_script` | `confirmedTestCaseToTestScript` | test |
| `context_enrich_upload` | `confirmedContextEnrichUpload` | common_integration |
| `context_enrich_ingest` | `confirmedContextEnrichIngest` | common_integration |
| `context_enrich_feedback` | `confirmedContextEnrichFeedback` | common_integration |
| `context_enrich_query` | `confirmedContextEnrichQuery` | common_integration |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment | development |
| `PORT` | Server port | 8081 |
| `LOG_LEVEL` | Logging level | INFO |
| `GOOGLE_API_KEY` | Google AI API key | - |
| `OPENAI_API_KEY` | OpenAI API key (fallback) | - |
| `PLANNING_ORCHESTRATOR_URL` | Planning orchestrator URL | https://dev-quantnik-planning-orchestrator-... |
| `TEST_ORCHESTRATOR_URL` | Test orchestrator URL | https://dev-quantnik-test-orchestrator-... |
| `COMMON_INTEGRATION_ORCHESTRATOR_URL` | Common Integration orchestrator URL | https://dev-quantnik-common-integration-service-... |
| `SSL_VERIFY` | Verify SSL certificates | true |

## Setup

1. Copy `.env.example` to `.env` and configure required variables

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the service:
   ```bash
   python run.py
   ```

## Docker

```bash
docker build -t quantnik-sdlc-orchestrator .
docker run -p 8081:8081 --env-file .env quantnik-sdlc-orchestrator
```

## Streaming (SSE)

The `/v1/chat/stream` endpoint returns Server-Sent Events with milestone updates that include events from both this orchestrator and the child orchestrators:

```
data: {"type": "milestone", "stage": "received", "title": "Request Received", "icon": "📥", "progress": 0.05}

data: {"type": "milestone", "stage": "analyzing", "title": "Analyzing Intent", "icon": "🔍", "progress": 0.25}

data: {"type": "milestone", "stage": "routing", "title": "Routing to Planning", "icon": "📋", "progress": 0.35}

data: {"type": "milestone", "stage": "executing", "title": "Creating BRD", "icon": "📝", "progress": 0.6, "_forwarded_from": "planning"}

data: {"type": "response", "session_id": "sess_123", "message": "...", "status": "success", "routed_to": "planning"}
```

## See Also

- [curl.md](./curl.md) - cURL examples for all endpoints
- [quantnik-planning-orchestrator](../Quantnik-planning-orchestrator) - Planning child orchestrator
- [quantnik-test-orchestrator](../Quantnik-test-orchestrator) - Test child orchestrator
- [quantnik-common-integration-service](../Quantnik-common-integration-service) - Common Integration child orchestrator
