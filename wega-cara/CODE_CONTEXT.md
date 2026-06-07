# Code Context

## Purpose

This file captures the current implementation context for future requirements and feature work.

## Project Summary

- Project: FastAPI backend for an automated AI code review agent
- Runtime entrypoint: `main.py`
- App factory: `cara/app.py`
- Main package: `cara/`
- Tests: `tests/`
- Persistence: local filesystem reports under `/tmp/reports` by default
- Architecture style: stateless service with FastAPI `BackgroundTasks`

## Current API Surface

### `POST /webhook`

- Accepts GitHub `pull_request` webhooks
- Processes `opened` and `synchronize`
- Returns `202 Accepted` immediately
- Verifies `X-Hub-Signature-256` when `GITHUB_WEBHOOK_SECRET` is configured
- Queues the shared review pipeline in the background

### `POST /prompt`

- Accepts a natural-language command
- Uses Gemini to extract:
  - `owner`
  - `repo`
  - `pr_number`
- Verifies the PR exists through GitHub
- Queues the same background review pipeline
- Returns `202 Accepted`

### `GET /reports/{owner}/{repo}/pulls/{pr_number}`

- Returns the latest saved report by default
- Supports `?version=<n>` for older report versions
- Reads versioned JSON reports from storage

## Package Layout

### `cara/core/`

- `config.py`: environment-driven settings using Pydantic Settings
- `dependencies.py`: FastAPI dependency injection builders
- `errors.py`: app-specific exceptions and JSON exception handlers
- `logging.py`: root logging configuration

### `cara/models/`

- `api.py`: external request/response schemas
- `domain.py`: internal review, PR, Jira, and report models/enums

### `cara/interfaces/`

- `report_storage.py`: `ReportStorageInterface` protocol

### `cara/services/`

- `github_service.py`
  - verifies webhook signatures
  - fetches PRs and changed files
  - builds diff context
  - downloads repo archives from GitHub
  - prunes binaries/unneeded folders
  - selects text files for model context
- `jira_service.py`
  - extracts Jira issue keys from PR text
  - fetches Jira issue details when configured
  - parses acceptance criteria
  - produces fallback Jira validation states
- `genai_service.py`
  - parses natural language into PR references
  - uploads repository context files through Google GenAI File API
  - generates structured review output using response schemas
- `report_storage.py`
  - local filesystem implementation of report storage
  - auto-increments report versions
- `review_orchestrator.py`
  - coordinates GitHub, Jira, Gemini, and storage
  - persists both success and failure reports

### `cara/routers/`

- `webhook.py`: GitHub webhook endpoint
- `prompt.py`: natural-language trigger endpoint
- `reports.py`: report retrieval endpoint

## Shared Review Flow

1. Resolve target PR from webhook payload or prompt parsing
2. Fetch PR metadata and changed files from GitHub
3. Detect Jira issue key from PR title/body
4. Fetch Jira issue context when Jira is configured
5. Download repository archive at the PR head SHA
6. Remove irrelevant/binary artifacts from extracted repo
7. Upload selected repository files as Gemini context
8. Send diff + project context to Gemini for structured review
9. Save a versioned JSON report to storage
10. If the pipeline fails, save a failure report instead of dropping the run

## Storage Behavior

- Default base path: `/tmp/reports`
- Report layout:
  - `{base}/{owner}/{repo}/pulls/{pr_number}/report-v{version}.json`
- Writes are done through a temporary file and rename
- No database is currently used

## Environment Variables

- `GITHUB_TOKEN`
- `GITHUB_WEBHOOK_SECRET`
- `GOOGLE_API_KEY`
- `JIRA_SERVER_URL`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`
- Optional model/config overrides:
  - `GENAI_REVIEW_MODEL`
  - `GENAI_PROMPT_PARSER_MODEL`
  - `REPORTS_BASE_PATH`

## Key Implementation Constraints

- Keep the app stateless
- Reuse the shared orchestrator flow for both `/webhook` and `/prompt`
- Preserve strict Pydantic schema validation for model outputs
- Keep storage behind `ReportStorageInterface`
- Avoid hardcoded credentials; use environment variables only
- Prefer extending existing service boundaries over adding logic to routers

## Existing Tests

- `tests/test_webhook_router.py`
- `tests/test_prompt_router.py`
- `tests/test_reports_router.py`
- `tests/test_review_orchestrator.py`

## Validation Commands

- `.venv/bin/ruff check .`
- `.venv/bin/ruff format --check .`
- `.venv/bin/python -m mypy cara main.py`
- `.venv/bin/python -m pytest tests`

## Notes For Future Requirements

- New features should usually fit into one of these extension points:
  - router-level request handling
  - service-level integration logic
  - domain/api models
  - storage interface + implementation
- If report persistence changes, preserve version lookup semantics used by `GET /reports/...`
- If review scope changes, update both the orchestrator flow and the related tests
