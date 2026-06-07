# Test Orchestrator - API Reference

Base URL: `https://wega-test-orchestrator-204952354085.us-central1.run.app`

---

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Simple health check |
| GET | `/health/detailed` | Detailed health check with components |
| GET | `/` | Root endpoint - service info |
| POST | `/v1/chat` | Main chat endpoint |
| POST | `/v1/chat/simple` | Simple chat with auto-generated session |
| POST | `/v1/chat/stream` | Streaming chat with SSE milestones |
| POST | `/api/v1/prompt/analyze` | Legacy endpoint (backward compatibility) |
| GET | `/v1/memory/{session_id}` | Get session memory |
| GET | `/v1/memory/{session_id}/history` | Get conversation history |
| DELETE | `/v1/memory/{session_id}` | Clear session memory |

---

## Health & Info Endpoints

### Health Check
```bash
curl https://wega-test-orchestrator-204952354085.us-central1.run.app/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "Wega Test Orchestrator"
}
```

### Detailed Health Check
```bash
curl https://wega-test-orchestrator-204952354085.us-central1.run.app/health/detailed
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "service": "Wega Test Orchestrator",
  "version": "1.0.0",
  "components": {
    "orchestrator": "healthy",
    "memory": "healthy",
    "llm": "healthy"
  }
}
```

### Root Endpoint
```bash
curl https://wega-test-orchestrator-204952354085.us-central1.run.app/
```

**Response:**
```json
{
  "service": "Wega Test Orchestrator",
  "version": "1.0.0",
  "status": "running",
  "endpoints": {
    "chat": "/v1/chat",
    "chat_stream": "/v1/chat/stream",
    "legacy": "/api/v1/prompt/analyze",
    "memory": "/v1/memory/{session_id}",
    "health": "/health"
  }
}
```

---

## Chat Endpoints

### Request Model: ChatRequest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | Yes | Unique session identifier |
| `message` | string | Yes | User's natural language message |
| `context` | object | No | Additional context (user_stories, test_cases, etc.) |
| `history` | array | No | Previous messages [{role, content, timestamp, metadata}] |
| `explicit_intent` | string | No | Explicit intent override |

### Response Model: ChatResponse

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `message` | string | Response message for the user |
| `status` | string | `success`, `error`, or `pending` |
| `nextagentflow` | string | Next agent flow identifier for frontend |
| `data` | object | Structured response data (see below) |
| `suggested_actions` | array | Suggested next actions [{action, intent, confidence}] |
| `metadata` | object | Execution metadata |
| `timestamp` | string | ISO timestamp |

### Response Data Object

| Field | Type | Description |
|-------|------|-------------|
| `intent` | string | Detected intent |
| `entities` | object | Extracted entities |
| `action_results` | array | Results from each executed action |
| `test_scripts` | object | Generated test scripts (for script generation) |
| `push_results` | object | Repository push results (for script generation) |
| `job_id` | string | Async job ID (if applicable) |
| `poll_url` | string | URL to poll for job status |
| `total` | number | Total count (scenarios/scripts generated) |
| `message` | string | Additional message from child agent |

---

### POST /v1/chat - Main Chat Endpoint

#### Generate Test Scenarios from User Stories

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_001",
    "message": "Generate test scenarios from user stories",
    "context": {
      "user_stories": "Epic: User Authentication\n- As a user, I want to login with email and password\n- As a user, I want to reset my password"
    }
  }'
```

#### Generate Test Scenarios with Scenario Types

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_001",
    "message": "Generate test scenarios",
    "context": {
      "user_stories": "As a user, I want to login...",
      "scenario_types": ["positive", "negative", "edge_case"]
    }
  }'
```

#### Generate Test Scripts - Selenium BDD Java

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_001",
    "message": "Generate test scripts",
    "context": {
      "test_cases": "TC001: Verify successful login with valid credentials\nTC002: Verify error message for invalid password",
      "framework_type": "Selenium BDD",
      "language": "Java",
      "script_generation_type": "Greenfield"
    }
  }'
```

**Response:**
```json
{
  "session_id": "sess_test_001",
  "message": "I've generated your test scripts using Selenium BDD in Java.",
  "status": "success",
  "nextagentflow": null,
  "data": {
    "intent": "generate_test_script",
    "entities": {},
    "action_results": [...],
    "test_scripts": {
      "files": [...],
      "summary": "Generated 2 test scripts"
    },
    "push_results": {
      "status": "success",
      "commit_sha": "abc123",
      "branch": "feature/test-scripts"
    }
  },
  "suggested_actions": [
    {"action": "Generate more scripts", "intent": "generate_test_script"},
    {"action": "Review generated scripts", "intent": null}
  ],
  "metadata": {...},
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### Generate Test Scripts - Playwright TypeScript

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_001",
    "message": "Generate Playwright test scripts",
    "context": {
      "test_cases": "TC001: Verify login functionality",
      "framework_type": "Playwright",
      "language": "TypeScript",
      "script_generation_type": "Greenfield"
    }
  }'
