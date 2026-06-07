# WEGA Anomaly Agent

AI-powered anomaly detection and auto-remediation engine for Kubernetes environments.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        WEGA ANOMALY AGENT (Container)                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                     CONFIGURATION LAYER (Customer Tunable)                  ││
│  │  Environment Variables / ConfigMap                                          ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                       │                                         │
│  ┌──────────────┐  ┌──────────────┐  ▼  ┌──────────────┐  ┌──────────────────┐ │
│  │  Monitoring  │  │     AI       │     │ Orchestrator │  │   Kubernetes     │ │
│  │  Adapters    │  │  Providers   │     │   Adapters   │  │   Client         │ │
│  │  • Datadog   │  │  • Gemini    │     │  • Harness   │  │   • Scale        │ │
│  │  • Prometheus│  │  • Bedrock   │     │  • Jenkins   │  │   • Restart      │ │
│  │  • CloudWatch│  │  • Vertex    │     │  • ArgoCD    │  │   • Rollback     │ │
│  │  • Splunk    │  │  • OpenAI    │     │  • GitLab CI │  │                  │ │
│  │  • Dynatrace │  │  • Azure OAI │     │  • Tekton    │  │                  │ │
│  └──────────────┘  └──────────────┘     └──────────────┘  └──────────────────┘ │
│          │                │                    │                   │            │
│          └────────────────┴────────────────────┴───────────────────┘            │
│                                       │                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                        CORE ENGINE (Protected IP)                           ││
│  │  • AI Prompt Templates          • Confidence Scoring Algorithm              ││
│  │  • Root Cause Analysis Logic    • Transient Detection                       ││
│  │  • Decision Engine              • Remediation Orchestration                 ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                       │                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                           REST API Layer                                    ││
│  │  POST /api/v1/analyze     - Analyze alert, return AI decision               ││
│  │  POST /api/v1/remediate   - Execute remediation action                      ││
│  │  POST /api/v1/chat        - Chatbot queries                                 ││
│  │  GET  /api/v1/status      - Get current status/history                      ││
│  │  GET  /health             - Health check                                    ││
│  │  GET  /ready              - Readiness check                                 ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
Anomaly-Agent/
├── src/
│   ├── main.py                    # Application entry point
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py            # Environment variable configuration
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # FastAPI route definitions
│   │   └── schemas.py             # Pydantic request/response models
│   ├── core/
│   │   ├── __init__.py
│   │   ├── engine.py              # Main decision engine (IP)
│   │   ├── analyzer.py            # Root cause analysis (IP)
│   │   ├── confidence.py          # Confidence scoring (IP)
│   │   └── transient.py           # Transient detection (IP)
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── monitoring/
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # Abstract monitoring adapter
│   │   │   ├── datadog.py
│   │   │   ├── prometheus.py
│   │   │   ├── cloudwatch.py
│   │   │   ├── splunk.py
│   │   │   └── dynatrace.py
│   │   ├── ai_providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # Abstract AI provider
│   │   │   ├── gemini.py
│   │   │   ├── bedrock.py
│   │   │   ├── vertex.py
│   │   │   ├── openai_provider.py
│   │   │   └── azure_openai.py
│   │   └── orchestrators/
│   │       ├── __init__.py
│   │       ├── base.py            # Abstract orchestrator adapter
│   │       ├── harness.py
│   │       ├── jenkins.py
│   │       ├── argocd.py
│   │       └── gitlab_ci.py
│   ├── kubernetes/
│   │   ├── __init__.py
│   │   └── client.py              # Kubernetes operations
│   ├── chatbot/
│   │   ├── __init__.py
│   │   ├── handler.py             # Chat message handler
│   │   └── prompts.py             # Chatbot prompt templates (IP)
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── metrics.py
├── tests/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_engine.py
│   └── test_adapters.py
├── deploy/
│   ├── kubernetes/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── configmap.yaml
│   │   └── secrets.yaml
│   └── helm/
│       └── anomaly-agent/
│           ├── Chart.yaml
│           ├── values.yaml
│           └── templates/
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Configuration

All configuration via environment variables:

### Adapter Selection
| Variable | Options | Default |
|----------|---------|---------|
| `MONITORING_ADAPTER` | datadog, prometheus, cloudwatch, splunk, dynatrace | datadog |
| `AI_PROVIDER` | gemini, bedrock, vertex, openai, azure_openai | gemini |
| `ORCHESTRATOR_ADAPTER` | harness, jenkins, argocd, gitlab_ci, tekton | harness |

### Thresholds (Customer Tunable)
| Variable | Description | Default |
|----------|-------------|---------|
| `CONFIDENCE_AUTO_THRESHOLD` | Auto-remediate if confidence >= this | 80 |
| `CONFIDENCE_REVIEW_THRESHOLD` | Human review if between review-auto | 60 |
| `TRANSIENT_CPU_THRESHOLD` | CPU below this = transient spike | 50 |
| `CONFIRMATION_WAIT_SECONDS` | Wait before confirming sustained issue | 300 |

### Scaling Limits
| Variable | Description | Default |
|----------|-------------|---------|
| `SCALING_MIN_REPLICAS` | Minimum pod replicas | 1 |
| `SCALING_MAX_REPLICAS` | Maximum pod replicas | 10 |
| `SCALING_COOLDOWN_SECONDS` | Cooldown between scaling ops | 300 |

### Behavior
| Variable | Description | Default |
|----------|-------------|---------|
| `AUTO_REMEDIATE_ENABLED` | Enable automatic remediation | true |
| `REQUIRE_HUMAN_APPROVAL` | Always require approval | false |
| `NOTIFICATION_SLACK_WEBHOOK` | Slack webhook URL | "" |
| `NOTIFICATION_EMAIL` | Email for notifications | "" |

### AI Provider Settings
| Variable | Description | Default |
|----------|-------------|---------|
| `AI_MODEL` | Model name (provider-specific) | gemini-2.5-flash |
| `AI_TIMEOUT_SECONDS` | API call timeout | 30 |
| `AI_MAX_TOKENS` | Max response tokens | 8192 |

### Secrets (Kubernetes Secrets)
| Variable | Description |
|----------|-------------|
| `AI_API_KEY` | API key for selected AI provider |
| `MONITORING_API_KEY` | API key for monitoring tool |
| `MONITORING_APP_KEY` | App key (if required, e.g., Datadog) |

## Quick Start

```bash
# Build container
docker build -t wega-anomaly-agent:latest .

# Run locally
docker run -p 8080:8080 \
  -e MONITORING_ADAPTER=datadog \
  -e AI_PROVIDER=gemini \
  -e AI_API_KEY=$GEMINI_KEY \
  -e MONITORING_API_KEY=$DD_API_KEY \
  wega-anomaly-agent:latest

# Deploy to Kubernetes
helm install anomaly-agent ./deploy/helm/anomaly-agent \
  --set monitoring.adapter=prometheus \
  --set ai.provider=bedrock \
  --set thresholds.confidenceAuto=85
```

## API Endpoints

### POST /api/v1/analyze
Analyze an alert and return AI decision.

### POST /api/v1/remediate
Execute a remediation action.

### POST /api/v1/chat
Handle chatbot queries about the system.

### GET /api/v1/status
Get current status and remediation history.

### GET /health
Health check endpoint.

## License

Proprietary - Wipro Limited
