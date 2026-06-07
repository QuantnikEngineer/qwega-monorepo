# SDLC Orchestrator - API Curl Commands

Base URL: `http://localhost:8081`

## Health & Info

```bash
# Health Check
curl http://localhost:8081/health

# Connectivity Check (verify child orchestrator connections)
curl http://localhost:8081/health/connectivity

# Root Info
curl http://localhost:8081/

# Get All Orchestrator Capabilities
curl http://localhost:8081/v1/capabilities
```

## Chat Endpoints

### Standard Chat

```bash
# Basic chat request
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "Create a BRD from my meeting transcript"
  }'

# Chat with context
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "Generate user stories",
    "context": {
      "brd_link": "https://confluence.example.com/brd/123",
      "project_name": "MyProject"
    }
  }'

# Chat with explicit intent override
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "Generate test scripts",
    "explicit_intent": "generate_test_script"
  }'

# Chat with explicit orchestrator target
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "Generate test cases",
    "target_orchestrator": "test"
  }'

# Chat targeting planning orchestrator
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "Create user stories",
    "target_orchestrator": "planning"
  }'

# Chat targeting common integration orchestrator - Query knowledge base
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "Search the knowledge base for testing requirements",
    "context": {
      "query": "testing requirements authentication",
      "sdlc_phase": "testing",
      "top_k": 5
    },
    "explicit_intent": "context_enrich_query"
  }'

# Chat targeting common integration orchestrator - Submit feedback
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "Submit a correction",
    "context": {
      "feedback_type": "correction",
      "content": "The authentication should use OAuth 2.0",
      "artifact_type": "user_story",
      "sdlc_phase": "development"
    },
    "explicit_intent": "context_enrich_feedback"
  }'

# Chat targeting common integration orchestrator - Ingest website
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "Ingest documentation from our website",
    "context": {
      "source": "website",
      "urls": ["https://docs.example.com/api", "https://docs.example.com/guide"]
    },
    "explicit_intent": "context_enrich_ingest"
  }'

# Confirmation flow (after receiving suggested actions)
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "yes"
  }'

# Select option by number
curl -X POST http://localhost:8081/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_001",
    "message": "option 2"
  }'
```

### Simple Chat

```bash
# Auto-generates session ID
curl -X POST http://localhost:8081/v1/chat/simple \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you do?"}'
```

### Streaming Chat (SSE Milestones)

```bash
# Streaming with real-time milestones
curl -X POST http://localhost:8081/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "sess_001",
    "message": "Create a BRD"
  }' --no-buffer

# Streaming for test cases
curl -X POST http://localhost:8081/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "sess_001",
    "message": "Generate test cases"
  }' --no-buffer

# Streaming for test script generation
curl -X POST http://localhost:8081/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "sess_001",
    "message": "Generate test scripts",
    "explicit_intent": "generate_test_script"
  }' --no-buffer

# Streaming for knowledge base query
curl -X POST http://localhost:8081/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "sess_001",
    "message": "Search the knowledge base",
    "context": {
      "query": "authentication requirements",
      "top_k": 5
    },
    "explicit_intent": "context_enrich_query"
  }' --no-buffer
```

## Legacy Endpoint

```bash
# Legacy analyze - BRD creation
curl -X POST http://localhost:8081/api/v1/prompt/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Create BRD",
    "nextagentflow": "confirmedCreateBrd"
  }'

# Legacy analyze - User stories
curl -X POST http://localhost:8081/api/v1/prompt/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Generate user stories",
    "brd_document_uri": "https://confluence.example.com/brd/123",
    "nextagentflow": "confirmedCreateUserStory"
  }'

# Legacy analyze - Test cases
curl -X POST http://localhost:8081/api/v1/prompt/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Generate test cases",
    "create_user_story_text": "As a user...",
    "nextagentflow": "confirmedUserStoryToTestScenario"
  }'

# Legacy analyze - Test script generation
curl -X POST http://localhost:8081/api/v1/prompt/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Generate test scripts",
    "test_cases": "[{\"test_case\": \"...\"}]",
    "framework_type": "Selenium",
    "language": "Java",
    "nextagentflow": "confirmedTestCaseToTestScript"
  }'

# Legacy analyze - Query knowledge base
curl -X POST http://localhost:8081/api/v1/prompt/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Search knowledge base for API documentation",
    "nextagentflow": "confirmedContextEnrichQuery"
  }'
```

