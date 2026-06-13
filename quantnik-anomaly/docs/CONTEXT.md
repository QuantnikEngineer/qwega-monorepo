# QUANTNIK Anomaly Agent - Context Document

**Purpose:** This document provides complete context for the Anomaly Agent project. Use this as a reference for future development, maintenance, and enhancements.

**Platform:** Ubuntu 22.04 LTS (AWS EC2)  
**Last Updated:** 2026-04-30  
**Status:** ✅ Live and Operational

---

## 1. Project Overview

### What is Anomaly Agent?

An AI-powered anomaly detection and auto-remediation engine designed to:
- Receive alerts from monitoring tools (Datadog, Prometheus, CloudWatch, etc.)
- Perform AI-driven root cause analysis using LLMs (Gemini, Bedrock, OpenAI, etc.)
- Automatically scale/restart Kubernetes deployments based on confidence scores
- Provide a chatbot interface for user queries and manual interventions

### Why Was It Built?

| Problem | Solution |
|---------|----------|
| Manual alert triage is slow | AI analyzes alerts in seconds |
| Different customers use different tools | Adapter pattern supports multiple tools |
| Need to protect proprietary logic (IP) | Containerized - customers see only API |
| Require human oversight for critical actions | Confidence thresholds control automation |

### Target Users

- **Enterprise Customers**: Deploy in their environment with their tools
- **Wipro DevOps Team**: Deploy and manage for customers
- **End Users**: Interact via quantnik-sdlc frontend (Dashboard + Chatbot)

---

## 2. Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CUSTOMER ENVIRONMENT                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐         ┌─────────────────────────────────────────────┐   │
│  │ MONITORING      │         │         QUANTNIK ANOMALY AGENT                  │   │
│  │ • Datadog       │  Alert  │         (Docker Container on EKS)           │   │
│  │ • Prometheus    │────────▶│                                             │   │
│  │ • CloudWatch    │ Webhook │  ┌─────────────────────────────────────┐    │   │
│  │ • Splunk        │         │  │     CONFIGURATION LAYER             │    │   │
│  │ • Dynatrace     │         │  │     (Environment Variables)         │    │   │
│  └─────────────────┘         │  │     Customer-tunable settings       │    │   │
│                              │  └─────────────────────────────────────┘    │   │
│  ┌─────────────────┐         │                    │                        │   │
│  │ quantnik-sdlc       │         │  ┌─────────────────▼─────────────────┐      │   │
│  │ FRONTEND        │◀───────▶│  │     ADAPTER LAYER                 │      │   │
│  │ • Dashboard     │   API   │  │  ┌───────────┐ ┌───────────────┐  │      │   │
│  │ • Chatbot       │         │  │  │Monitoring │ │ AI Providers  │  │      │   │
│  └─────────────────┘         │  │  │ Adapters  │ │ • Gemini      │  │      │   │
│                              │  │  │ • Datadog │ │ • Bedrock     │  │      │   │
│                              │  │  │ • Prom    │ │ • Vertex      │  │      │   │
│                              │  │  │ • CW      │ │ • OpenAI      │  │      │   │
│                              │  │  └───────────┘ └───────────────┘  │      │   │
│                              │  └─────────────────────────────────────┘    │   │
│                              │                    │                        │   │
│                              │  ┌─────────────────▼─────────────────┐      │   │
│                              │  │     CORE ENGINE (Protected IP)    │      │   │
│                              │  │  • AI Prompt Templates            │      │   │
│                              │  │  • Confidence Scoring Algorithm   │      │   │
│                              │  │  • Root Cause Analysis Logic      │      │   │
│                              │  │  • Decision Engine                │      │   │
│                              │  └─────────────────────────────────────┘    │   │
│                              │                    │                        │   │
│                              │  ┌─────────────────▼─────────────────┐      │   │
│                              │  │     REST API LAYER                │      │   │
│                              │  │  POST /api/v1/analyze             │      │   │
│                              │  │  POST /api/v1/remediate           │      │   │
│                              │  │  POST /api/v1/chat                │      │   │
│                              │  │  GET  /api/v1/status              │      │   │
│                              │  └─────────────────────────────────────┘    │   │
│                              └──────────────────┬──────────────────────────┘   │
│                                                 │                              │
│                                                 ▼                              │
│                              ┌─────────────────────────────────────────────┐   │
│                              │     KUBERNETES CLUSTER (EKS)               │   │
│                              │     kubectl scale / restart / rollback     │   │
│                              └─────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Decision Flow

