# WEGA CI/CD Agent

An enterprise-grade CI/CD pipeline generation service that transforms structured intent payloads into production-ready pipeline configurations. Supports multiple platforms including Azure DevOps, GitHub Actions, GitLab CI, Harness, and Jenkins with advanced deployment strategies for Azure Container Apps.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WEGA SDLC FRONTEND                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CI Pipeline Workspace: Configure → Generate → Publish → Execute   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DEPLOYMENT ORCHESTRATOR                                │
│                       (Routes CI/CD Requests)                               │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      WEGA CI/CD AGENT (This Project)                        │
│                               Port 8092                                     │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                    PIPELINE GENERATION ENGINE                       │    │
│  │                                                                     │    │
│  │   Intent ──▶ [Guardrails] ──▶ [Context Builder] ──▶ [Renderer]     │    │
│  │                                                          │          │    │
│  │                                                          ▼          │    │
│  │   Response ◀── [Validation] ◀── [Template/LLM Rendering]           │    │
│  │                                                                     │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      RENDER MODES                                   │    │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐                      │    │
│  │  │  Template  │ │    LLM     │ │   Hybrid   │                      │    │
│  │  │  (Jinja2)  │ │  (Gemini)  │ │ (Fallback) │                      │    │
│  │  └────────────┘ └────────────┘ └────────────┘                      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SUPPORTED PLATFORMS                               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │  Azure   │ │  GitHub  │ │  GitLab  │ │ Harness  │ │ Jenkins  │  │   │
│  │  │  DevOps  │ │  Actions │ │    CI    │ │    CI    │ │          │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Features

### Multi-Platform Pipeline Generation
- **Azure DevOps**: YAML pipelines with multi-stage deployments
- **GitHub Actions**: Workflow files with matrix builds
- **GitLab CI**: `.gitlab-ci.yml` with stages and jobs
- **Harness**: Native Harness pipeline YAML
- **Jenkins**: Declarative Jenkinsfile generation

### Azure Container Apps Deployment
- **Multi-Environment Stages**: Dev, QA, Prod deployment stages
- **ACR Integration**: Build and push to Azure Container Registry
- **Environment Provisioning**: Automatic Container Apps environment creation
- **Zero-Downtime Deployments**: Rolling updates with health checks

### Enterprise Controls
- **Approval Gates**: Manual validation before production deployments
- **Regional Rollout**: Multi-region deployment support
- **Image Tagging**: Semantic versioning and commit-based tags
- **Security Scanning**: Integration with security tools

