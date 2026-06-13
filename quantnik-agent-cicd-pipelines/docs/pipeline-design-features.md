# Pipeline Design Features

## Overview
This document summarizes the key features of the current QUANTNIK BuildAI pipeline design.

## 1. Orchestrator + Worker Separation
- `CiCD-BUILDAI-ORCHESTRATOR` handles runtime inputs and coordination.
- `RepoWorkerBuildDeploy` performs repository-level CI/CD execution.

## 2. Multi-Repo Matrix Execution
- Worker pipeline runs selected repositories in parallel via matrix strategy.
- Supports targeted execution with `selectedRepo` (single, multiple, or `all`).

## 3. Per-Repo Branch Control
- Orchestrator provides per-repo branch runtime inputs.
- Worker resolves branch dynamically per matrix repository before clone.

## 4. Flexible Execution Modes
- `build_and_deploy`
- `build_only`
- `deploy_only`

## 5. Security and Quality Checks in Build Stage
- TruffleHog secret scan.
- Semgrep SAST scan.
- Trivy container vulnerability scan.
- OPA policy check against manifests (configured as non-blocking warning flow).

## 6. Container Build and Publish
- Backend and frontend image builds run in parallel where applicable.
- Images are pushed to ECR using configured AWS account/region and connector.

## 7. Native Harness CD Deployments
- Deploy stage uses `K8sRollingDeploy`.
- Rollback path uses `K8sRollingRollback`.
- Service and infra references are mapped per repository.

## 8. Deploy Gate by Build Result
- Deploy stage is gated to run only when upstream build stage status is successful.

## 9. Automated Sync Pipelines
- `Sync-Orchestrator-Branch-Options`: updates orchestrator branch runtime allowed values (runs every 30 minutes).
- `Sync-OnboardingRepos-Catalog`: syncs onboarding catalog changes into orchestrator and all worker pipeline YAML (CloudRun, ACA, EKS, GKE, AKS).

## 10. Catalog-Driven Onboarding
- Catalog source file: `.harness/catalog/onboardingrepos.yaml`.
- Sync automation updates pipeline definitions from catalog entries.

## 11. GitOps-Style Self-Update
- Sync pipelines commit and push generated YAML updates back to the repo.
- Non-interactive git auth is handled via pipeline credentials/secrets.

## 12. Security Report Publication Readiness (Harness STO/ATO)
- Security scan outputs are centralized under `reports/` in the worker stage.
- `BuildContext` artifact `security-reports` now includes JSON + SARIF outputs:
	- `reports/trufflehog-report.json`
	- `reports/semgrep-report.json`
	- `reports/semgrep-report.sarif`
	- `reports/trivy-backend-report.json`
	- `reports/trivy-backend-report.sarif`
	- `reports/trivy-frontend-report.json`
	- `reports/trivy-frontend-report.sarif`
	- Pipeline now includes native STO ingestion steps (`Semgrep` and `AquaTrivy` in `mode: ingestion`) that import the SARIF files during CI execution.
	- Ingestion files are copied to `/shared/scan_results` and ingested into STO for centralized findings and trend dashboards.
- Recommended gate policy after import: fail deploy on `CRITICAL > 0` and optionally on `HIGH` threshold by service risk profile.

## 13. Multi-Cloud Deployment Support
- **Cloud Run (GCP)**: Primary deployment target for QUANTNIK 3.0 repos
- **Azure Container Apps (ACA)**: Secondary deployment target for QUANTNIK 3.0 repos
- **EKS (AWS)**: Kubernetes deployment for QUANTNIK 1.0 repos
- **GKE (GCP)**: Alternative Kubernetes deployment
- **AKS (Azure)**: Azure Kubernetes Service deployment
- QUANTNIK 3.0 repos automatically sync to both CloudRun and ACA workers

## 14. Environment-Specific Deployment Flow
- Selecting specific environment (e.g., `dev`) skips subsequent environment approval/deploy stages
- Approval gates only trigger for environments included in selection
- Service naming uses environment prefix: `<env>-<service-name>` (e.g., `dev-quantnik-brd-backend`)

## 15. Catalog-Driven Cleanup
- Sync pipeline removes old/stale branch variables not in catalog
- Matrix entries are fully replaced (not just added to)
- Ensures clean state matching current catalog

## 16. Disabled Security Scanners (Available for Re-enablement)
- **SonarCloud**: Code quality analysis (disabled via condition)
- **Fortify on Demand**: Enterprise SAST (disabled via condition)
- **Harness SAST (ShiftLeft)**: Native Harness SAST (disabled - requires Enterprise license)