```
Alert Received
      │
      ▼
┌─────────────────┐
│ Parse Alert     │ ◀── Monitoring Adapter converts to standard format
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Confirmation    │ ◀── Wait 5 minutes (configurable)
│ Wait            │     to detect transient spikes
└────────┬────────┘
         │
         ▼
┌─────────────────┐     Yes    ┌─────────────────┐
│ CPU < Threshold?│───────────▶│ TRANSIENT       │
│ (e.g., < 50%)   │            │ RESOLVED        │
└────────┬────────┘            │ (No action)     │
         │ No                  └─────────────────┘
         ▼
┌─────────────────┐
│ Fetch Context   │ ◀── Recent metrics, historical baseline, past alerts
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ AI Analysis     │ ◀── Call Gemini/Bedrock/OpenAI with context
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Calculate       │ ◀── Proprietary scoring algorithm (IP)
│ Confidence      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                  DECISION                           │
├─────────────────┬─────────────────┬─────────────────┤
│ Confidence ≥80% │ Confidence 60-79│ Confidence <60% │
│                 │                 │                 │
│ PROCEED_AUTO    │ HUMAN_REVIEW    │ MONITORING_ONLY │
│ (Auto-scale)    │ (Manual)        │ (No action)     │
└─────────────────┴─────────────────┴─────────────────┘
```

---

## 3. IP Protection Strategy

### What is Protected (Hidden in Container)

| Component | Location | Description |
|-----------|----------|-------------|
| AI Prompts | `src/core/prompts.py` | Engineered prompts for root cause analysis |
| Confidence Algorithm | `src/core/confidence.py` | Proprietary scoring formula |
| Decision Logic | `src/core/engine.py` | How decisions are made |
| Transient Detection | `src/core/engine.py` | Spike detection algorithm |

### What Customers Can See/Configure

| Component | How Exposed | Description |
|-----------|-------------|-------------|
| Thresholds | Environment Variables | `CONFIDENCE_AUTO_THRESHOLD=80` |
| Adapter Selection | Environment Variables | `MONITORING_ADAPTER=prometheus` |
| Scaling Limits | Environment Variables | `SCALING_MAX_REPLICAS=10` |
| API Endpoints | REST API | `/api/v1/analyze`, etc. |
| Input/Output Schema | API Documentation | Request/response JSON format |

### Why Container Approach Works

1. **Code is compiled/bundled** - Not visible as source
2. **No access to filesystem** - Container is read-only
3. **Only API exposed** - Customers interact via HTTP only
4. **Secrets injected at runtime** - Not baked into image

---

## 4. Folder Structure

```
Anomaly-Agent/
├── docs/                           # Documentation
│   ├── CONTEXT.md                  # This file - project context
│   ├── IMPLEMENTATION_GUIDE.md     # Step-by-step setup guide
│   └── QUANTNIK_SDLC_INTEGRATION.md    # Frontend integration guide
│
├── src/                            # Source code
│   ├── main.py                     # FastAPI application entry
│   ├── __init__.py
│   │
│   ├── config/                     # Configuration
│   │   ├── __init__.py
│   │   └── settings.py             # Pydantic settings (env vars)
│   │
│   ├── api/                        # REST API layer
│   │   ├── __init__.py
│   │   ├── routes.py               # Endpoint definitions
│   │   └── schemas.py              # Request/response models
│   │
│   ├── core/                       # Core engine (PROTECTED IP)
│   │   ├── __init__.py
│   │   ├── engine.py               # Main AnomalyEngine class
│   │   ├── prompts.py              # AI prompt templates
│   │   └── confidence.py           # Scoring algorithm
│   │
│   ├── adapters/                   # External integrations
│   │   ├── __init__.py
│   │   │
│   │   ├── ai_providers/           # LLM providers
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Abstract base class
│   │   │   ├── gemini.py           # Google Gemini
│   │   │   ├── bedrock.py          # AWS Bedrock
│   │   │   ├── vertex.py           # Google Vertex AI
│   │   │   ├── openai_provider.py  # OpenAI
│   │   │   └── azure_openai.py     # Azure OpenAI
│   │   │
│   │   └── monitoring/             # Monitoring tools
│   │       ├── __init__.py
│   │       ├── base.py             # Abstract base class
│   │       ├── datadog.py          # Datadog
│   │       ├── prometheus.py       # Prometheus/Alertmanager
│   │       └── cloudwatch.py       # AWS CloudWatch
│   │
│   └── kubernetes/                 # K8s operations
│       ├── __init__.py
│       └── client.py               # Scale, restart, rollback
│
├── deploy/                         # Deployment configs
│   ├── kubernetes/
│   │   ├── deployment.yaml         # K8s Deployment + Service + RBAC
│   │   ├── configmap.yaml          # Customer configuration
│   │   └── secrets.yaml.example    # Secrets template
│   └── harness/
│       └── anomaly-agent-cicd.yaml # Harness CI/CD pipeline
│
├── Dockerfile                      # Container build
├── requirements.txt                # Python dependencies
├── .gitignore                      # Git ignore rules
└── README.md                       # Project overview
```

