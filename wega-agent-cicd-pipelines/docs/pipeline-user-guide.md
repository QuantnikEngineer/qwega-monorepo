# WEGA CI/CD Pipeline User Guide

## Overview

This guide explains how to run the WEGA CI/CD pipelines in Harness. The pipelines support building and deploying multiple microservices to different cloud platforms.

---

## Available Pipelines

| Pipeline | Description | Deploy Target |
|----------|-------------|---------------|
| `RepoWorkerBuildDeployCloudRun` | Build and deploy to Google Cloud Run | GCP Cloud Run |
| `RepoWorkerBuildDeployACA` | Build and deploy to Azure Container Apps | Azure Container Apps |
| `RepoWorkerBuildDeployEKS` | Build and deploy to AWS EKS | AWS EKS (Kubernetes) |
| `RepoWorkerBuildDeployGKE` | Build and deploy to Google GKE | GCP GKE (Kubernetes) |
| `RepoWorkerBuildDeployAKS` | Build and deploy to Azure AKS | Azure AKS (Kubernetes) |

> **Note**: WEGA 3.0 repositories are automatically synced to both CloudRun and ACA pipelines.

---

## Quick Start

### Step 1: Access Harness

1. Login to Harness: `https://app.harness.io`
2. Navigate to **Project**: `WEGA_Build_AI`
3. Go to **Pipelines** in the left menu

### Step 2: Select Pipeline

Choose the appropriate pipeline based on your deployment target:
- **Cloud Run**: `RepoWorkerBuildDeployCloudRun`
- **AWS EKS**: `RepoWorkerBuildDeployEKS`
- **Google GKE**: `RepoWorkerBuildDeployGKE`
- **Azure AKS**: `RepoWorkerBuildDeployAKS`

### Step 3: Click "Run"

Click the **Run** button in the top-right corner.

---

## Pipeline Input Parameters

### Common Parameters (All Pipelines)

| Parameter | Description | Options | Default |
|-----------|-------------|---------|---------|
| `selectedRepo` | Which repository to build | `all` or specific repo name | `all` |
| `executionMode` | What action to perform | `build_only`, `deploy_only`, `build_and_deploy` | `build_and_deploy` |
| `environment` | Target deployment environment | `dev`, `qa`, `staging`, `production`, `all` | `dev` |
| `imageTag` | Docker image tag | Any string or auto-generated | `<pipeline.executionId>` |

### Branch Parameters

Each repository has its own branch parameter:

| Parameter | Repository | Allowed Values |
|-----------|------------|----------------|
| `branchWEGABRD` | WEGA-BRD | main, develop, dev, dev-no-sso, release, feature/brd |
| `branchWegaOrchestratorAgent` | Wega-Orchestrator-Agent | main, develop, dev, dev-no-sso, release |
| `branchWegaUserstoryToTestcasesAgent` | Wega-userstory-to-testcases-agent | main, develop, dev, dev-no-sso, release |
| `branchWegaBrdSummaryAgent` | Wega-brd-summary-agent | main, develop, dev, dev-no-sso, release |
| `branchWegaTestcasesToScriptAgent` | wega-testcases-to-script-agent | main, develop, dev, dev-no-sso, release |
| `branchWegaBrdAnalyzerAgent` | Wega-Brd-Analyzer-Agent | main, develop, dev, dev-no-sso, release |
| `branchDevelopmentAgent` | development-agent | main, develop, dev, dev-no-sso, release |
| `branchWegaStagingFigma` | Wega-Staging-figma | main, develop, dev, dev-no-sso, release |

---

## Execution Modes

### 1. Build and Deploy (`build_and_deploy`)

**Use when**: You want to build new images AND deploy them.

```
executionMode: build_and_deploy
environment: dev (or all for full promotion)
```

**Flow**:
1. Clone repository
2. Run security scans (SonarCloud, Semgrep, TruffleHog)
3. Build Docker images
4. Push to container registry
5. Run Trivy container scan
6. Deploy to selected environment(s)

### 2. Build Only (`build_only`)

**Use when**: You only want to build and push images without deploying.

```
executionMode: build_only
```

**Flow**:
1. Clone repository
2. Run security scans
3. Build Docker images
4. Push to container registry
5. Run Trivy container scan
6. **STOP** (no deployment)

### 3. Deploy Only (`deploy_only`)

**Use when**: You want to deploy an existing image (already built).

```
executionMode: deploy_only
imageTag: <existing-image-tag>
environment: qa
```

**Flow**:
1. Skip build steps
2. Deploy specified image tag to target environment

---

## Environment Deployment

### Single Environment

Deploy to a specific environment only (no promotion flow):

```
environment: dev         # Deploy to Dev only - exits after Dev
environment: qa          # Deploy to Dev → QA only - exits after QA  
environment: stage       # Deploy to Dev → QA → Stage only
environment: production  # Full promotion flow to Production
```

