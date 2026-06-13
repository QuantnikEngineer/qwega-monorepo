# QUANTNIK Code Review Agent

QUANTNIK (WEbhook GitHub Agent) is an AI-powered code review service that automatically reviews pull requests using Google's Gemini AI. It integrates with GitHub and Jira to provide comprehensive, automated code reviews aligned with your project's requirements.

## About

QUANTNIK Code Review Agent is a FastAPI-based microservice that:

- Receives GitHub pull request webhooks and triggers automatic reviews
- Accepts natural language commands to initiate reviews on any PR
- Uses Gemini AI to analyze code changes for security issues, bugs, and best practices
- Validates PRs against Jira ticket requirements when linked
- Stores versioned review reports for tracking and auditing

### Key Features

- **Automated Reviews**: Triggers on PR opened or updated via webhooks
- **Natural Language Interface**: Start reviews with simple commands like "Review PR #42 in owner/repo"
- **Security Focus**: Detects vulnerabilities, CWE issues, and provides remediation suggestions
- **Jira Integration**: Validates code changes against acceptance criteria
- **Versioned Reports**: Every review is saved with a version number for historical tracking

## Deployment

### Prerequisites

- Python 3.11+
- A GitHub App with a private key (`.pem`) and the App installed on your target organization or repositories
- Google AI API key (Gemini)

### Quick Start

1. **Clone and install dependencies**
   ```bash
   cd quantnik-cara
   pip install -e .
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

   Required variables:
   - `ENVIRONMENT` - `development` (local) or `production`
   - `GITHUB_APP_ID` - Your GitHub App ID
   - `GITHUB_INSTALLATION_ID` - The installation ID for your org/repo
   - `GITHUB_PRIVATE_KEY` - **Behavior depends on `ENVIRONMENT`**:
     - `development` -> path to the PEM file (e.g. `~/Downloads/quantnik.pem`)
     - `production` -> the inline PEM contents (multi-line, quoted)
   - `GOOGLE_API_KEY` - Google AI API key

   Optional:
   - `GITHUB_WEBHOOK_SECRET` - For webhook signature verification
   - `GITHUB_TOKEN` - Static fallback token (used only if App auth is not configured)
   - `JIRA_*` variables for Jira integration

3. **Run the service**
   ```bash
   python main.py
   ```

   The API will be available at `http://localhost:8001` (override with `PORT=...`).
   Port `8001` is the default for CARA locally — the Planning Orchestrator runs on `8000`.

### How GitHub Authentication Works

QUANTNIK uses **GitHub App installation tokens**, which are minted and refreshed
automatically inside the service via PyGithub. You do not have to maintain a
short-lived `GITHUB_TOKEN` or run any cron/refresh job.

Order of precedence:

1. If `GITHUB_APP_ID` + `GITHUB_INSTALLATION_ID` + `GITHUB_PRIVATE_KEY` are set
   -> App auth (recommended; tokens auto-refresh).
2. Else if `GITHUB_TOKEN` is set -> static token (useful for quick local tests).
3. Else -> startup error.

Helper script `get_ghtoken.py` is provided for ad-hoc local token generation,
but it is **not needed** when App auth is configured.

### Production Secret Management

For production, never store the PEM in a file or commit it to Git. Recommended:

- **AWS** - Secrets Manager (or SSM Parameter Store with KMS), injected as env vars by ECS/Cloud Run/EKS
- **GCP** - Secret Manager, injected with `--set-secrets`
- **Azure** - Key Vault references in Container Apps / App Service
- **Kubernetes** - External Secrets Operator syncing from your cloud secret manager into a `Secret`, mounted as env via `secretKeyRef`
- **HashiCorp Vault** - Vault Agent Injector or sidecar pattern

Rotate the GitHub App private key periodically (regenerate in GitHub App settings).

### Docker Deployment

```bash
docker build -t quantnik-cara .

# Local-style (PEM file mounted in)
docker run -p 8001:8001 \
  -e PORT=8001 \
  -e ENVIRONMENT=development \
  -e GITHUB_APP_ID=123456 \
  -e GITHUB_INSTALLATION_ID=12345678 \
  -e GITHUB_PRIVATE_KEY=/secrets/quantnik.pem \
  -v $HOME/Downloads/quantnik.pem:/secrets/quantnik.pem:ro \
  -e GOOGLE_API_KEY=your_key \
  quantnik-cara

# Production-style (inline PEM via env)
docker run -p 8001:8001 \
  -e PORT=8001 \
  -e ENVIRONMENT=production \
  -e GITHUB_APP_ID=123456 \
  -e GITHUB_INSTALLATION_ID=12345678 \
  -e GITHUB_PRIVATE_KEY="$(cat /path/to/quantnik.pem)" \
  -e GOOGLE_API_KEY=your_key \
  quantnik-cara
```

## Usage

### Via GitHub Webhook

Configure your GitHub repository webhook:

- **URL**: `https://your-server/webhook`
- **Events**: Pull requests

QUANTNIK automatically reviews PRs when they're opened or updated.

### Via Natural Language

Send a review request to the `/prompt` endpoint:

```bash
curl -X POST http://localhost:8001/prompt \
  -H "Content-Type: application/json" \
  -d '{"command": "Review PR #11 in owner/repository"}'
```

Response:
```json
{
  "status": "accepted",
  "message": "Pull request review queued from natural language prompt.",
  "owner": "owner",
  "repo": "repository",
  "pr_number": 11,
  "source": "prompt"
}
```

### Retrieve Review Reports

Get the latest review report for a PR:

```bash
curl http://localhost:8001/reports/{owner}/{repo}/pulls/{pr_number}
```

Get a specific version:

```bash
curl "http://localhost:8001/reports/{owner}/{repo}/pulls/{pr_number}?version=2"
```

## QUANTNIK Orchestrator Integration

QUANTNIK can work alongside the QUANTNIK Orchestrator to provide a complete AI-driven development workflow. The orchestrator coordinates multiple AI agents that handle different aspects of the development process.

### Integration Points

1. **Webhook Coordination**: QUANTNIK receives PR events from GitHub and processes reviews. Results can be fed back to the orchestrator for further actions.

2. **API Integration**: The orchestrator can trigger reviews via the `/prompt` endpoint and fetch results from `/reports`.

3. **Result Processing**: Review findings (vulnerabilities, bugs, Jira alignment) can be used by other agents in the orchestrator to automatically comment on PRs, create tickets, or trigger additional workflows.

### Example Orchestrator Flow

```
GitHub PR Event
       ↓
QUANTNIK Orchestrator (coordinates agents)
       ↓
  ┌────┴────┐
  ↓         ↓
QUANTNIK    Other Agents
Review  (docs, tests,
 Agent   security)
       ↓
Orchestrator aggregates results → GitHub PR Comment / Slack Notification
```

### Environment Variables for Orchestrator

When running with the QUANTNIK Orchestrator, ensure:

- `APP_NAME` is set for identification
- `REPORTS_BASE_PATH` points to accessible storage if using shared volumes
- Service URL is exposed for orchestrator to reach
