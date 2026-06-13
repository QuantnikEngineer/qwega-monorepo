# Langfuse Instrumentation Documentation

## QUANTNIK UserStory to Test Cases Agent

Date: May 2026
SDK: Langfuse Python SDK v4 (OTEL-based)

---

## 1. Purpose

This document explains the current Langfuse and OpenTelemetry instrumentation setup for the UserStory to Test Cases service.

Goals:

- Capture LLM generations (input, output, token usage, latency).
- Capture request-level and step-level spans.
- Export traces to Langfuse and optionally to an OTEL collector.
- Emit OTEL metrics for dashboards and alerts.

---

## 2. Files In Scope

- main.py: instrumented runtime entry point.
- langfuse_instrumentation.py: monkey patches, ASGI middleware, OTEL setup/exporters, shutdown.
- api_server.py: FastAPI endpoints.
- userstory2TestCasesAgent.py: core generation and integrations (Jira, Xray, qTest, ADO).
- build_cert_bundle.py: builds combined_ca.pem from cert inputs.
- cert/: cert files used to build CA bundle.

---

## 3. Runtime Flow (As Implemented)

1. main.py imports app from api_server.py.
2. main.py sets SSL_CERT_FILE and REQUESTS_CA_BUNDLE if combined_ca.pem exists.
3. main.py calls instrument().
4. main.py adds LangfuseASGIMiddleware.
5. main.py registers shutdown() using atexit.
6. uvicorn starts the service.

Note: startup order currently imports api_server.py before instrument() executes.

---

## 4. Current Instrumentation Behavior

langfuse_instrumentation.py currently attempts these patches:

- model.generate_content
- convert_test_cases_to_test_data
- analyze_and_generate_test_data
- push_to_harness_devops

ASGI middleware creates root span:

- testcase_to_testdata_conversion

Current middleware path filter:

- /generate-test-data

---

## 5. Alignment With Current API

Current API routes in this repository are centered on:

- /v1/generate-test-cases/bulk
- /v1/generate-test-cases/bulk/qtest
- /v1/generate-test-cases/bulk/ado
- /v1/generate-test-cases/bulk/brownfield
- /v1/jobs/{job_id}

Current agent functions include:

- process_single_story_jira
- process_single_story_qtest
- run_bulk_job_jira
- run_bulk_job_qtest
- run_bulk_brownfield_job_jira

Legacy function names in current instrumentation do not match this module surface.

Impact:

- Middleware filter does not target active generation routes.
- Legacy patch targets do not align with current agent function names.

---

## 6. OTEL Metrics Defined

When OTEL_EXPORTER_OTLP_ENDPOINT is set, the following metrics are created:

- llm_requests_total
- llm_tokens_total
- llm_request_duration_seconds
- testdata_generation_total
- harness_push_total
- http_request_duration_seconds

Common labels include model, status, endpoint, method, status_code.

---

## 7. Trace Export Pipeline

### 7.1 Langfuse OTEL exporter

- Endpoint: {LANGFUSE_HOST}/api/public/otel/v1/traces
- Auth: Basic LANGFUSE_PUBLIC_KEY:LANGFUSE_SECRET_KEY
- TLS: combined_ca.pem used when available

### 7.2 Optional standalone OTEL collector exporter

Enabled by:

- OTEL_COLLECTOR_ENDPOINT

Optional auth/headers:

- OTEL_COLLECTOR_AUTH_TOKEN
- OTEL_COLLECTOR_HEADERS
- OTEL_COLLECTOR_TIMEOUT_SEC

### 7.3 Multi-export mode

If both exporters are available, spans are fanned out to both.

---

## 8. Environment Variables

### 8.1 Langfuse required

- LANGFUSE_PUBLIC_KEY
- LANGFUSE_SECRET_KEY
- LANGFUSE_HOST

### 8.2 Langfuse optional

- LANGFUSE_TIMEOUT_SEC

### 8.3 OTEL optional

- OTEL_EXPORTER_OTLP_ENDPOINT
- OTEL_EXPORTER_OTLP_PROTOCOL (grpc or http/protobuf)
- OTEL_SERVICE_NAME
- OTEL_RESOURCE_ATTRIBUTES

### 8.4 Optional extra collector export

- OTEL_COLLECTOR_ENDPOINT
- OTEL_COLLECTOR_AUTH_TOKEN
- OTEL_COLLECTOR_HEADERS
- OTEL_COLLECTOR_TIMEOUT_SEC

### 8.5 TLS/cert related

- OTEL_CA_CERT_PATH
- REQUESTS_CA_BUNDLE
- SSL_CERT_FILE

---

## 9. Certificates In Docker/Cloud Run

Cloud Run can read certificates that are copied into the image at build time.

Recommended Dockerfile pattern:

```dockerfile
COPY cert/ /app/cert/
COPY build_cert_bundle.py /app/
RUN python /app/build_cert_bundle.py
ENV REQUESTS_CA_BUNDLE=/app/combined_ca.pem
ENV SSL_CERT_FILE=/app/combined_ca.pem
```

Notes:

- Ensure cert/ is not excluded by .dockerignore.
- Prefer CA bundle setup over DISABLE_SSL_VERIFY.

---

## 10. Run Steps

### 10.1 Install dependencies

```bash
pip install -r requirements.txt
```

### 10.2 Build CA bundle (if needed)

```bash
python build_cert_bundle.py
```

### 10.3 Start instrumented service

```bash
python main.py
```

Alternative:

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

---

## 11. Validation Checklist

- Startup logs confirm instrumentation and middleware registration.
- Langfuse receives traces for instrumented request paths.
- LLM generation observations include output and token metadata on Vertex path.
- OTEL metrics are visible in collector/dashboard when configured.

---

## 12. Known Gaps And Recommended Next Fixes

To fully align observability with this repository:

1. Update middleware filter from /generate-test-data to active /v1/generate-test-cases routes.
2. Replace legacy patch targets with current functions in userstory2TestCasesAgent.py.
3. Call instrument() before importing api_server.py in main.py.
4. Rename legacy span/metric terms (testdata/harness) for consistency with testcases service.

---

## 13. Troubleshooting

### Missing traces

- Verify LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST.
- Start service with main.py.
- Verify request path matches middleware filter.

### TLS errors

- Rebuild combined_ca.pem.
- Verify REQUESTS_CA_BUNDLE and SSL_CERT_FILE values.

### No OTEL metrics

- Set OTEL_EXPORTER_OTLP_ENDPOINT.
- Confirm OTEL packages are installed.

### Startup patch errors

- Verify patch target function names exist in userstory2TestCasesAgent.py.

---

## 14. Security Notes

- Never commit real credentials.
- Keep .env local and .env.example sanitized.
- Avoid permanent DISABLE_SSL_VERIFY=true use outside controlled testing.