> **Important**: When you select a specific environment (e.g., `dev`), the pipeline will deploy ONLY to that environment and exit. Approval gates for subsequent environments are skipped.

### Full Promotion (`all`)

Deploy through all environments with approval gates:

```
environment: all
```

**Flow**:
```
Dev → [Approval] → QA → [Approval] → Staging → [Approval] → Production
```

- **Approval Timeout**: 14 days
- **QA/Staging Approval**: Minimum 1 approver
- **Production Approval**: Minimum 2 approvers (executor cannot approve)

### Service Naming Convention

Services are created with environment prefix:
- **Dev**: `dev-<service-name>` (e.g., `dev-wega-brd-backend`)
- **QA**: `qa-<service-name>`
- **Stage**: `stage-<service-name>`
- **Production**: `prod-<service-name>`

---

## Running Specific Repositories

### Build All Repositories

```
selectedRepo: all
```

### Build Single Repository

```
selectedRepo: WEGA-BRD
```

### Build Multiple Repositories

Use comma-separated values or partial match:

```
selectedRepo: WEGA-BRD,Wega-Orchestrator-Agent
```

---

## Example Scenarios

### Scenario 1: Build and Deploy Single Repo to Dev

```yaml
selectedRepo: WEGA-BRD
executionMode: build_and_deploy
environment: dev
branchWEGABRD: develop
```

### Scenario 2: Build All Repos (No Deployment)

```yaml
selectedRepo: all
executionMode: build_only
branchWEGABRD: main
branchWegaOrchestratorAgent: main
# ... set all branch parameters
```

### Scenario 3: Deploy Existing Image to Production

```yaml
selectedRepo: WEGA-BRD
executionMode: deploy_only
environment: production
imageTag: abc123def456  # Existing image tag from previous build
```

### Scenario 4: Full Promotion (Dev → QA → Staging → Prod)

```yaml
selectedRepo: all
executionMode: build_and_deploy
environment: all
branchWEGABRD: release
# ... set all branch parameters to release
```

---

## Security Scans

Each pipeline run includes these security scans:

| Scan | Tool | Purpose | Status |
|------|------|---------|--------|
| SAST | Semgrep | Static Application Security Testing | Active |
| Secrets | TruffleHog | Detect hardcoded secrets | Active |
| Container | Trivy | Container image vulnerability scanning | Active |
| Code Quality | SonarCloud | Code quality and security analysis | Disabled |
| SAST | Fortify on Demand | Enterprise SAST | Disabled |
| SAST | Harness SAST (ShiftLeft) | Native Harness SAST | Disabled (requires license) |

> **Note**: SonarCloud, Fortify, and Harness SAST steps are disabled but can be re-enabled when needed.

### Viewing Security Results

1. After pipeline completion, go to **Security Tests** tab
2. Or check the **Artifacts** section for JSON reports:
   - `semgrep-report.json`
   - `trufflehog-report.json`
   - `trivy-backend-report.json`
   - `trivy-frontend-report.json`

---

## Pipeline Stages

### Build Stage (`Build_Repo_*`)

1. **Display_Repo_Info** - Shows repository details
2. **Resolve_Branch_For_Repo** - Determines branch to build
3. **CloneRepo** - Clones source code
4. **SonarCloud_Scan** - Code quality analysis
5. **TruffleHog_Secret_Scan** - Secrets detection
6. **Semgrep_SAST_Scan** - SAST analysis
7. **BuildAndPush_Backend** - Build backend Docker image
8. **BuildAndPush_Frontend** - Build frontend Docker image (if applicable)
9. **Trivy_Container_Scan** - Scan container images
10. **Prepare_STO_Ingestion_Files** - Prepare security reports
11. **STO_Ingest_**** - Ingest reports to Harness STO

### Deploy Stages

- **Deploy_Dev** - Deploy to Development
- **Approval_QA** - Wait for QA approval
- **Deploy_QA** - Deploy to QA
- **Approval_Staging** - Wait for Staging approval
- **Deploy_Staging** - Deploy to Staging
- **Approval_Production** - Wait for Production approval
- **Deploy_Production** - Deploy to Production

---

## Repositories Catalog

### WEGA 3.0 Repositories (Cloud Run + ACA)