### Render Modes
- **Template Mode**: Fast, deterministic Jinja2-based rendering
- **LLM Mode**: AI-powered generation using Google Gemini
- **Hybrid Mode**: LLM with template fallback for reliability

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/v1/catalog` | GET | Get supported platforms, tools, and stages |
| `/v1/pipelines/generate` | POST | Generate pipeline from intent payload |
| `/v1/sample-request` | GET | Get sample request payload |

## Request Format

### Pipeline Generation Request

```json
{
    "pipeline_name": "wega-payment-service",
    "prompt": "Build and deploy a Python FastAPI service to Azure Container Apps",
    "render_mode": "hybrid",
    "repository": {
        "url": "https://github.com/org/wega-payment-service.git",
        "branch": "main"
    },
    "target": {
        "platform": "azure-devops",
        "deployment_target": "container-apps",
        "environment": "dev",
        "regions": ["eastus"],
        "azureDevops": {
            "containerApps": {
                "serviceConnection": "azure-service-connection",
                "resourceGroup": "wega-rg",
                "location": "eastus",
                "containerAppName": "wega-payment-service",
                "containerAppEnvPrefix": "wega-aca",
                "acrName": "wegaacr",
                "acrLoginServer": "wegaacr.azurecr.io",
                "deploymentEnvironments": ["dev", "qa", "prod"],
                "triggerBranches": ["main"],
                "prBranches": ["main"]
            }
        }
    },
    "stages": [
        {
            "id": "install",
            "name": "Install Dependencies",
            "commands": ["pip install -r requirements.txt"]
        },
        {
            "id": "lint",
            "name": "Lint Code",
            "commands": ["ruff check ."]
        },
        {
            "id": "test",
            "name": "Run Tests",
            "commands": ["pytest tests/ -v --cov=app"]
        }
    ],
    "tools": [
        {"id": "python", "name": "Python", "version": "3.11"},
        {"id": "docker", "name": "Docker"}
    ],
    "build": {
        "artifact_type": "container",
        "image_repository": "wegaacr.azurecr.io/wega-payment-service",
        "image_tags": ["latest", "${BUILD_ID}"]
    },
    "execution": {
        "triggers": {
            "push": true,
            "pull_request": true
        },
        "approvals": {
            "enabled": true,
            "approvers": ["devops@company.com"],
            "timeout_minutes": 60
        }
    }
}
```

## Response Format

```json
{
    "status": "success",
    "summary": "Generated azure-devops CI pipeline with 5 stages and 2 selected tools.",
    "message": "Generated azure-devops CI pipeline with 5 stages and 2 selected tools.",
    "pipelineName": "wega-payment-service",
    "platform": "azure-devops",
    "artifact": {
        "path": "azure-pipelines.yml",
        "contentType": "text/yaml",
        "content": "trigger:\n  branches:\n    include:\n      - main\n..."
    },
    "normalizedIntent": {
        "pipeline_name": "wega-payment-service",
        "platform": "azure-devops",
        "stages": ["install", "lint", "test", "build", "deploy"],
        "renderMode": "hybrid"
    },
    "metadata": {
        "stage_count": 5,
        "tool_count": 2,
        "render_mode_requested": "hybrid",
        "render_mode_used": "template"
    }
}
```

## Project Structure

```
wega-ci-agent/
├── app/
│   ├── main.py                    # FastAPI application
│   ├── core/
│   │   ├── config.py              # Configuration management
│   │   ├── logging.py             # Structured logging
│   │   └── policies.py            # Enterprise policy enforcement
│   ├── models/
│   │   ├── requests.py            # Request models (GeneratePipelineRequest)
│   │   └── responses.py           # Response models
│   ├── services/
│   │   ├── pipeline_service.py    # Main pipeline generation service
│   │   ├── pipeline_context.py    # Context builder for templates
│   │   ├── pipeline_renderers.py  # Template and LLM renderers
│   │   ├── pipeline_guardrails.py # Input validation and security
│   │   ├── prompt_library.py      # LLM prompt management
│   │   ├── catalog_registry.py    # Platform/tool catalog
│   │   ├── command_resolver.py    # Stage command resolution
│   │   └── enterprise_controls.py # Approval and rollout logic
│   ├── templates/
│   │   ├── azure-pipelines.yml.j2 # Azure DevOps template
│   │   ├── workflow.yml.j2        # GitHub Actions template
│   │   ├── .gitlab-ci.yml.j2      # GitLab CI template
│   │   ├── harness-pipeline.yml.j2# Harness template
│   │   └── Jenkinsfile.j2         # Jenkins template
│   ├── prompts/
│   │   ├── azure-devops.prompt.txt.j2  # Azure DevOps LLM prompt
│   │   ├── github-actions.prompt.txt.j2
│   │   ├── gitlab-ci.prompt.txt.j2
│   │   ├── harness.prompt.txt.j2
│   │   └── jenkins.prompt.txt.j2
│   └── policies/
│       ├── catalogs.json          # Platform/tool definitions
│       ├── commands.json          # Stage command mappings
│       └── guardrails.json        # Security guardrails
├── tests/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development/production) | development |
| `PORT` | Server port | 8092 |
| `LOG_LEVEL` | Logging level | INFO |
| `DEFAULT_RENDER_MODE` | Default rendering mode | hybrid |
| `GOOGLE_API_KEY` | Google AI API key for LLM mode | - |
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex AI | - |
| `LLM_MODEL` | LLM model name | gemini-2.0-flash |
| `LLM_TEMPERATURE` | LLM temperature | 0.0 |
| `LLM_MAX_TOKENS` | Max output tokens | 8192 |
| `LLM_THINKING_BUDGET` | Thinking budget for Gemini | 1024 |
| `LLM_TIMEOUT_SECONDS` | LLM request timeout | 120 |

