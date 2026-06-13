# SDLC Knowledge Base (RAG)

An enterprise-grade **Retrieval-Augmented Generation** system that ingests, classifies, and retrieves SDLC documentation using AI-powered semantic search and LLM generation. It serves as a centralized knowledge hub for software development lifecycle artifacts across all phases — requirements, design, development, testing, deployment, and security.

## Key Features

- **Multi-source ingestion** — Upload files (PDF, DOCX, XLSX, JSON), index GitHub/Harness repos, scrape websites, ingest SharePoint documents, ingest Confluence pages, and accept agent-generated output
- **Dual-layer classification** — Rule engine (YAML patterns) + LLM classifier (Vertex AI) with recall-biased confidence blending
- **Dual-database architecture** — Critical and non-critical content stored in separate PostgreSQL instances with automatic migration
- **Semantic retrieval** — Qdrant vector search with phase-aware query routing, multi-stage fallback, and TF-IDF reranking
- **RAG generation** — Grounded answers via Google Gemini with source citations and confidence scores
- **Input/output guardrails** — PII detection (Presidio), prompt injection prevention, grounding verification, and toxicity filtering
- **Diff-aware re-uploads** — SHA256 chunk hashing with vector reuse for fast re-indexing
- **Feedback loop** — User corrections and domain preferences indexed as critical knowledge for future retrieval

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Ingestion (Upload / Repo / Website / Agent / Feedback) │
└────────────────────────┬────────────────────────────────┘
                         │
                 Classification Pipeline
                  (Rule Engine + LLM)
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
     ┌──────────────┐         ┌──────────────────┐
     │ PostgreSQL   │         │ PostgreSQL       │
     │ (Critical)   │         │ (Non-Critical)   │
     └──────┬───────┘         └────────┬─────────┘
            └────────────┬─────────────┘
                         ▼
                  ┌──────────────┐
                  │   Qdrant     │
                  │ Vector Store │
                  └──────────────┘
                         │
                         ▼
              ┌────────────────────┐
              │  Query / Retrieve  │
              │  + RAG Generation  │
              └────────────────────┘
```

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI, Uvicorn, Pydantic |
| Databases | PostgreSQL 16 (critical + non-critical), Qdrant (vector DB) |
| LLM / Embeddings | Google Vertex AI (Gemini, text-embedding-004) |
| Document Parsing | PyMuPDF, python-docx, openpyxl, pandas |
| Connectors | GitHub API, Harness Code API, BeautifulSoup, Confluence REST API |
| Guardrails | Presidio (PII), better-profanity, scikit-learn (grounding) |
| Text Processing | LangChain RecursiveCharacterTextSplitter |
| Async Runtime | SQLAlchemy asyncio + asyncpg |

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Google Cloud project with Vertex AI enabled
- (Optional) GitHub / Harness / Confluence / SharePoint access tokens

## Getting Started

### 1. Start infrastructure

```bash
docker-compose up -d
```

This provisions:
| Service | Port | Purpose |
|---|---|---|
| `postgres` | 5432 | Critical document store |
| `postgres_nc` | 5433 | Non-critical document store |
| `qdrant` | 6333, 6334 | Vector database (both collections) |

### 2. Configure environment

Copy `.env.example` to `.env` (or create `.env`) and set:

```env
# App
APP_ENV=development
DEBUG=true

# PostgreSQL — Critical DB
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=sdlc_kb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# PostgreSQL — Non-Critical DB
POSTGRES_HOST_NC=127.0.0.1
POSTGRES_PORT_NC=5432
POSTGRES_DB_NON_CRITICAL=sdlc_kb_non_critical

# Qdrant
QDRANT_LOCAL_PATH=./qdrant_storage
QDRANT_COLLECTION=sdlc_kb
QDRANT_VECTOR_SIZE=768

# Vertex AI
VERTEX_PROJECT_ID=<your-project-id>
VERTEX_LOCATION=us-central1
VERTEX_EMBEDDING_MODEL=text-embedding-004
VERTEX_LLM_MODEL=gemini-2.5-flash

# Chunking
CHUNK_SIZE=512
CHUNK_OVERLAP=64

# Retrieval
TOP_K=5
SIMILARITY_THRESHOLD=0.7

# Classification
CONFIDENCE_THRESHOLD=0.75

# Upload
MAX_UPLOAD_MB=50

# Connector tokens (optional)
GITHUB_TOKEN=<PAT>
HARNESS_TOKEN=<PAT>
CONFLUENCE_EMAIL=<email>
CONFLUENCE_TOKEN=<api-token>
SHAREPOINT_TOKEN=<bearer-token>
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

### 4. Run the application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## API Reference

### Ingestion

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/upload` | Upload files (PDF, DOCX, XLSX, JSON) |
| POST | `/api/v1/ingest/repo` | Index a GitHub or Harness Code repository |
| POST | `/api/v1/ingest/website` | Scrape one or more web URLs |
| POST | `/api/v1/ingest/agent-output` | Ingest agent-generated content |

All ingestion endpoints return **202 Accepted** and process in the background. Poll `/api/v1/documents/{doc_id}` for status.

For the unified ingest body, supported `source` values include `website`, `sharepoint`, `repo`, and `agent_output`.

### Retrieval & Query

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/query` | RAG query — semantic search + LLM generation |
| POST | `/api/v1/context/enrich` | Retrieve ranked context chunks for agent pre-generation |

**Query example:**

```json
{
  "query": "How do we handle authentication in microservices?",
  "sdlc_phase": "design",
  "top_k": 5,
  "include_sources": true,
  "criticality": null
}
```

### Document Management

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/documents` | List all documents (paginated) |
| GET | `/api/v1/documents/{doc_id}` | Get document metadata and status |
| DELETE | `/api/v1/documents/{doc_id}` | Delete document and all associated vectors |

### Feedback

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/feedback` | Submit feedback (rating, correction, or domain preference) |

Corrections and domain preferences are indexed as **critical** knowledge and prioritized in future retrievals.

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |

## Classification System

Documents are classified through a dual-layer pipeline:

1. **Rule Engine** — 12 weighted pattern rules defined in `config/sdlc_rules.yaml` covering security, requirements, architecture, testing, deployment, and operations
2. **LLM Classifier** — Vertex AI semantic analysis of document content
3. **Confidence Blending** — `max(rule × 0.4 + llm × 0.6, rule, llm)` with recall bias (errs toward CRITICAL)

SDLC phases: `requirements`, `design`, `development`, `testing`, `deployment`, `security`, `general`

## Project Structure

```
sdlc_kb/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/v1/                 # API route handlers
│   ├── classification/         # Rule engine + LLM classifier
│   ├── connectors/             # GitHub, Harness, Website, Confluence
│   ├── core/                   # Config, exceptions, logging
│   ├── db/                     # SQLAlchemy async session management
│   ├── feedback/               # Feedback collection and indexing
│   ├── guardrails/             # Input/output safety checks
│   ├── indexing/               # Chunking + embedding
│   ├── ingestion/              # Document pipeline + deduplication
│   ├── models/                 # SQLAlchemy ORM models
│   ├── retrieval/              # Qdrant store + retriever
│   └── schemas/                # Pydantic request/response schemas
├── config/
│   └── sdlc_rules.yaml         # Classification rule definitions
├── docker-compose.yml
├── requirements.txt
└── .env
```