---

## 5. Key Design Decisions

### 5.1 Adapter Pattern

**Decision:** Use abstract base classes for AI providers and monitoring tools.

**Why:**
- Customers use different tools (Datadog vs Prometheus vs CloudWatch)
- Customers prefer different AI providers (Gemini vs Bedrock vs OpenAI)
- Adding new adapters doesn't require changing core logic

**Implementation:**
```python
# Factory function creates the right adapter based on config
ai_provider = get_ai_provider(
    provider=settings.ai_provider,  # "gemini", "bedrock", etc.
    api_key=settings.ai_api_key,
    model=settings.ai_model
)
```

### 5.2 Confirmation Wait

**Decision:** Wait 5 minutes (configurable) before taking action.

**Why:**
- CPU spikes are often transient (burst traffic, batch job)
- Prevents unnecessary scaling for self-resolving issues
- Reduces noise and cost

**Implementation:**
```python
# In engine.py
if not skip_confirmation_wait:
    await asyncio.sleep(settings.confirmation_wait_seconds)
# Then check if CPU is still high
```

### 5.3 Confidence-Based Decisions

**Decision:** Use confidence thresholds for automation levels.

**Why:**
- High confidence (≥80%) → Safe to auto-remediate
- Medium confidence (60-79%) → Needs human review
- Low confidence (<60%) → Just monitor, don't act

**Implementation:**
```python
if confidence >= settings.confidence_auto_threshold:
    decision = PipelineDecision.PROCEED_AUTOMATION
elif confidence >= settings.confidence_review_threshold:
    decision = PipelineDecision.HUMAN_REVIEW
else:
    decision = PipelineDecision.MONITORING_ONLY
```

### 5.4 Environment Variables for Config

**Decision:** All configuration via environment variables, not config files.

**Why:**
- Works with Kubernetes ConfigMaps and Secrets
- Easy to change without rebuilding container
- Standard 12-factor app practice
- Customers can customize without seeing code

---

## 6. API Reference

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check (for load balancers) |
| `GET` | `/live` | Liveness probe (for K8s) |
| `GET` | `/ready` | Readiness probe (for K8s) |
| `GET` | `/api/v1/status` | System status + recent alerts |
| `POST` | `/api/v1/analyze` | Analyze alert, return AI decision |
| `POST` | `/api/v1/remediate` | Execute K8s action |
| `POST` | `/api/v1/chat` | Chatbot interaction |

### Key Request/Response Examples

**Analyze Alert:**
```json
// POST /api/v1/analyze
// Request:
{
  "alert_payload": {
    "title": "High CPU Alert",
    "alert_metric": "kubernetes.cpu.usage.total",
    "alert_value": 92,
    "hostname": "eks-node-1",
    "pod_name": "my-app-abc123",
    "kube_namespace": "production"
  }
}

// Response:
{
  "request_id": "uuid",
  "confidence_score": 85,
  "pipeline_decision": "PROCEED_AUTOMATION",
  "automation_approved": true,
  "recommended_action": {
    "action_type": "scale_up",
    "target_replicas": 3,
    "rationale": "CPU consistently above 90%, scaling recommended"
  },
  "root_cause_analysis": "High traffic causing CPU saturation...",
  "executive_summary": "Production pod experiencing sustained high CPU...",
  "transient_resolved": false
}
```