```

#### Generate Test Scripts - Selenium TestNG Python

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_001",
    "message": "Create automation scripts",
    "context": {
      "test_cases": "TC001: Verify user registration",
      "framework_type": "Selenium TestNG",
      "language": "Python",
      "script_generation_type": "Brownfield"
    }
  }'
```

#### Chat with Explicit Intent

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_001",
    "message": "Process this request",
    "explicit_intent": "generate_test_cases"
  }'
```

#### Confirmation Flow

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_001",
    "message": "yes, proceed"
  }'
```

---

### POST /v1/chat/simple - Simple Chat

Auto-generates session ID.

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat/simple \
  -H "Content-Type: application/json" \
  -d '{"message": "What testing features do you support?"}'
```

---

### POST /v1/chat/stream - Streaming Chat (SSE)

Returns Server-Sent Events with real-time milestone updates.

#### Streaming Test Scenario Generation

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "sess_test_001",
    "message": "Generate test scenarios",
    "context": {
      "user_stories": "As a user, I want to login..."
    }
  }' --no-buffer
```

#### Streaming Test Script Generation

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "sess_test_001",
    "message": "Generate Selenium test scripts",
    "context": {
      "test_cases": "TC001: Verify login",
      "framework_type": "Selenium BDD",
      "language": "Java"
    }
  }' --no-buffer
```

#### SSE Event Types

**Milestone Event:**
```json
{
  "type": "milestone",
  "stage": "analyzing",
  "title": "Analyzing Intent",
  "description": "Detected intent: Generate Test Script",
  "progress": 0.25,
  "icon": "🔍",
  "animation": "spin",
  "details": {"intent": "generate_test_script", "confidence": 0.95},
  "timestamp": "2024-01-15T10:30:00.000Z",
  "duration_hint_ms": 2000
}
```

**Child Agent Event (when streaming enabled):**
```json
{
  "type": "milestone",
  "stage": "executing",
  "title": "Generating Scripts",
  "source_agent": "test_script_agent",
  "progress": 0.6,
  "icon": "💻"
}
```

**Final Response:**
```json
{
  "type": "response",
  "session_id": "sess_test_001",
  "message": "Generated test scripts successfully",
  "status": "success",
  "nextagentflow": null,
  "data": {
    "intent": "generate_test_script",
    "entities": {},
    "action_results": [...],
    "job_id": "job_123",
    "poll_url": "https://...",
    "total": 5,
    "message": "Generated 5 test scripts",
    "test_scripts": {...},
    "push_results": {...}
  },
  "suggested_actions": [...],
  "total_duration_ms": 15000
}
```

**Error Event:**
```json
{
  "type": "error",
  "stage": "error",
  "title": "Error Occurred",
  "message": "Test Script agent error: Connection timeout",
  "icon": "❌",
  "source_agent": "test_script_agent"
}
```

#### Milestone Stages

| Stage | Progress | Description |
|-------|----------|-------------|
| `received` | 0.05 | Request received |
| `thinking` | 0.15 | Understanding requirements |
| `analyzing` | 0.25 | Analyzing intent |
| `planning` | 0.35 | Planning test generation |
| `executing` | 0.40-0.80 | Executing actions |
| `calling_agent` | 0.55-0.60 | Calling child agent |
| `processing` | 0.85 | Processing response |
| `synthesizing` | 0.92 | Preparing final response |
| `complete` | 1.0 | Completed |
| `error` | 1.0 | Error occurred |

---

## Legacy Endpoint

### POST /api/v1/prompt/analyze

For backward compatibility with existing integrations.

#### Request Model: LegacyAnalyzeRequest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query_text` | string | Yes | User query text |
| `nextagentflow` | string | No | Agent flow identifier |
| `create_user_story_text` | string/array | No | User stories for scenario generation |
| `scenario_types` | string | No | Comma-separated scenario types |
| `test_scenarios` | string | No | Test scenarios |
| `test_case_format` | string | No | Test case format |
| `test_cases` | string | No | Test cases for script generation |
| `framework_type` | string | No | Test framework |
| `language` | string | No | Programming language |
| `script_generation_type` | string | No | Greenfield or Brownfield |
| `input_test_text` | string | No | Input test text |
| `user_story_name` | string | No | User story name |
| `instructions` | string | No | Additional instructions |

