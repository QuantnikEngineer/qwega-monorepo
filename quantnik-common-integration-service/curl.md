# cURL Commands for Quantnik Common Integration Service

Base URL: `http://localhost:8002`

---

## Health Endpoints

### Simple Health Check
```bash
curl -X GET http://localhost:8002/health
```

**Response:**
```json
{
    "status": "healthy",
    "service": "Quantnik Common Integration Service"
}
```

### Detailed Health Check
```bash
curl -X GET http://localhost:8002/health/detailed
```

**Response:**
```json
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00.000000",
    "service": "Quantnik Common Integration Service",
    "version": "1.0.0",
    "components": {
        "orchestrator": "healthy",
        "memory": "healthy",
        "llm": "healthy",
        "rag_agent": "healthy"
    }
}
```

### Root Endpoint
```bash
curl -X GET http://localhost:8002/
```

**Response:**
```json
{
    "service": "Quantnik Common Integration Service",
    "version": "1.0.0",
    "docs": "/docs",
    "health": "/health"
}
```

---

## Chat Endpoints

### 1. Main Chat Endpoint (Non-Streaming)

#### Query Knowledge Base
```bash
curl -X POST http://localhost:8002/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_001",
    "message": "What are the testing requirements for user authentication?",
    "context": {
        "query": "testing requirements user authentication",
        "sdlc_phase": "testing",
        "top_k": 5,
        "include_sources": true
    },
    "explicit_intent": "context_enrich_query",
    "selected_model": "gemini-2.0-flash"
}'
```

**Response:**
```json
{
    "session_id": "sess_test_001",
    "message": "Based on the knowledge base, the testing requirements for user authentication include...",
    "status": "success",
    "nextagentflow": "confirmedContextEnrichQuery",
    "data": {
        "intent": "context_enrich_query",
        "entities": {},
        "action_results": [
            {
                "action": "execute_query",
                "success": true,
                "result": {
                    "query": "testing requirements user authentication",
                    "answer": "The testing requirements include...",
                    "sources": [
                        {
                            "chunk_id": "chunk_123",
                            "filename": "requirements.pdf",
                            "sdlc_phase": "testing",
                            "score": 0.92,
                            "content": "Authentication testing should cover...",
                            "criticality": "critical"
                        }
                    ],
                    "guardrail_passed": true,
                    "retrieval_count": 5,
                    "sdlc_phase": "testing"
                }
            }
        ]
    },
    "suggested_actions": [
        {"action": "Ask another question", "intent": "context_enrich_query"},
        {"action": "Upload more documents", "intent": "context_enrich_upload"}
    ],
    "metadata": {
        "start_time": "2024-01-15T10:30:00.000000",
        "explicit_intent": "context_enrich_query",
        "selected_model": "gemini-2.0-flash"
    },
    "timestamp": "2024-01-15T10:30:05.000000"
}
```

#### Submit Feedback (Correction)
```bash
curl -X POST http://localhost:8002/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_002",
    "message": "Submit a correction for the authentication flow",
    "context": {
        "feedback_type": "correction",
        "content": "The authentication flow should use OAuth 2.0, not basic auth",
        "artifact_type": "user_story",
        "sdlc_phase": "development",
        "agent_name": "user_story_generator"
    },
    "explicit_intent": "context_enrich_feedback",
    "selected_model": "gemini-2.0-flash"
}'
```

**Response:**
```json
{
    "session_id": "sess_test_002",
    "message": "Feedback submitted successfully and indexed to knowledge base.",
    "status": "success",
    "nextagentflow": "confirmedContextEnrichFeedback",
    "data": {
        "intent": "context_enrich_feedback",
        "entities": {},
        "action_results": [
            {
                "action": "execute_feedback",
                "success": true,
                "result": {
                    "id": "fb_abc123",
                    "feedback_type": "correction",
                    "indexed": true,
                    "message": "Feedback submitted successfully"
                }
            }
        ]
    },
    "suggested_actions": [
        {"action": "Submit more feedback", "intent": "context_enrich_feedback"},
        {"action": "Query the knowledge base", "intent": "context_enrich_query"}
    ],
    "metadata": {},
    "timestamp": "2024-01-15T10:31:00.000000"
}
```

