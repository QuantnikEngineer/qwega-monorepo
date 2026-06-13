# QUANTNIK Deployment Orchestrator

A modern, LLM-powered orchestrator using LangGraph for intelligent routing of deployment workflow requests. This service acts as the parent orchestrator for CI/CD operations, managing pipeline generation, repository operations, and multi-platform deployments.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (QUANTNIK SDLC)                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CI Pipeline Workspace                                              │   │
│  │  • Platform & Target Selection                                       │   │
│  │  • Tool Configuration                                                │   │
│  │  • Streaming Response Display                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │ REST API / SSE Streaming
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SDLC ORCHESTRATOR                                     │
│                    (Routes deployment intents)                              │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  QUANTNIK DEPLOYMENT ORCHESTRATOR (This Project)                │
│                               Port 8091                                     │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    LangGraph State Machine                          │    │
│  │                                                                     │    │
│  │   START ──▶ [Memory] ──▶ [Intent Classifier] ──▶ [Route Agent]     │    │
│  │                                                        │            │    │
│  │                                                        ▼            │    │
│  │   END ◀── [Memory Update] ◀── [Response] ◀── [Execute Actions]    │    │
│  │                                                                     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      CHILD AGENTS                                   │    │
│  │  ┌────────────────────┐              ┌────────────────────┐        │    │
│  │  │     CI Agent       │              │     CD Agent       │        │    │
│  │  │   (Port 8092)      │              │   (Port 8093)      │        │    │
│  │  │                    │              │                    │        │    │
│  │  │  Pipeline          │              │  Deployment        │        │    │
│  │  │  Generation        │              │  Execution         │        │    │
│  │  └────────────────────┘              └────────────────────┘        │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                   REPOSITORY OPERATIONS                             │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐       │    │
│  │  │   List     │ │   List     │ │   Write    │ │  Publish   │       │    │
│  │  │   Repos    │ │  Branches  │ │   Files    │ │  Pipeline  │       │    │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘       │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

### LLM-Based Intent Classification
- **Intelligent Routing**: Routes requests to CI or CD agents based on intent
- **Primary LLM**: Google Gemini with OpenAI fallback
- **Entity Extraction**: Extracts deployment parameters from natural language
- **Confirmation Flow**: Supports "yes/no" confirmation responses

### LangGraph State Machine
- **Flexible Execution**: Graph-based workflow with conditional routing
- **State Persistence**: Session-based state management
- **Streaming Support**: Real-time SSE event streaming

### Repository Operations
- **Multi-Platform Support**: Harness, Azure DevOps, GitHub, GitLab
- **Branch Management**: List and create branches
- **File Operations**: Write files to repositories
- **Pipeline Publishing**: Direct pipeline creation via platform APIs

### Pipeline Lifecycle Management
- **Generation**: Route to CI Agent for pipeline YAML generation
- **Publishing**: Commit pipelines to repositories
- **Execution**: Trigger pipeline runs (via CD Agent)

## API Endpoints

### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health with child agent status |

### Chat Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat` | POST | Main chat endpoint (routes to child agents) |
| `/v1/chat/stream` | POST | Streaming chat with SSE milestones |
| `/v1/chat/simple` | POST | Simple chat with auto-generated session |

### Repository Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/repositories` | GET | List repositories for a platform |
| `/v1/repositories/context` | GET | Get repository context URL |
| `/v1/repositories/branches` | GET | List branches for a repository |
| `/v1/repositories/files` | POST | Write file to repository |

### Pipeline Publishing

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/harness/pipelines` | POST | Publish pipeline to Harness |
| `/v1/azure-devops/pipelines` | POST | Publish pipeline to Azure DevOps |

## Request Format

### Chat Request

```json
{
    "session_id": "deploy_abc123",
    "message": "Generate a CI pipeline for my Python FastAPI service",
    "context": {
        "platform": "azure-devops",
        "deployment_target": "container-apps",
        "repository_url": "https://github.com/org/my-service.git",
        "entities": {
            "project_name": "quantnik-payment-service",
            "language": "python"
        }
    },
    "explicit_intent": "generate_ci_pipeline",
    "target_agent": "ci"
}
```

### Repository File Write Request

```json
{
    "platform": "azure-devops",
    "repository_url": "https://dev.azure.com/org/project/_git/repo",
    "branch": "main",
    "file_path": "azure-pipelines.yml",
    "content": "trigger:\n  - main\n...",
    "commit_message": "Add CI/CD pipeline configuration"
}
```

### Harness Pipeline Publish Request

```json
{
    "platform": "harness",
    "repository_url": "https://app.harness.io/account/xxx/org/yyy/project/zzz",
    "content": "pipeline:\n  name: my-pipeline\n  identifier: my_pipeline\n..."
}
```

## Response Format

### Chat Response

```json
{
    "session_id": "deploy_abc123",
    "message": "Generated azure-devops CI pipeline with 5 stages.",
    "status": "success",
    "nextagentflow": "confirmedGenerateCiPipeline",
    "data": {
        "intent": "generate_ci_pipeline",
        "entities": {
            "platform": "azure-devops",
            "pipeline_name": "quantnik-payment-service"
        },
        "artifact": {
            "path": "azure-pipelines.yml",
            "content": "trigger:\n  - main\n..."
        }
    },
    "suggested_actions": [
        {"action": "Publish pipeline to repository", "intent": "publish_pipeline", "agent": "deployment"},
        {"action": "Configure deployment environments", "intent": "configure_environments", "agent": "deployment"}
    ],
    "routed_to": "ci",
    "timestamp": "2026-05-04T10:30:00.000000"
}
```

### Repository File Write Response

```json
{
    "status": "success",
    "repositoryUrl": "https://dev.azure.com/org/project/_git/repo",
    "branch": "main",
    "filePath": "azure-pipelines.yml",
    "commitMessage": "Add CI/CD pipeline configuration",
    "commitSha": "abc123def456"
}
```

## Project Structure

```
quantnik-deployment-orchestrator/
├── app/
│   ├── main.py                    # FastAPI application
│   ├── core/
│   │   ├── config.py              # Configuration management
│   │   ├── logging.py             # Structured logging
│   │   └── security.py            # Authentication & authorization
│   ├── models/
│   │   ├── requests.py            # Request models (ChatRequest)
│   │   ├── responses.py           # Response models
│   │   ├── streaming.py           # SSE event models
│   │   └── repository_operations.py # Repository operation models
│   ├── agents/
│   │   ├── graph.py               # LangGraph state machine
│   │   ├── streaming_graph.py     # Streaming execution
│   │   └── intent_classifier.py   # LLM intent classification
│   ├── tools/
│   │   ├── agent_client.py        # HTTP client for child agents
│   │   └── repository_lookup.py   # Repository operations client
│   └── memory/
│       └── conversation_memory.py # Session memory management
├── tests/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development/production) | development |
| `PORT` | Server port | 8091 |
| `LOG_LEVEL` | Logging level | INFO |
| `GOOGLE_API_KEY` | Google AI API key for intent classification | - |
| `CI_AGENT_URL` | CI Agent service URL | http://localhost:8092 |
| `CD_AGENT_URL` | CD Agent service URL | http://localhost:8093 |
| `REPOSITORY_LOOKUP_URL` | Repository lookup service URL | - |
| `REPOSITORY_LOOKUP_API_KEY` | API key for repository operations | - |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins | * |
| `SSL_VERIFY` | Verify SSL certificates | true |