---

## 7. Environment Variables Reference

### Adapter Selection
| Variable | Options | Default |
|----------|---------|---------|
| `MONITORING_ADAPTER` | datadog, prometheus, cloudwatch, splunk, dynatrace | datadog |
| `AI_PROVIDER` | gemini, bedrock, vertex, openai, azure_openai | gemini |

### Thresholds
| Variable | Range | Default | Description |
|----------|-------|---------|-------------|
| `CONFIDENCE_AUTO_THRESHOLD` | 0-100 | 80 | Auto-remediate if ≥ this |
| `CONFIDENCE_REVIEW_THRESHOLD` | 0-100 | 60 | Human review if between this and auto |
| `TRANSIENT_CPU_THRESHOLD` | 0-100 | 50 | CPU below this = transient |
| `CONFIRMATION_WAIT_SECONDS` | 0+ | 300 | Wait before confirming issue |

### Scaling
| Variable | Range | Default | Description |
|----------|-------|---------|-------------|
| `SCALING_MIN_REPLICAS` | 1+ | 1 | Minimum pods |
| `SCALING_MAX_REPLICAS` | 1+ | 10 | Maximum pods |
| `SCALING_COOLDOWN_SECONDS` | 0+ | 300 | Wait between scaling ops |

### Behavior
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AUTO_REMEDIATE_ENABLED` | bool | true | Enable auto-remediation |
| `REQUIRE_HUMAN_APPROVAL` | bool | false | Always require approval |

### AI Settings
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AI_MODEL` | string | gemini-2.5-flash | Model name |
| `AI_TIMEOUT_SECONDS` | int | 30 | API timeout |
| `AI_MAX_TOKENS` | int | 8192 | Max response tokens |

### Secrets
| Variable | Description |
|----------|-------------|
| `AI_API_KEY` | API key for AI provider |
| `MONITORING_API_KEY` | API key for monitoring tool |
| `MONITORING_APP_KEY` | App key (Datadog only) |

---

## 8. Integration Points

### 8.1 Monitoring Tool → Anomaly Agent

**Webhook Configuration:**
- Datadog: Create webhook pointing to `/api/v1/analyze`
- Prometheus: Configure Alertmanager webhook receiver
- CloudWatch: Use SNS to trigger Lambda → API call

### 8.2 Anomaly Agent → Kubernetes

**Required RBAC Permissions:**
```yaml
rules:
- apiGroups: ["apps"]
  resources: ["deployments", "deployments/scale"]
  verbs: ["get", "list", "watch", "patch", "update"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
```

### 8.3 quantnik-sdlc Frontend → Anomaly Agent

**API Integration:**
- Base URL: `VITE_ANOMALY_AGENT_URL` environment variable
- Uses existing `apiClient.ts` for authenticated requests
- Components: `AnomalyDashboard.tsx`, `AnomalyChatbot.tsx`

---

## 9. Customer Deployment Variations

### Example: Bank (High Security)

```yaml
# Conservative settings
MONITORING_ADAPTER: prometheus
AI_PROVIDER: azure_openai  # Data stays in Azure
CONFIDENCE_AUTO_THRESHOLD: "90"  # Very high bar for auto
REQUIRE_HUMAN_APPROVAL: "true"   # Always need approval
SCALING_MAX_REPLICAS: "50"
```

### Example: Retail (High Automation)

```yaml
# Aggressive automation
MONITORING_ADAPTER: datadog
AI_PROVIDER: gemini
CONFIDENCE_AUTO_THRESHOLD: "75"  # Lower bar, more automation
AUTO_REMEDIATE_ENABLED: "true"
REQUIRE_HUMAN_APPROVAL: "false"
CONFIRMATION_WAIT_SECONDS: "120"  # Faster response
```

### Example: Healthcare (Compliance)