#### Submit Rating Feedback
```bash
curl -X POST http://localhost:8002/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_003",
    "message": "Rate the generated output",
    "context": {
        "feedback_type": "rating",
        "rating": "positive",
        "artifact_type": "test_case",
        "agent_name": "test_case_generator",
        "ref_doc_id": "doc_xyz789"
    },
    "explicit_intent": "context_enrich_feedback"
}'
```

**Response:**
```json
{
    "session_id": "sess_test_003",
    "message": "Rating feedback recorded.",
    "status": "success",
    "nextagentflow": "confirmedContextEnrichFeedback",
    "data": {
        "intent": "context_enrich_feedback",
        "action_results": [
            {
                "action": "execute_feedback",
                "success": true,
                "result": {
                    "id": "fb_def456",
                    "feedback_type": "rating",
                    "indexed": false,
                    "message": "Rating recorded"
                }
            }
        ]
    },
    "suggested_actions": [],
    "timestamp": "2024-01-15T10:32:00.000000"
}
```

#### Ingest Website Content
```bash
curl -X POST http://localhost:8002/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_004",
    "message": "Ingest content from our documentation website",
    "context": {
        "source": "website",
        "urls": [
            "https://docs.example.com/api-guide",
            "https://docs.example.com/user-manual"
        ]
    },
    "explicit_intent": "context_enrich_ingest",
    "selected_model": "gemini-2.0-flash"
}'
```

**Response:**
```json
{
    "session_id": "sess_test_004",
    "message": "Successfully ingested 2 documents from website.",
    "status": "success",
    "nextagentflow": "confirmedContextEnrichIngest",
    "data": {
        "intent": "context_enrich_ingest",
        "action_results": [
            {
                "action": "execute_ingest",
                "success": true,
                "result": {
                    "source": "website",
                    "documents": [
                        {
                            "id": "doc_001",
                            "name": "api-guide",
                            "status": "pending",
                            "message": "Queued for processing"
                        },
                        {
                            "id": "doc_002",
                            "name": "user-manual",
                            "status": "pending",
                            "message": "Queued for processing"
                        }
                    ],
                    "skipped": [],
                    "message": "Ingestion started for 2 URLs"
                }
            }
        ]
    },
    "suggested_actions": [
        {"action": "Query the knowledge base", "intent": "context_enrich_query"},
        {"action": "Ingest more content", "intent": "context_enrich_ingest"}
    ],
    "timestamp": "2024-01-15T10:33:00.000000"
}
```

#### Ingest Repository Content
```bash
curl -X POST http://localhost:8002/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_005",
    "message": "Ingest code from our GitHub repository",
    "context": {
        "source": "repo",
        "repo_url": "https://github.com/org/project",
        "branch": "main",
        "path_filter": "docs/**/*.md",
        "token": "ghp_xxxxxxxxxxxx"
    },
    "explicit_intent": "context_enrich_ingest"
}'
```

**Response:**
```json
{
    "session_id": "sess_test_005",
    "message": "Repository ingestion started.",
    "status": "success",
    "nextagentflow": "confirmedContextEnrichIngest",
    "data": {
        "intent": "context_enrich_ingest",
        "action_results": [
            {
                "action": "execute_ingest",
                "success": true,
                "result": {
                    "source": "repo",
                    "documents": [
                        {
                            "id": "doc_003",
                            "name": "github.com/org/project",
                            "status": "pending",
                            "message": "Repository queued for processing"
                        }
                    ],
                    "skipped": [],
                    "message": "Repository ingestion initiated"
                }
            }
        ]
    },
    "timestamp": "2024-01-15T10:34:00.000000"
}
```

#### Ingest SharePoint Content
```bash
curl -X POST http://localhost:8002/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_006",
    "message": "Ingest documents from SharePoint",
    "context": {
        "source": "sharepoint",
        "link": "https://company.sharepoint.com/sites/project/docs",
        "token": "YOUR_TOKEN_HERE"
    },
    "explicit_intent": "context_enrich_ingest"
}'
```