### Catalog Configuration

Platforms and tools are defined in `app/policies/catalogs.json`:

```json
{
    "platforms": [
        {
            "id": "azure-devops",
            "name": "Azure DevOps",
            "template": "azure-pipelines.yml.j2",
            "artifactPath": "azure-pipelines.yml"
        }
    ],
    "tools": [
        {
            "id": "python",
            "name": "Python",
            "category": "language",
            "defaultVersion": "3.11"
        },
        {
            "id": "docker",
            "name": "Docker",
            "category": "container"
        }
    ],
    "deploymentTargets": [
        {
            "id": "container-apps",
            "name": "Azure Container Apps",
            "platforms": ["azure-devops"]
        }
    ]
}
```

## Setup

### 1. Install Dependencies

```bash
cd wega-ci-agent
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Run the Service

```bash
python run.py
```

## Docker

```bash
docker build -t wega-ci-agent .
docker run -p 8092:8092 --env-file .env wega-ci-agent
```

## Generated Pipeline Example (Azure Container Apps)

```yaml
trigger:
  branches:
    include:
      - main

pr:
  branches:
    include:
      - main

variables:
  acrServiceConnection: 'azure-service-connection'
  acrName: 'wegaacr'
  acrLoginServer: 'wegaacr.azurecr.io'
  imageRepository: 'wega-payment-service'
  azureServiceConnection: 'azure-service-connection'
  resourceGroup: 'wega-rg'
  containerAppName: 'wega-payment-service'
  location: 'eastus'

stages:
  - stage: Build
    displayName: 'Build and Push'
    jobs:
      - job: BuildAndPush
        pool:
          vmImage: 'ubuntu-latest'
        steps:
          - checkout: self
          - task: UsePythonVersion@0
            inputs:
              versionSpec: '3.11'
          - script: |
              pip install -r requirements.txt
              ruff check .
              pytest tests/ -v --cov=app
            displayName: 'Install, Lint, Test'
          - task: AzureCLI@2
            displayName: 'Build and Push to ACR'
            inputs:
              azureSubscription: '$(azureServiceConnection)'
              scriptType: 'bash'
              scriptLocation: 'inlineScript'
              inlineScript: |
                az acr build \
                  --registry $(acrName) \
                  --image $(imageRepository):$(Build.BuildId) \
                  --image $(imageRepository):latest \
                  .

  - stage: DeployDev
    displayName: 'Deploy to Dev'
    dependsOn: Build
    jobs:
      - job: DeployToContainerApps
        pool:
          vmImage: 'ubuntu-latest'
        steps:
          - task: AzureCLI@2
            inputs:
              azureSubscription: '$(azureServiceConnection)'
              scriptType: 'bash'
              scriptLocation: 'inlineScript'
              inlineScript: |
                az containerapp update \
                  --name dev-$(containerAppName) \
                  --resource-group $(resourceGroup) \
                  --image $(acrLoginServer)/$(imageRepository):$(Build.BuildId)
```

## Integration with WEGA Platform

This service integrates with the WEGA SDLC platform:

1. **Deployment Orchestrator**: Routes pipeline generation requests
2. **Repository Lookup Service**: Fetches repository metadata and branches
3. **SDLC Frontend**: CI Pipeline Workspace UI for configuration
4. **Auth Service**: JWT token validation for secure API access

## See Also

- [WEGA Deployment Orchestrator](../wega-deployment-orchestrator) - Parent orchestrator
- [WEGA SDLC Frontend](../wega-sdlc) - Pipeline configuration UI
- [WEGA Auth Service](../wega-auth-service) - Authentication and authorization