```yaml
# Balance of automation and oversight
MONITORING_ADAPTER: cloudwatch
AI_PROVIDER: bedrock  # AWS-native, HIPAA compliant
CONFIDENCE_AUTO_THRESHOLD: "85"
CONFIRMATION_WAIT_SECONDS: "300"
NOTIFICATION_EMAIL: "oncall@hospital.com"
```

---

## 10. Development Environment Setup (Ubuntu)

### Quick Setup

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install Docker
sudo apt install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# 3. Install Python 3 and venv (Ubuntu 22.04 has Python 3.10)
sudo apt install -y python3 python3-venv python3-pip

# 4. Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install && rm -rf aws awscliv2.zip

# 5. Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# 6. Install Node.js (for frontend)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 7. Logout and login again for Docker group
```

### Local Development

```bash
cd ~/quantnik-projects/anomaly-agent

# Create virtual environment (Ubuntu 22.04 has Python 3.10)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run locally
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8080

# Test
curl http://localhost:8080/health
```

---

## 11. Useful Commands

### Docker
```bash
docker build -t quantnik-anomaly-agent:latest .
docker run -d -p 8080:8080 --name test quantnik-anomaly-agent:latest
docker logs test
docker stop test && docker rm test
```

### AWS ECR
```bash
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.ap-south-1.amazonaws.com
docker tag quantnik-anomaly-agent:latest <ecr-uri>:latest
docker push <ecr-uri>:latest
```

### Kubernetes
```bash
kubectl get pods -n quantnik-system
kubectl logs -l app=quantnik-anomaly-agent -n quantnik-system
kubectl port-forward svc/quantnik-anomaly-agent -n quantnik-system 8080:80
kubectl rollout restart deployment/quantnik-anomaly-agent -n quantnik-system
```

---

## 12. Future Enhancements

| Feature | Priority | Description |
|---------|----------|-------------|
| Splunk Adapter | High | Add Splunk monitoring support |
| Dynatrace Adapter | High | Add Dynatrace monitoring support |
| Memory Remediation | Medium | Handle memory alerts, not just CPU |
| Slack Integration | Medium | Send notifications to Slack |
| PagerDuty Integration | Medium | Create incidents in PagerDuty |
| Multi-cluster Support | Low | Manage multiple K8s clusters |

### Adding New Adapters

**To add a new monitoring adapter:**
1. Create `src/adapters/monitoring/new_tool.py`
2. Extend `BaseMonitoringAdapter`
3. Implement: `parse_webhook`, `fetch_metrics`, `fetch_cpu_metrics`, `fetch_memory_metrics`, `health_check`
4. Add to `get_monitoring_adapter()` in `base.py`
5. Update documentation

**To add a new AI provider:**
1. Create `src/adapters/ai_providers/new_provider.py`
2. Extend `BaseAIProvider`
3. Implement: `analyze`, `health_check`
4. Add to `get_ai_provider()` in `base.py`
5. Update documentation

---

## 13. Implementation Status (As of 2026-04-30)

### Current Deployment

| Component | Status | Details |
|-----------|--------|---------|
| **AI Agent API** | ✅ Live | Running on AWS EKS |
| **Public URL** | ✅ Active | `http://k8s-quantniksyst-quantnikanom-0573c24f8a-975249009.ap-south-1.elb.amazonaws.com` |
| **Swagger UI** | ✅ Working | `/docs` endpoint enabled |
| **Gemini AI** | ✅ Connected | AI provider healthy |
| **Datadog** | ✅ Connected | Monitoring adapter healthy |
| **ECR Image** | ✅ Pushed | `145748108830.dkr.ecr.ap-south-1.amazonaws.com/quantnik-quantnik-anomaly:1.0.1` |
| **Harness Pipeline** | ✅ Created | `AnomalyAgent-CICD` in `QUANTNIK_Build_AI` project |

### Kubernetes Resources

```
Namespace: quantnik-system
Deployment: quantnik-anomaly-agent (2 replicas)
Service: quantnik-anomaly-agent (ClusterIP, port 80 → 8080)
Ingress: quantnik-anomaly-agent (ALB, internet-facing)
ConfigMap: quantnik-anomaly-config
Secret: quantnik-anomaly-secrets
```

### API Endpoints (Verified Working)