#### Ingest Agent Output
```bash
curl -X POST http://localhost:8002/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_test_007",
    "message": "Index generated user stories",
    "context": {
        "source": "agent_output",
        "agent_name": "user_story_generator",
        "source_url": "https://app.example.com/session/123",
        "content": "As a user, I want to login with SSO so that I can access the system securely.",
        "title": "SSO Login User Story",
        "artifact_type": "user_story",
        "sdlc_phase": "requirements"
    },
    "explicit_intent": "context_enrich_ingest"
}'
```

---

### 2. Simple Chat Endpoint (Auto-generated Session)

```bash
curl -X POST http://localhost:8002/v1/chat/simple \
  -H "Content-Type: application/json" \
  -d '"What can you help me with?"'
```

**Response:**
```json
{
    "session_id": "sess_a1b2c3d4e5f6",
    "message": "I can help you with the following knowledge base operations:\n\n**Upload Documents:** Upload files to the knowledge base for indexing.\n\n**Ingest Content:** Ingest from websites, SharePoint, repositories, or agent outputs.\n\n**Submit Feedback:** Provide ratings, corrections, or domain preferences.\n\n**Query Knowledge Base:** Search for information in the knowledge base.\n\nWhat would you like to do?",
    "status": "success",
    "suggested_actions": [
        {"action": "Upload documents", "intent": "context_enrich_upload"},
        {"action": "Ingest content", "intent": "context_enrich_ingest"},
        {"action": "Submit feedback", "intent": "context_enrich_feedback"},
        {"action": "Query knowledge base", "intent": "context_enrich_query"}
    ],
    "timestamp": "2024-01-15T10:35:00.000000"
}
```

---

### 3. Streaming Chat Endpoint (SSE)

```bash
curl -X POST http://localhost:8002/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "session_id": "sess_stream_001",
    "message": "Query the knowledge base for API documentation",
    "context": {
        "query": "API documentation endpoints",
        "top_k": 5
    },
    "explicit_intent": "context_enrich_query",
    "selected_model": "gemini-2.0-flash"
}'
```

**Response (SSE Stream):**
```
data: {"type": "milestone", "stage": "received", "title": "Request Received", "message": "Processing request for session sess_stream_001", "icon": "📥", "progress": 0.1, "timestamp": "2024-01-15T10:36:00.000000"}

data: {"type": "milestone", "stage": "thinking", "title": "Analyzing Request", "message": "Understanding: Query the knowledge base for API documen...", "icon": "🤔", "progress": 0.2, "timestamp": "2024-01-15T10:36:00.500000"}

data: {"type": "milestone", "stage": "analyzing", "title": "Intent Classified", "message": "Detected intent: context_enrich_query", "icon": "🎯", "progress": 0.3, "data": {"intent": "context_enrich_query", "confidence": 1.0}, "timestamp": "2024-01-15T10:36:01.000000"}

data: {"type": "milestone", "stage": "executing", "title": "Querying Knowledge Base", "message": "Searching knowledge base for relevant information", "icon": "🔍", "progress": 0.5, "timestamp": "2024-01-15T10:36:01.500000"}

data: {"type": "complete", "session_id": "sess_stream_001", "message": "Found 5 relevant documents about API documentation...", "status": "success", "data": {"intent": "context_enrich_query", "entities": {}, "action_results": [{"action": "execute_query", "success": true, "result": {"query": "API documentation endpoints", "answer": "...", "sources": [...], "retrieval_count": 5}}]}, "suggested_actions": [{"action": "Ask another question", "intent": "context_enrich_query"}], "metadata": {"start_time": "2024-01-15T10:36:00.000000", "end_time": "2024-01-15T10:36:05.000000", "selected_model": "gemini-2.0-flash"}, "timestamp": "2024-01-15T10:36:05.000000"}

```

---

### 4. File Upload (Multipart Form Data)

```bash
curl -X POST http://localhost:8002/v1/chat \
  -F "session_id=sess_upload_001" \
  -F "message=Upload these documents to the knowledge base" \
  -F "explicit_intent=context_enrich_upload" \
  -F "selected_model=gemini-2.0-flash" \
  -F "files=@/path/to/document1.pdf" \
  -F "files=@/path/to/document2.docx"
```

