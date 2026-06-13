# Langfuse Instrumentation — Change Documentation

## QUANTNIK Test Cases to Scripts Agent

**Date:** April 2026  
**SDK Version:** Langfuse Python SDK v4.5.0 (OTEL-based)  
**Model:** Vertex AI Gemini (`gemini-3-flash-preview`)

---

## 1. Overview

Langfuse observability has been added to the Test Cases to Scripts Agent to track LLM performance, token usage, costs, latency, and quality metrics. The implementation follows a **non-invasive monkey-patching approach** — no existing agent or API server code was modified.

### Design Principles

- **Zero changes to existing code**: `testcase_to_scripts_agent.py` and `api_server.py` remain untouched.
- **Wrapper-based instrumentation**: All tracing is injected via monkey-patching at startup, before the API server imports agent functions.
- **New entry point**: `main.py` replaces direct `api_server.py` execution, orchestrating the instrumentation before the app starts.
- **Custom SSL handling**: A combined CA certificate bundle supports both corporate proxy CAs and the self-signed Langfuse ALB certificate on AWS.

---

## 2. Files Changed / Created

### 2.1 Files NOT Modified (Existing Code)

| File | Description |
|------|-------------|
| `testcase_to_scripts_agent.py` | Core agent — Gemini LLM calls, code extraction, Harness push. **No changes.** |
| `api_server.py` | FastAPI app with `/convert`, `/health`, `/supported-combinations`. **No changes.** |
| `Dockerfile` | Container build definition. **No changes.** |
| `README.md` | Original documentation. **No changes.** |

### 2.2 New Files Created

| File | Purpose |
|------|---------|
| `main.py` | New entry point — wires instrumentation before app startup |
| `langfuse_instrumentation.py` | All monkey-patching, middleware, and Langfuse client setup |
| `build_cert_bundle.py` | Builds `combined_ca.pem` from certifi + Windows Root CAs + Langfuse ALB cert |
| `combined_ca.pem` | Combined CA certificate bundle (184 certificates, ~344 KB) |
| `scripts/extract_metrics.py` | Queries Langfuse REST API for generation data, outputs metrics JSON |
| `scripts/generate_report.py` | Reads metrics JSON, generates human-readable TXT and JSON reports |

### 2.3 Files Updated

| File | Change |
|------|--------|
| `requirements.txt` | Added `langfuse>=4.5.0`, `opentelemetry-exporter-otlp-proto-http`, `httpx` |
| `.env` | Added Langfuse environment variables (keys, host, cert path) |

---

## 3. Architecture

### 3.1 Startup Flow

```
main.py
  │
  ├─ (0) Set SSL_CERT_FILE / REQUESTS_CA_BUNDLE env vars (before any network imports)
  │
  ├─ (1) import testcase_to_scripts_agent
  │       → Triggers Vertex AI init, model creation, prompt config
  │
  ├─ (2) langfuse_instrumentation.instrument()
  │       → Build custom OTEL span exporter with CA bundle
  │       → Create Langfuse client (singleton)
  │       → Monkey-patch: executor, model.generate_content,
  │         convert_test_cases_to_scripts, push_to_harness_devops,
  │         process_single_test_case
  │
  ├─ (3) from api_server import app
  │       → api_server does `from testcase_to_scripts_agent import process_single_test_case`
  │       → Picks up the ALREADY-PATCHED version of the function
  │
  ├─ (4) langfuse_instrumentation.add_middleware(app)
  │       → Adds LangfuseASGIMiddleware for root span per /convert request
  │
  └─ (5) atexit.register(shutdown)
          → Ensures Langfuse flushes pending events on process exit
```

### 3.2 Request-Time Trace Hierarchy

For each `POST /convert` request, the following trace structure is created:

```
Trace: testcase_to_script_conversion (root span — ASGI middleware)
  │
  ├─ Span: process_test_case_TC001
  │   ├─ Span: convert_test_cases
  │   │   └─ Generation: generate-script (Gemini LLM call)
  │   └─ Span: push_to_harness
  │
  ├─ Span: process_test_case_TC002
  │   ├─ Span: convert_test_cases
  │   │   └─ Generation: generate-script (Gemini LLM call)
  │   └─ Span: push_to_harness
  │
  └─ (For BDD frameworks, additional generations appear:
      generate-feature-file, generate-step-definition, generate-page-object)
```

---

## 4. Detailed File Descriptions

### 4.1 `main.py` — Instrumented Entry Point

**Purpose:** Replaces direct `api_server.py` execution. Ensures instrumentation is applied before the FastAPI app is loaded.

**Key details:**
- Sets `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` environment variables to the combined CA bundle **before any network-related imports** — this ensures both Python's `ssl` module and the `requests` library use the combined bundle for all outgoing HTTPS connections.
- Import order is critical: agent module first → patch functions → then import api_server.
- Registers `atexit` handler for clean Langfuse shutdown.

**Usage:**
```bash
# Direct
python main.py

# Via uvicorn
uvicorn main:app --host 0.0.0.0 --port 8080
```

### 4.2 `langfuse_instrumentation.py` — Core Instrumentation

**Purpose:** Contains all monkey-patching logic, ASGI middleware, and Langfuse client management.

#### 4.2.1 Functions Patched

| Original Function | Wrapper Behavior |
|---|---|
| `model.generate_content()` | Creates a `GENERATION` observation for every Gemini LLM call. Captures prompt input (truncated to 5000 chars), model name, generation config, output text, token usage (`input`/`output`/`total`), latency, and error details. |
| `convert_test_cases_to_scripts()` | Creates a `SPAN` per conversion. Captures framework type, language, generation type as input. Records output flags (has_feature, has_script, etc.) and latency. |
| `push_to_harness_devops()` | Creates a `SPAN` per Harness push. Captures folder name, file count, file names. Records resulting URLs, success status, files pushed count. |
| `process_single_test_case()` | Creates a `SPAN` per test case. Captures test case ID/name, framework, language. Records files generated, push results. Attaches **quality scores** to the trace. |
| `executor` (ThreadPoolExecutor) | Wrapped with `_ContextPropagatingExecutor` to copy `contextvars` into thread-pool workers, ensuring OpenTelemetry context propagates correctly across threads. |

#### 4.2.2 ASGI Middleware (`LangfuseASGIMiddleware`)

- Intercepts only `POST /convert` requests (all other endpoints pass through unmodified).
- Creates the **root span** (`testcase_to_script_conversion`) that all child observations nest under.
- Sets a unique `request_id` as a session attribute on the OTEL span.
- Captures HTTP status code and total request latency.
- Attaches a `request_success` quality score (1.0 for 2xx, 0.0 otherwise).
- Calls `_langfuse.flush()` **outside** the `with` block — this is required by Langfuse v4 to ensure the OTEL span is fully ended before being exported.

#### 4.2.3 Custom OTEL Span Exporter (`_build_span_exporter`)

- Builds an `OTLPSpanExporter` from `opentelemetry-exporter-otlp-proto-http`.
- Points to `{LANGFUSE_HOST}/api/public/otel/v1/traces`.
- Uses Basic auth (`public_key:secret_key` base64-encoded).
- Sets `certificate_file` to `combined_ca.pem` — this allows OTEL trace export over HTTPS to the Langfuse ALB with a self-signed certificate.
- Falls back to default SSL if no combined CA bundle exists.

#### 4.2.4 Guard Flags

- `_instrumented` boolean prevents double-patching if `instrument()` is called multiple times (e.g., on uvicorn reload).
- `_middleware_added` boolean prevents adding middleware more than once.

### 4.3 `build_cert_bundle.py` — SSL Certificate Builder

**Purpose:** Builds a combined PEM file from three certificate sources, needed for HTTPS connections in a corporate proxy environment with a self-signed Langfuse ALB.

**Certificate Sources:**