| Endpoint | Method | Status |
|----------|--------|--------|
| `/health` | GET | ✅ Working |
| `/live` | GET | ✅ Working |
| `/ready` | GET | ✅ Working |
| `/docs` | GET | ✅ Working (Swagger UI) |
| `/api/v1/status` | GET | ✅ Working |
| `/api/v1/chat` | POST | ✅ Working |
| `/api/v1/analyze` | POST | ✅ Working |
| `/api/v1/remediate` | POST | ✅ Working |

### Phases Completed

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Repository Setup (Harness Code) | ✅ Done |
| Phase 2 | Backend Implementation | ✅ Done |
| Phase 3 | Docker Container | ✅ Done |
| Phase 4 | AWS ECR Setup | ✅ Done |
| Phase 5 | Kubernetes Deployment | ✅ Done |
| Phase 6 | Harness CI/CD Pipeline | ✅ Done |
| Phase 7 | Frontend Integration | ⏳ Pending |
| Phase 8 | Testing | 🔄 In Progress |
| Phase 9 | Customer Deployment | ⏳ Pending |

### Issues Resolved

| Issue | Root Cause | Resolution |
|-------|------------|------------|
| Python 3.11 not found | Not in Ubuntu 22.04 repos | Use `python3` (3.10) |
| runAsNonRoot error | Non-numeric user in Dockerfile | Use UID 10001 |
| ErrImagePull | Wrong image name in deployment | Manual fix |
| ALB not provisioning | Missing IAM AddTags permission | Added IAM policy |
| ALB 504 timeout | Health check path was `/` | Changed to `/health` |
| Targets unhealthy | Security group blocking 8080 | Added inbound rule |
| Git clone failed | Branch not specified | Added `branch: main` |
| `/docs` not found | DEBUG=false | Set DEBUG=true |

### Remaining Tasks

| Priority | Task | Estimated Time |
|----------|------|----------------|
| 1 | Set up Datadog webhook | 15 min |
| 2 | Test real alert flow | 30 min |
| 3 | Frontend integration (quantnik-sdlc) | 2-4 hours |
| 4 | Fix Harness pipeline resources | 30 min |
| 5 | Customer deployment documentation | 1 hour |

---

## 13.1 Phase 7: Frontend Integration - Detailed Plan

### Current quantnik-sdlc UI Structure

Based on screenshot analysis, AI Agents appear in the **Prompt Library** sidebar:
- Agents listed: BRD Generator, BRD Summary, User Stories Creator, User Stories Validator, Code Assistant, Test Case, Test Script, Test Data, User Manual
- Each agent is selectable from the sidebar
- Selected agent shows a chatbot interface with "Welcome! I am quantnik agent. How can I help you?"

### Integration Approach Decision: Chatbot Component

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Option A: Reuse EmbeddedChatbot.tsx** | ✅ Consistent UX with existing agents<br>✅ All features built-in (streaming, history, settings)<br>✅ Already handles authentication<br>✅ 5985 lines of battle-tested code | ❌ Complex to modify<br>❌ Need to understand orchestrator routing<br>❌ May have dependencies on other services | **Phase 2** - After MVP |
| **Option B: Simple Dedicated Chatbot** | ✅ Quick to implement<br>✅ Easy to customize for anomaly-specific UI<br>✅ No risk of breaking existing functionality<br>✅ Can add anomaly-specific features (alert display, remediation buttons) | ❌ Separate codebase to maintain<br>❌ May have UX inconsistency initially | **Phase 1** - MVP |

**Decision:** Start with **Option B (Simple)** for MVP, then migrate to **Option A** for consistency.

### Integration Approach Decision: SDLC Phase Placement

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Option A: Add to ReliabilityDetail.tsx** | ✅ Logical placement (reliability/monitoring)<br>✅ Follows existing pattern<br>✅ Less code changes | ❌ May clutter existing page<br>❌ Limited customization | Consider for v2 |
| **Option B: Create AnomalyAgentDetail.tsx** | ✅ Dedicated page for anomaly features<br>✅ Full control over UI/UX<br>✅ Can add dashboard + chatbot<br>✅ Room for future features | ❌ More files to create<br>❌ Need to add to navigation | **Recommended** |

**Decision:** Create **AnomalyAgentDetail.tsx** as a new dedicated component.

