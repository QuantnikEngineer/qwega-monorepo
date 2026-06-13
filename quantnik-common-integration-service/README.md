# Quantnik Common Integration Service

LangGraph-based orchestrator for context enrichment operations. This service acts as a child orchestrator for the `quantnik-sdlc-orchestrator`, handling all RAG (Retrieval-Augmented Generation) knowledge base operations.

## Architecture

```
┌─────────────────────────┐
│  quantnik-sdlc-orchestrator │
│       (Parent)          │
└───────────┬─────────────┘
            │
   ┌────────┼────────┬────────────────┐
   ▼        ▼        ▼                ▼
┌──────┐ ┌──────┐ ┌──────────────────────┐
│Plan  │ │Test  │ │ Common Integration   │ ← You are here
│Orch  │ │Orch  │ │ Service (Port 8002)  │
└──────┘ └──────┘ └──────────┬───────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │   RAG Agent API     │
                  │ (Knowledge Base)    │
                  └─────────────────────┘
```

## Features

| Intent | Description | RAG Endpoint |
|--------|-------------|--------------|
| `context_enrich_upload` | Upload documents/files to knowledge base | POST `/api/v1/upload` |
| `context_enrich_ingest` | Ingest from websites, SharePoint, repos, agent outputs | POST `/api/v1/ingest` |
| `context_enrich_feedback` | Submit ratings, corrections, domain preferences | POST `/api/v1/feedback` |
| `context_enrich_query` | Query the knowledge base | POST `/api/v1/query` |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat` | POST | Main non-streaming chat endpoint |
| `/v1/chat/simple` | POST | Simple chat with auto-generated session |
| `/v1/chat/stream` | POST | Streaming chat with SSE milestones |
| `/api/v1/prompt/analyze` | POST | Legacy endpoint for backward compatibility |
| `/health` | GET | Simple health check |
| `/health/detailed` | GET | Detailed health with RAG agent status |
| `/v1/memory/{session_id}` | GET | Get session memory state |
| `/v1/memory/{session_id}` | DELETE | Clear session memory |
| `/v1/memory/{session_id}/history` | GET | Get conversation history |

## Request Format

All chat endpoints accept the following request body:

```json
{
    "session_id": "sess_123",
    "message": "Your message here",
    "context": {
        // Intent-specific context fields
    },
    "history": [
        {"role": "user", "content": "Previous message"},
        {"role": "assistant", "content": "Previous response"}
    ],
    "explicit_intent": "context_enrich_query",
    "selected_model": "gemini-2.0-flash"
}
```

### Context Fields by Intent

**Upload (`context_enrich_upload`):**
- `files`: Array of file objects (for multipart/form-data)

**Ingest (`context_enrich_ingest`):**
- `source`: "website" | "sharepoint" | "repo" | "agent_output"
- `urls`: Array of URLs (for website)
- `link`: SharePoint link
- `repo_url`, `branch`, `path_filter`: Repository details
- `agent_name`, `source_url`, `content`: Agent output details

**Feedback (`context_enrich_feedback`):**
- `feedback_type`: "rating" | "correction" | "domain_preference"
- `rating`: "positive" | "negative" (for rating type)
- `content`: Feedback content
- `artifact_type`, `sdlc_phase`, `agent_name`, `ref_doc_id`: Optional metadata

**Query (`context_enrich_query`):**
- `query`: Search query string
- `sdlc_phase`: "requirements" | "design" | "development" | "testing" | "deployment" | "security" | "general"
- `top_k`: Number of results (1-20, default 5)
- `include_sources`: Boolean (default true)
- `criticality`: "critical" | "non_critical"

## Optional Parameters

- `selected_model`: Optional model selection passed to all downstream RAG agent API calls (as header or query param)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development/staging/production) | development |
| `PORT` | Server port | 8002 |
| `LOG_LEVEL` | Logging level | INFO |
| `GOOGLE_API_KEY` | Google AI API key for LLM | - |
| `OPENAI_API_KEY` | OpenAI API key (fallback) | - |
| `RAG_AGENT_URL` | RAG Agent base URL | https://dev-quantnik-rag-... |
| `SSL_VERIFY` | Verify SSL certificates | false |
| `AGENT_CALL_TIMEOUT` | Timeout for RAG agent calls (seconds) | 600 |
| `REQUEST_TIMEOUT` | General request timeout (seconds) | 600 |

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
docker build -t quantnik-common-integration-service .
docker run -p 8002:8002 --env-file .env quantnik-common-integration-service
```

## Deployment

### Profile-Based Deployment

The service supports profile-based deployment where the profile name prefixes the service name:

| Profile | Service Name | Environment |
|---------|--------------|-------------|
| (none) | `quantnik-common-integration-service` | Default |
| `dev` | `dev-quantnik-common-integration-service` | Development |
| `qa` | `qa-quantnik-common-integration-service` | QA/Testing |
| `stage` | `stage-quantnik-common-integration-service` | Staging |
| `prod` | `quantnik-common-integration-service` | Production |

### Using deploy.sh (Recommended)

```bash
# Deploy without profile
./deploy.sh

# Deploy with profile
./deploy.sh --profile dev
./deploy.sh --profile qa
./deploy.sh --profile stage
./deploy.sh --profile prod

# Deploy with custom region
./deploy.sh --profile dev --region us-east1

# Dry run (show commands without executing)
./deploy.sh --profile dev --dry-run

# Show help
./deploy.sh --help
```

### Using Cloud Build

```bash
# Deploy without profile
gcloud builds submit --config cloudbuild.yaml

# Deploy with profile
gcloud builds submit --config cloudbuild.yaml --substitutions=_PROFILE=dev
gcloud builds submit --config cloudbuild.yaml --substitutions=_PROFILE=qa
gcloud builds submit --config cloudbuild.yaml --substitutions=_PROFILE=stage

# Deploy with custom region
gcloud builds submit --config cloudbuild.yaml --substitutions=_PROFILE=dev,_REGION=us-east1
```

### Environment Files

Profile-specific environment files are supported:
- `.env` - Default environment
- `.env.dev` - Development environment
- `.env.qa` - QA environment  
- `.env.stage` - Staging environment
- `.env.prod` - Production environment

The deployment script automatically selects the appropriate env file based on the profile.

## Streaming (SSE)

The `/v1/chat/stream` endpoint returns Server-Sent Events with milestone updates:

```
data: {"type": "milestone", "stage": "received", "title": "Request Received", "icon": "📥", "progress": 0.1}

data: {"type": "milestone", "stage": "thinking", "title": "Analyzing Request", "icon": "🤔", "progress": 0.2}

data: {"type": "milestone", "stage": "analyzing", "title": "Intent Classified", "icon": "🎯", "progress": 0.3}

data: {"type": "milestone", "stage": "executing", "title": "Querying Knowledge Base", "icon": "🔍", "progress": 0.5}

data: {"type": "complete", "session_id": "sess_123", "message": "...", "status": "success", "data": {...}}
```

## Logging

All methods include INFO level logging at entry and exit with the filename:

```
[main.py] chat: ENTRY session_id=sess_123 message_preview="Query the..."
[main.py] chat: EXIT session_id=sess_123 status=success intent=context_enrich_query
```

## See Also

- [curl.md](./curl.md) - cURL examples for all endpoints
- [quantnik-sdlc-orchestrator](../Quantnik-sdlc-orchestrator) - Parent orchestrator
- [quantnik-test-orchestrator](../Quantnik-test-orchestrator) - Sibling orchestrator for test operations