#### Response Model: LegacyAnalyzeResponse

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the request succeeded |
| `result` | object | Result data |
| `message` | string | Response message |
| `error` | string | Error message if failed |
| `nextagentflow` | string | Next agent flow |
| `next_suggested_action` | string | Suggested action |
| `nextuserflow` | string | Next user flow |
| `updatedNextQuery` | string | Updated query |

#### Generate Test Scenarios (Legacy)

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/api/v1/prompt/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Generate test scenarios",
    "create_user_story_text": "As a user, I want to login with email and password",
    "nextagentflow": "confirmedUserStoryToTestScenario"
  }'
```

#### Generate Test Scripts (Legacy)

```bash
curl -X POST https://wega-test-orchestrator-204952354085.us-central1.run.app/api/v1/prompt/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Generate test scripts",
    "test_cases": "TC001: Verify login functionality",
    "framework_type": "Selenium BDD",
    "language": "Java",
    "script_generation_type": "Greenfield",
    "nextagentflow": "confirmedTestCaseToTestScript"
  }'
```

**Response:**
```json
{
  "success": true,
  "result": {
    "intent": "generate_test_script",
    "entities": {},
    "action_results": [...],
    "test_scripts": {...},
    "push_results": {...}
  },
  "message": "Generated test scripts successfully",
  "error": null,
  "nextagentflow": "confirmedTestCaseToTestScript",
  "next_suggested_action": "Review generated scripts",
  "nextuserflow": "",
  "updatedNextQuery": ""
}
```

---

## Memory Management Endpoints

### GET /v1/memory/{session_id}

Get session memory state.

```bash
curl https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/memory/sess_test_001
```

**Response:**
```json
{
  "session_id": "sess_test_001",
  "message_count": 5,
  "entities": {
    "framework_type": "Selenium BDD",
    "language": "Java"
  },
  "context": {
    "suggested_actions": [...]
  },
  "last_activity": "2024-01-15T10:30:00.000Z"
}
```

### GET /v1/memory/{session_id}/history

Get conversation history.

```bash
curl "https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/memory/sess_test_001/history?limit=20"
```

**Response:**
```json
{
  "session_id": "sess_test_001",
  "messages": [
    {"role": "user", "content": "Generate test scripts", "timestamp": "..."},
    {"role": "assistant", "content": "I've generated...", "timestamp": "..."}
  ],
  "total": 5
}
```

### DELETE /v1/memory/{session_id}

Clear session memory.

```bash
curl -X DELETE https://wega-test-orchestrator-204952354085.us-central1.run.app/v1/memory/sess_test_001
```

**Response:**
```json
{
  "status": "cleared",
  "session_id": "sess_test_001"
}
```

---

## Reference Tables

### Supported Intents

| Intent | Description |
|--------|-------------|
| `generate_test_cases` | Generate test cases from user stories |
| `generate_test_script` | Generate automated test scripts from test cases |
| `general_question` | General questions about testing |
| `confirmation` | Confirmation of previous action |
| `unknown` | Unable to determine intent |

### Supported Frameworks & Languages

| Framework | Languages |
|-----------|-----------|
| Selenium BDD | Java, Python, JavaScript, C# |
| Selenium TestNG | Java, Python |
| Playwright | TypeScript, JavaScript, Python, C# |

### Script Generation Types

| Type | Description |
|------|-------------|
| `Greenfield` | New project, generate from scratch |
| `Brownfield` | Existing project, follow existing patterns |

### nextagentflow Values

| Value | Description |
|-------|-------------|
| `confirmedUserStoryToTestScenario` | User story to test scenario flow |
| `confirmedTestCaseToTestScript` | Test case to test script flow |

---

## Configuration - Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_CHILD_AGENT_STREAMING` | `true` | Enable SSE streaming from child agents |
| `TEST_SCENARIO_AGENT_URL` | - | URL of the Test Scenario Generator Agent |
| `TEST_SCRIPT_AGENT_URL` | - | URL of the Test Script Generator Agent |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `REQUEST_TIMEOUT` | `600` | Request timeout in seconds (10 minutes) |
| `AGENT_CALL_TIMEOUT` | `600` | Timeout for child agent HTTP calls in seconds |
| `SSL_VERIFY` | `true` | Enable/disable SSL verification |

### Child Agent Streaming Endpoints

When streaming is enabled, the orchestrator connects to child agent SSE endpoints:
- Test Scenario Agent: `{TEST_SCENARIO_AGENT_URL}/api/v1/prompt/analyze/stream`
- Test Script Agent: `{TEST_SCRIPT_AGENT_URL}/convert`

If streaming is disabled, the orchestrator falls back to regular HTTP POST requests.