## Memory Management

```bash
# Get session memory
curl http://localhost:8081/v1/memory/sess_001

# Get conversation history
curl "http://localhost:8081/v1/memory/sess_001/history?limit=20"

# Clear session memory
curl -X DELETE http://localhost:8081/v1/memory/sess_001
```

---

## Request & Response Structures

### ChatRequest (POST /v1/chat)

```json
{
  "session_id": "string (required)",
  "message": "string (required)",
  "context": { },
  "history": [
    { "role": "user|assistant", "content": "string" }
  ],
  "explicit_intent": "string (optional) - e.g., create_brd, generate_test_script",
  "target_orchestrator": "string (optional) - planning|test"
}
```

### ChatResponse (POST /v1/chat)

```json
{
  "session_id": "string",
  "message": "string",
  "status": "success|error|pending",
  "job_id": "string|null",
  "nextagentflow": "string|null",
  "data": { },
  "push_results": { },
  "suggested_actions": [
    {
      "action": "string",
      "intent": "string|null",
      "orchestrator": "string|null",
      "confidence": 1.0
    }
  ],
  "metadata": { },
  "routed_to": "planning|test|null",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### StreamingResponse (POST /v1/chat/stream - final event)

```json
{
  "type": "response",
  "session_id": "string",
  "message": "string",
  "status": "success|error",
  "job_id": "string|null",
  "nextagentflow": "string|null",
  "data": { },
  "push_results": { },
  "suggested_actions": [ ],
  "routed_to": "planning|test|null",
  "total_duration_ms": 1234
}
```

### LegacyAnalyzeRequest (POST /api/v1/prompt/analyze)

```json
{
  "query_text": "string (required)",
  "nextagentflow": "string|null",
  "brd_document_uri": "string|null",
  "create_user_story_text": "string|array|null",
  "scenario_types": "string|null",
  "test_scenarios": "string|null",
  "test_cases": "string|null",
  "framework_type": "string|null",
  "language": "string|null",
  "script_generation_type": "string|null"
}
```

### LegacyAnalyzeResponse (POST /api/v1/prompt/analyze)

```json
{
  "success": true,
  "result": { },
  "message": "string|null",
  "error": "string|null",
  "nextagentflow": "string|null",
  "next_suggested_action": "string|null",
  "nextuserflow": "string|null",
  "updatedNextQuery": "string|null",
  "routed_to": "planning|test|null"
}
```

### HealthResponse (GET /health)

```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "service": "Wega SDLC Orchestrator",
  "version": "1.0.0",
  "components": {
    "llm": "healthy",
    "memory": "healthy"
  },
  "child_orchestrators": {
    "planning": "healthy|unhealthy",
    "test": "healthy|unhealthy",
    "common_integration": "healthy|unhealthy"
  }
}
```

### CapabilitiesResponse (GET /v1/capabilities)

```json
{
  "orchestrators": [
    {
      "name": "planning",
      "description": "Handles BRD creation, user stories, and validation",
      "intents": ["create_brd", "create_user_story", "validate_user_story", "create_user_manual", "brd_summary"],
      "keywords": ["brd", "user story", "requirement"],
      "url": "https://...",
      "status": "healthy"
    },
    {
      "name": "test",
      "description": "Handles test case,test cases and test script generation",
      "intents": ["generate_test_cases", "generate_test_script"],
      "keywords": ["test", "test cases", "script"],
      "url": "https://...",
      "status": "healthy"
    },
    {
      "name": "common_integration",
      "description": "Handles context enrichment: upload, ingest, feedback, query",
      "intents": ["context_enrich_upload", "context_enrich_ingest", "context_enrich_feedback", "context_enrich_query"],
      "keywords": ["upload", "ingest", "feedback", "query", "knowledge base"],
      "url": "https://...",
      "status": "healthy"
    }
  ],
  "total_intents": 12,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

---

## Streaming Response Format

The `/v1/chat/stream` endpoint returns Server-Sent Events (SSE):

### Milestone Events

```
data: {"type": "milestone", "stage": "received", "title": "Request Received", "progress": 0.05, "icon": "📥", "animation": "fade"}

data: {"type": "milestone", "stage": "thinking", "title": "Thinking", "progress": 0.15, "icon": "🤔", "animation": "pulse"}

data: {"type": "milestone", "stage": "analyzing", "title": "Analyzing Intent", "progress": 0.25, "icon": "🔍", "animation": "spin", "details": {"intent": "generate_test_script", "confidence": 0.95}}

data: {"type": "milestone", "stage": "routing", "title": "Routing to Test", "progress": 0.35, "icon": "🧪", "animation": "slide", "details": {"target": "test"}}

data: {"type": "milestone", "stage": "calling_agent", "title": "Calling Test Orchestrator", "progress": 0.60, "icon": "📡", "animation": "pulse"}

data: {"type": "milestone", "stage": "processing", "title": "Processing Response", "progress": 0.80, "icon": "⚙️", "animation": "spin"}

data: {"type": "milestone", "stage": "complete", "title": "Complete", "progress": 1.0, "icon": "✅", "animation": "fade"}
```

### Final Response Event

```
data: {"type": "response", "session_id": "sess_001", "message": "Test scripts generated successfully.", "status": "success", "job_id": "job_123", "nextagentflow": "confirmedTestCaseToTestScript", "data": {"scripts": [...]}, "push_results": {"repo": "...", "branch": "...", "commit": "..."}, "suggested_actions": [{"action": "View generated scripts", "intent": null}], "routed_to": "test", "total_duration_ms": 5432}
```

### Error Event

```
data: {"type": "error", "stage": "error", "title": "Error Occurred", "message": "Connection timeout", "icon": "❌", "animation": "none"}
```

---

## Supported Intents

| Orchestrator | Intent | Description |
|--------------|--------|-------------|
| **Planning** | `create_brd` | Create BRD from transcript |
| **Planning** | `create_user_story` | Generate user stories from BRD |
| **Planning** | `validate_user_story` | Validate user stories against BRD |
| **Planning** | `create_user_manual` | Create user manual |
| **Planning** | `brd_summary` | Get BRD summary |
| **Test** | `generate_test_cases` | Generate test cases from user stories |
| **Test** | `generate_test_script` | Generate automated test scripts (Selenium, Playwright) |
| **Test** | `generate_test_data` | Generate test data from test cases |
| **Common Integration** | `context_enrich_upload` | Upload documents to knowledge base |
| **Common Integration** | `context_enrich_ingest` | Ingest content from websites, SharePoint, repos |
| **Common Integration** | `context_enrich_feedback` | Submit feedback (ratings, corrections, preferences) |
| **Common Integration** | `context_enrich_query` | Query the knowledge base |

---

## nextagentflow Mapping

| Intent | nextagentflow value |
|--------|---------------------|
| `create_brd` | `confirmedCreateBrd` |
| `create_user_story` | `confirmedCreateUserStory` |
| `validate_user_story` | `confirmedValidateUserStory` |
| `create_user_manual` | `confirmedCreateUserManual` |
| `brd_summary` | `confirmedBrdSummary` |
| `generate_test_cases` | `confirmedUserStoryToTestScenario` |
| `generate_test_script` | `confirmedTestCaseToTestScript` |
| `context_enrich_upload` | `confirmedContextEnrichUpload` |
| `context_enrich_ingest` | `confirmedContextEnrichIngest` |
| `context_enrich_feedback` | `confirmedContextEnrichFeedback` |
| `context_enrich_query` | `confirmedContextEnrichQuery` |