**Response:**
```json
{
    "session_id": "sess_upload_001",
    "message": "Successfully uploaded 2 documents.",
    "status": "success",
    "nextagentflow": "confirmedContextEnrichUpload",
    "data": {
        "intent": "context_enrich_upload",
        "action_results": [
            {
                "action": "execute_upload",
                "success": true,
                "result": {
                    "documents": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "filename": "document1.pdf",
                            "file_type": "application/pdf",
                            "file_size_bytes": 102400,
                            "status": "pending",
                            "message": "Queued for processing"
                        },
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440001",
                            "filename": "document2.docx",
                            "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "file_size_bytes": 51200,
                            "status": "pending",
                            "message": "Queued for processing"
                        }
                    ],
                    "skipped": [],
                    "message": "2 documents uploaded successfully"
                }
            }
        ]
    },
    "suggested_actions": [
        {"action": "Query the knowledge base", "intent": "context_enrich_query"},
        {"action": "Upload more documents", "intent": "context_enrich_upload"}
    ],
    "timestamp": "2024-01-15T10:37:00.000000"
}
```

---

### 5. File Upload with Streaming

```bash
curl -X POST http://localhost:8002/v1/chat/stream \
  -H "Accept: text/event-stream" \
  -F "session_id=sess_upload_stream_001" \
  -F "message=Upload document" \
  -F "explicit_intent=context_enrich_upload" \
  -F "files=@/path/to/document.pdf"
```

---

## Legacy Endpoint

### Analyze Prompt (Backward Compatibility)

```bash
curl -X POST http://localhost:8002/api/v1/prompt/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "Query the knowledge base for testing guidelines",
    "nextagentflow": "context_enrich_query",
    "selected_model": "gemini-2.0-flash"
}'
```

**Response:**
```json
{
    "success": true,
    "result": {
        "intent": "context_enrich_query",
        "entities": {},
        "action_results": [...]
    },
    "message": "Based on the knowledge base...",
    "error": null,
    "nextagentflow": "confirmedContextEnrichQuery",
    "next_suggested_action": "Ask another question",
    "nextuserflow": null,
    "updatedNextQuery": null
}
```

---

## Memory Endpoints

### Get Session Memory

```bash
curl -X GET http://localhost:8002/v1/memory/sess_test_001
```

**Response:**
```json
{
    "session_id": "sess_test_001",
    "message_count": 4,
    "entities": {},
    "last_intent": "context_enrich_query",
    "context": {}
}
```

### Get Conversation History

```bash
curl -X GET "http://localhost:8002/v1/memory/sess_test_001/history?limit=10"
```

**Response:**
```json
{
    "session_id": "sess_test_001",
    "messages": [
        {
            "role": "user",
            "content": "What are the testing requirements?",
            "timestamp": "2024-01-15T10:30:00.000000",
            "metadata": {}
        },
        {
            "role": "assistant",
            "content": "Based on the knowledge base...",
            "timestamp": "2024-01-15T10:30:05.000000",
            "metadata": {"intent": "context_enrich_query"}
        }
    ],
    "count": 2
}
```

### Clear Session Memory

```bash
curl -X DELETE http://localhost:8002/v1/memory/sess_test_001
```

**Response:**
```json
{
    "status": "cleared",
    "session_id": "sess_test_001"
}
```

---

## Error Responses

### Validation Error (422)
```json
{
    "detail": [
        {
            "loc": ["body", "session_id"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}
```

### Internal Error (500)
```json
{
    "status": "error",
    "error_code": "INTERNAL_ERROR",
    "message": "An internal error occurred",
    "details": {"error": "Connection refused"},
    "timestamp": "2024-01-15T10:40:00.000000"
}
```

### Timeout Error (504)
```json
{
    "error_code": "REQUEST_TIMEOUT",
    "message": "Request timed out after 600 seconds",
    "details": {"path": "/v1/chat", "timeout_seconds": 600}
}
```

---

## Notes

1. **selected_model**: This optional parameter is passed to the RAG agent API calls as a header (`X-Selected-Model`) for downstream model selection.

2. **SSL Verification**: By default, SSL verification is disabled (`SSL_VERIFY=false`). Set to `true` in production.

3. **Timeouts**: Default timeout is 600 seconds (10 minutes) for both requests and agent calls.

4. **CORS**: CORS is enabled for all origins. Configure appropriately for production.

5. **Streaming**: The `/v1/chat/stream` endpoint returns Server-Sent Events (SSE). Ensure your client handles `text/event-stream` content type.