### Dashboard Approach Decision

| Approach | Features | Effort | Recommendation |
|----------|----------|--------|----------------|
| **Phase 1: Simple Status** | Health check, AI/Monitoring status, basic chat | 2 hours | **MVP** |
| **Phase 2: Full Dashboard** | Metrics charts, alert history table, remediation log, real-time updates | 4-6 hours | **Future** |

**Decision:** Start with **Simple Status View**, add full dashboard features later.

### Files to Create (MVP)

| # | File | Purpose | Priority |
|---|------|---------|----------|
| 1 | `src/services/anomalyAgentApi.ts` | API client for Anomaly Agent | P1 |
| 2 | `src/components/AnomalyAgent/AnomalyAgentChat.tsx` | Simple chat interface | P1 |
| 3 | `src/components/AnomalyAgent/AnomalyAgentStatus.tsx` | Health/status display | P1 |
| 4 | `src/components/AnomalyAgent/index.tsx` | Main component combining chat + status | P1 |
| 5 | Update sidebar/navigation | Add "Anomaly Agent" to Prompt Library | P1 |
| 6 | Update `.env` | Add `VITE_ANOMALY_AGENT_URL` | P1 |

### Future Enhancements (To-Do List)

| Priority | Feature | Description | Estimated Effort |
|----------|---------|-------------|------------------|
| P2 | Full Dashboard | Metrics charts, alert history, remediation log | 4-6 hours |
| P2 | EmbeddedChatbot Integration | Migrate to use existing chatbot for consistency | 2-3 hours |
| P2 | Real-time Updates | WebSocket for live alert notifications | 3-4 hours |
| P3 | Alert Timeline | Visual timeline of alerts and remediations | 2-3 hours |
| P3 | Confidence Score Visualization | Charts showing AI confidence trends | 2 hours |
| P3 | Remediation Approval Workflow | UI for human-in-the-loop approvals | 3-4 hours |
| P3 | Multi-cluster Support | Dashboard for multiple K8s clusters | 4-6 hours |
| P4 | Add to ReliabilityDetail.tsx | Integrate into SDLC journey view | 2 hours |

### Environment Configuration

```bash
# Add to quantnik-sdlc/.env
VITE_ANOMALY_AGENT_URL=http://k8s-quantniksyst-quantnikanom-0573c24f8a-975249009.ap-south-1.elb.amazonaws.com
```

### API Endpoints to Integrate

| Endpoint | Method | Use Case |
|----------|--------|----------|
| `/health` | GET | Status indicator (green/red) |
| `/api/v1/status` | GET | Detailed status for dashboard |
| `/api/v1/chat` | POST | Chatbot messages |
| `/api/v1/analyze` | POST | Manual alert analysis (future) |
| `/api/v1/remediate` | POST | Manual remediation trigger (future) |

### Quick Access

```bash
# Health check
curl http://k8s-quantniksyst-quantnikanom-0573c24f8a-975249009.ap-south-1.elb.amazonaws.com/health

# Swagger UI
http://k8s-quantniksyst-quantnikanom-0573c24f8a-975249009.ap-south-1.elb.amazonaws.com/docs

# Chat with AI
curl -X POST http://k8s-quantniksyst-quantnikanom-0573c24f8a-975249009.ap-south-1.elb.amazonaws.com/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you help me with?"}'
```

---

## 14. Related Documents

| Document | Location | Purpose |
|----------|----------|---------|
| Implementation Guide | `docs/IMPLEMENTATION_GUIDE.md` | Step-by-step setup |
| Frontend Integration | `docs/QUANTNIK_SDLC_INTEGRATION.md` | quantnik-sdlc changes |
| K8s Deployment | `deploy/kubernetes/deployment.yaml` | K8s manifests |
| Original Pipeline | `../AnomalyAWS_EKS.yaml` | Reference Harness pipeline |

---

## 14. Contacts & Ownership

| Role | Responsibility |
|------|----------------|
| DevOps Team | Deployment, CI/CD, infrastructure |
| Backend Team | Anomaly Agent development |
| Frontend Team | quantnik-sdlc integration |
| AI/ML Team | Prompt engineering, model selection |

---

**End of Context Document**