| Repository | Backend Image | Frontend Image | CloudRun Service | ACA Service |
|------------|---------------|----------------|------------------|-------------|
| WEGA-BRD | wega-brd-backend | - | wega-brd-backend | wega-brd |
| Wega-userstory-to-testcases-agent | wega-userstory-to-testcases-agent-backend | - | wega-userstory-to-testcases-agent | wega-userstory-to-testcases-agent |
| Wega-brd-summary-agent | wega-brd-summary-agent-backend | - | wega-brd-summary-agent | wega-brd-summary-agent |
| wega-testcases-to-script-agent | wega-testcases-to-script-agent-backend | - | wega-testcases-to-script-agent | wega-testcases-to-script-agent |
| Wega-Staging | wega-staging-frontend | - | wega-staging | wega-staging |
| Wega-sdlc-orchestrator | wega-sdlc-orchestrator-backend | - | wega-sdlc-orchestrator | wega-sdlc-orchestrator |
| Wega-planning-orchestrator | wega-planning-orchestrator-backend | - | wega-planning-orchestrator | wega-planning-orchestrator |
| Wega-test-orchestrator | wega-test-orchestrator-backend | - | wega-test-orchestrator | wega-test-orchestrator |
| wega-code-assistant-agent | wega-code-assistant-agent-backend | - | wega-code-assistant-agent | wega-code-assistant-agent |
| wega-sdlc | wega-sdlc-backend | - | wega-sdlc | wega-sdlc |

> **Note**: WEGA 3.0 repos deploy to both Cloud Run and Azure Container Apps (ACA).

### WEGA 1.0 Repositories (EKS)

| Repository | Backend Image | Frontend Image |
|------------|---------------|----------------|
| development-agent | development-agent-backend | development-agent-frontend |
| buildaicode-wega_rag_1 | buildaicode-wega-rag-1-backend | buildaicode-wega-rag-1-frontend |
| code-to-documentation-agent | code-to-documentation-agent-backend | code-to-documentation-agent-frontend |
| project-scaffolding-agent | project-scaffolding-agent-backend | project-scaffolding-agent-frontend |
| functional-testing-agent | functional-testing-agent-backend | functional-testing-agent-frontend |
| planning-agent | planning-agent-backend | planning-agent-frontend |
| unit-test-case-agent | unit-test-case-agent-backend | unit-test-case-agent-frontend |
| requirement-agent | requirement-agent-backend | requirement-agent-frontend |
| bdd-agent | bdd-agent-backend | bdd-agent-frontend |

---

## Troubleshooting

### Common Issues

#### 1. Branch Not Allowed

**Error**: `The values provided for pipeline.variables.branchXXX do not match any of the allowed values`

**Solution**: Add the branch to the allowed values in the pipeline YAML, or select an allowed branch.

#### 2. Build Fails - Dockerfile Not Found

**Error**: `Dockerfile not found`

**Solution**: Verify the repository has a Dockerfile at the expected path (`source/Dockerfile` or `source/backend/Dockerfile`).

#### 3. Deployment Fails - Image Not Found

**Error**: `Image not found in registry`

**Solution**: 
- If using `deploy_only`, ensure the `imageTag` exists
- Check if the build stage completed successfully

#### 4. Approval Timeout

**Error**: Pipeline stuck at approval stage

**Solution**: 
- Check email for approval notification
- Login to Harness and approve the pending stage
- Approvals timeout after 14 days

### Getting Help

1. Check pipeline logs in Harness
2. Review the **Artifacts** tab for detailed reports
3. Contact the DevOps team for access issues

---

## Platform-Specific Configuration

### Cloud Run (GCP)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `gcpProjectId` | digital-rig-poc | GCP Project ID |
| `gcpRegion` | us-central1 | GCP Region |
| `garConnectorRef` | account.DigitalRigGCPConnector | Artifact Registry connector |

### EKS (AWS)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `awsRegion` | us-west-2 | AWS Region |
| `awsAccountId` | 145748108830 | AWS Account ID |
| `ecrConnectorRef` | account.WEGAAWSHarnessconnector | ECR connector |
| `k8sNamespace` | wega-wipro-buildai | Kubernetes namespace |

---

## Automated Sync Pipelines

### Branch Options Sync

**Pipeline**: `SyncOrchestratorBranchOptions`  
**Schedule**: Every 30 minutes  
**Purpose**: Syncs live repository branches into orchestrator pipeline branch allowed values.

### Onboarding Catalog Sync

**Pipeline**: `SyncOnboardingReposCatalog`  
**Purpose**: Syncs onboardingrepos.yaml catalog into orchestrator and all worker pipelines (CloudRun, ACA, EKS, GKE, AKS).

**What it syncs**:
- Repository matrices in build/deploy stages
- Branch variables
- Branch resolver scripts
- Removes old/stale repositories not in catalog

---

## Onboarding New Repositories

1. Add the repository to `.harness/catalog/onboardingrepos.yaml`:

```yaml
- repoName: your-new-repo
  branch: develop
  wegaVersion: "3.0"
  deployTarget: cloudrun
  backend:
    dockerfile: source/Dockerfile
    context: source/
    imageName: your-new-repo-backend
    cloudRunService: your-new-repo
  serviceRef: yourNewRepoService
```

2. Commit and push the change
3. Run the `SyncOnboardingReposCatalog` pipeline
4. The new repo will be added to all relevant worker pipelines

---

**Document Version**: 2.0  
**Last Updated**: April 2026