| Source | Method | Typical Count |
|--------|--------|---------------|
| certifi default bundle | `certifi.where()` | ~128 CAs |
| Windows Root CAs | PowerShell `Get-ChildItem Cert:\LocalMachine\Root` | ~46 CAs |
| Langfuse ALB cert | File at `LANGFUSE_CA_CERT_PATH` env var | 1 cert |

**Output:** `combined_ca.pem` (~344 KB, ~184 certificates)

**Usage:**
```bash
python build_cert_bundle.py
```

### 4.4 `scripts/extract_metrics.py` — Metrics Extraction

**Purpose:** Queries the Langfuse REST API to fetch all `GENERATION` observations and compute per-trace token usage and cost metrics.

**What it does:**
1. Fetches generation observations via `GET /api/public/observations?type=GENERATION`.
2. Groups generations by trace ID.
3. Computes token counts (input, output, total) and estimated cost per trace.
4. Outputs `metrics_report.json` and `cost_summary.txt` to the `scripts/` folder.

**Cost model:** Configurable pricing constants (`COST_PER_1K_INPUT`, `COST_PER_1K_OUTPUT`), defaults to Gemini Flash pricing.

**Usage:**
```bash
python scripts/extract_metrics.py
```

### 4.5 `scripts/generate_report.py` — Report Generator

**Purpose:** Reads `metrics_report.json` and produces formatted reports with per-trace breakdowns and cost projections.

**Outputs:**
- `scripts/test_script_metrics_report.txt` — Human-readable report
- `scripts/test_script_metrics_report.json` — Machine-readable report with summary, projections, and per-trace data

**Cost projections** are calculated for 50, 100, 500, and 1000 requests/day over a 30-day month.

**Usage:**
```bash
python scripts/generate_report.py
```

---

## 5. Metrics Tracked

| # | Metric | How It's Tracked |
|---|--------|------------------|
| 1 | **Prompt Monitoring** | `generate_content` wrapper captures full prompt input and LLM output text (truncated to 5000 chars) as `GENERATION` observation input/output |
| 2 | **Token Usage** | Extracted from `result.usage_metadata` — `prompt_token_count`, `candidates_token_count`, `total_token_count` — stored in `usage_details` |
| 3 | **Cost Analysis** | Langfuse auto-calculates from token counts + model pricing config; also computed offline by `extract_metrics.py` |
| 4 | **Response Latency** | Measured via `time.time()` at every level: per LLM call, per conversion step, per test case, and end-to-end request |
| 5 | **Model Performance** | Success/failure status on every observation; errors captured with exception type and message |
| 6 | **Quality Scores** | `score_trace()` calls: `code_extraction_success` (0/1), `push_success` (0/1), `files_generated` (count), `request_success` (0/1) |
| 7 | **Tool Usage** | `push_to_harness` span tracks file count, file names, resulting URLs, and push success/failure |
| 8 | **User Interaction Patterns** | Framework type, language, and generation type captured as span input/metadata/tags |
| 9 | **Error & Retry Patterns** | Try/catch at every instrumentation layer; errors logged with type, message, and level=ERROR |
| 10 | **End-to-End Execution Time** | Root span `testcase_to_script_conversion` measures total request duration in the ASGI middleware |

---

## 6. Environment Variables

### Required (add to `.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key | `pk-lf-971cd336-...` |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key | `sk-lf-b155fa86-...` |
| `LANGFUSE_HOST` | Langfuse server URL | `https://k8s-langfuse-...elb.amazonaws.com` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `LANGFUSE_CA_CERT_PATH` | Path to the Langfuse ALB certificate file | *(none)* |
| `LANGFUSE_TIMEOUT_SEC` | OTEL export timeout in seconds | `20` |
| `LANGFUSE_INSECURE_SKIP_VERIFY` | Skip SSL verification for Langfuse | `false` |

---

## 7. Dependencies Added

Added to `requirements.txt`:

```
langfuse>=4.5.0
opentelemetry-exporter-otlp-proto-http
httpx
```

| Package | Purpose |
|---------|---------|
| `langfuse` | Core SDK for observability (v4 uses OpenTelemetry internally) |
| `opentelemetry-exporter-otlp-proto-http` | Custom OTEL span exporter with `certificate_file` support for self-signed certs |
| `httpx` | HTTP client used by `extract_metrics.py` with custom CA bundle support |

---

## 8. Langfuse v4 API Notes

The implementation uses **Langfuse Python SDK v4.5.0** which was rewritten in March 2026 with an OTEL-based architecture. Key API differences from v3:

| Aspect | v3 (Legacy) | v4 (Current) |
|--------|-------------|--------------|
| Create trace | `langfuse.trace()` | `langfuse.start_as_current_observation(as_type="span")` |
| Context manager | `async with` | `with` (sync context manager) |
| End observation | `gen.end(output=...)` | `gen.update(output=...); gen.end()` |
| Trace scoring | `trace.score()` | `span.score_trace()` |
| Token usage key | `usage` | `usage_details` |
| Custom exporter | N/A | `Langfuse(span_exporter=OTLPSpanExporter(...))` |
| Flush timing | Inside `with` block | **Outside** `with` block (span must be ended first) |

---

## 9. How to Run

### First-Time Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Build the combined CA certificate bundle
python build_cert_bundle.py

# 3. Ensure .env has Langfuse keys (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST)
```

### Start the Instrumented Server

```bash
# Option A: Direct
python main.py

# Option B: Via uvicorn
uvicorn main:app --host 0.0.0.0 --port 8080
```

### Run Without Instrumentation (Original Behavior)

```bash
# Start the original API server directly — no Langfuse tracing
uvicorn api_server:app --host 0.0.0.0 --port 8080
```

### Extract Metrics & Generate Reports

```bash
# After running some /convert requests:
python scripts/extract_metrics.py
python scripts/generate_report.py
```

---

## 10. Verification

After sending a `POST /convert` request:

1. **Server Logs** should show:
   - `✅ SSL CA bundle set`
   - `✅ Custom OTEL exporter built with CA bundle`
   - `✅ Langfuse instrumentation applied (functions patched)`
   - `✅ Langfuse ASGI middleware added`
   - No "Unexpected error" messages from OTEL export

2. **Langfuse Dashboard** should display:
   - A trace named `testcase_to_script_conversion` per request
   - Nested spans: `process_test_case_TCxxx` → `convert_test_cases` → `generate-script` (generation) + `push_to_harness`
   - Token usage and latency on generation observations
   - Quality scores: `code_extraction_success`, `push_success`, `files_generated`, `request_success`

3. **Metrics Scripts** output:
   - `scripts/metrics_report.json` — Per-trace token and cost data
   - `scripts/cost_summary.txt` — Aggregate summary with cost projections
   - `scripts/test_script_metrics_report.txt` — Formatted report

---

## 11. Troubleshooting

| Issue | Cause | Resolution |
|-------|-------|------------|
| "Unexpected error" in OTEL export logs | SSL certificate verification failure for self-signed Langfuse ALB | Run `python build_cert_bundle.py` to rebuild `combined_ca.pem`; verify `LANGFUSE_CA_CERT_PATH` points to correct cert |
| Double-patching warnings | `instrument()` called more than once (e.g., uvicorn reload) | `_instrumented` guard flag prevents this automatically |
| Traces missing child spans | Context not propagating across threads | `_ContextPropagatingExecutor` wraps the ThreadPoolExecutor to copy contextvars |
| `flush()` produces incomplete spans | `flush()` called inside the `with` block before span is ended | `flush()` is called **outside** the `with` block in the middleware |
| Port conflict on startup | Previous server process still holding the port | Kill the old process or use a different port |
| No traces in Langfuse dashboard | OTEL export failing silently | Check server logs for exporter errors; verify Langfuse keys and host URL |
