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

- Python 3.12+
- Google Cloud project with Vertex AI enabled
- Google Cloud CLI (`gcloud`) for deployment
- (Optional) GitHub / Harness / Confluence / SharePoint access tokens

## Getting Started

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 2. Deploy to Cloud Run

```bash
make deploy
# Or:
gcloud run deploy dev-wega-rag-agent --source . \
  --service-account=sa-cloudrun@digital-rig-poc.iam.gserviceaccount.com \
  --region=us-central1 --min-instances=0 --max-instances=1 \
  --port=8080 --allow-unauthenticated --timeout=900 --memory=2Gi --cpu=1
```

### 3. Local development

```bash
# Install dependencies
pip install -e .
python -m spacy download en_core_web_sm

# Run the app (connects to remote Postgres + Qdrant per .env)
make dev
# Or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

The API will be available at `http://localhost:8080`. Interactive docs at `http://localhost:8080/docs`.

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
├── Dockerfile
├── requirements.txt
└── .env
```