### Child Agent Configuration

Configure URLs for child agents in `.env`:

```env
CI_AGENT_URL=https://quantnik-ci-agent-204952354085.us-central1.run.app
CD_AGENT_URL=https://quantnik-cd-agent-204952354085.us-central1.run.app
```

## Supported Intents

| Intent | Description | Routes To |
|--------|-------------|-----------|
| `generate_ci_pipeline` | Generate CI/CD pipeline | CI Agent |
| `publish_pipeline` | Publish pipeline to repository | Repository Operations |
| `list_repositories` | List available repositories | Repository Operations |
| `list_branches` | List branches in repository | Repository Operations |
| `trigger_deployment` | Trigger deployment execution | CD Agent |
| `check_deployment_status` | Check deployment status | CD Agent |

## Orchestrator Graph Flow

```
        START
          │
          ▼
    ┌─────────────┐
    │  retrieve   │  ← Load session state & conversation history
    │   memory    │
    └─────────────┘
          │
          ▼
    ┌─────────────┐
    │  classify   │  ← LLM-driven intent classification
    │   intent    │    (or use explicit_intent/target_agent)
    └─────────────┘
          │
          ▼
    ┌─────────────┐
    │   route     │  ← Determine target agent (CI/CD)
    │   agent     │
    └─────────────┘
          │
          ▼
    ┌─────────────┐
    │   execute   │  ← Call child agent or repository operation
    │   action    │
    └─────────────┘
          │
          ▼
    ┌─────────────┐
    │  synthesize │  ← Build response from child results
    │  response   │
    └─────────────┘
          │
          ▼
    ┌─────────────┐
    │   update    │  ← Persist session state
    │   memory    │
    └─────────────┘
          │
          ▼
         END
```

## Setup

### 1. Install Dependencies

```bash
cd quantnik-deployment-orchestrator
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Run the Service

```bash
python run.py
```

## Docker

```bash
docker build -t quantnik-deployment-orchestrator .
docker run -p 8091:8091 --env-file .env quantnik-deployment-orchestrator
```

## Streaming (SSE)

The `/v1/chat/stream` endpoint returns Server-Sent Events with progress updates:

```
data: {"type": "milestone", "stage": "received", "title": "Request Received", "progress": 0.05}

data: {"type": "milestone", "stage": "classifying", "title": "Classifying Intent", "progress": 0.15}

data: {"type": "milestone", "stage": "routing", "title": "Routing to CI Agent", "progress": 0.25}

data: {"type": "milestone", "stage": "generating", "title": "Generating Pipeline", "progress": 0.5, "_forwarded_from": "ci"}

data: {"type": "milestone", "stage": "validating", "title": "Validating Output", "progress": 0.85, "_forwarded_from": "ci"}

data: {"type": "response", "session_id": "deploy_abc123", "status": "success", "routed_to": "ci"}
```

## Integration with QUANTNIK Platform

This service integrates with the QUANTNIK SDLC platform:

1. **SDLC Orchestrator**: Parent orchestrator that routes deployment intents
2. **CI Agent**: Pipeline generation service
3. **CD Agent**: Deployment execution service
4. **Repository Lookup Service**: Repository and branch management
5. **Auth Service**: JWT token validation for secure API access
6. **SDLC Frontend**: CI Pipeline Workspace UI

## See Also

- [QUANTNIK SDLC Orchestrator](../quantnik-sdlc-orchestrator) - Parent orchestrator
- [QUANTNIK CI Agent](../quantnik-ci-agent) - Pipeline generation service
- [QUANTNIK SDLC Frontend](../quantnik-sdlc) - CI Pipeline Workspace UI
- [QUANTNIK Auth Service](../quantnik-auth-service) - Authentication and authorization
