# Wega-Agent-CICD-Pipelines

## Harness pipeline: multiple repos in parallel

Added starter pipeline:

- `.harness/pipeline-multi-repo-ecr-eks.yaml`

This pipeline has 2 stages, both running in parallel for each repo using a matrix:

1. **Parallel Build Stages (Harness Cloud)**
	- `Build_unit_test_case_agent`
	- `Build_requirement_agent`
	- Each stage clones repo and runs `BuildAndPushECR` to ECR

2. **Parallel Deploy Stages (Kubernetes delegate)**
	- `Deploy_unit_test_case_agent`
	- `Deploy_requirement_agent`
	- Each stage updates deployment image in EKS and waits for rollout

## Configured values

Pipeline is now pre-filled with:

- Org: `default`
- Project: `WEGA_Build_AI`
- AWS Account: `145748108830`
- AWS Region: `ap-south-1`
- EKS Cluster: `wega-dev-eks`
- Namespace: `wega-demo`

Configured repo matrix:

- Repo: `unit-test-case-agent` → ECR: `unit-test-case-agent` → Deployment: `service-unit-test-case-agent` → Container: `service-unit-test-case-agent`
- Repo: `requirement-agent` → ECR: `requirement-agent` → Deployment: `service-requirement-agent` → Container: `service-requirement-agent`

All repositories deploy to the same namespace: `wega-demo`.

## Redesigned model (Kickoff + Worker)

This repo uses native Harness pipeline chaining (no webhook trigger) with one kickoff pipeline and one worker pipeline.

- Kickoff pipeline: `.harness/pipeline-kickoff-repo-fanout.yaml`
- Worker pipeline: `.harness/pipeline-repo-worker-build-deploy.yaml`

### Flow

1. Run **KickoffRepoFanout**.
2. Use `selectedRepo` runtime multi-select (checkbox-style) to choose:
	- `all`, or
	- one/more repo names
3. Set `executionMode` as one of: `build_and_deploy`, `build_only`, `deploy_only`.
4. Kickoff calls **RepoWorkerBuildDeployV2** once using a Pipeline stage.
5. Worker runs selected repos in parallel via matrix for build and uses native CD deploy stage (pilot) for EKS rollout.
4. Worker run:
	- Builds backend + frontend images to ECR in parallel.
	- Deploys backend + frontend to EKS in parallel.

After this, adding a new repo only requires adding one entry in `.harness/catalog/onboardingrepos.yaml`; kickoff selects repos via `selectedRepo`.

Note: the `selectedRepo` option list is statically configured in pipeline YAML. If you add a new repo in `onboardingrepos.yaml`, update the `selectedRepo` runtime options in `.harness/pipeline-kickoff-repo-fanout.yaml`.

## Repos without frontend/backend folders

Worker pipeline supports optional components per repo matrix entry:

- If a repo has only backend, keep frontend fields empty (`""`) and frontend build/deploy steps are skipped.
- If a repo has only frontend, keep backend fields empty (`""`) and backend build/deploy steps are skipped.
- If Dockerfile is at repo root, use:
	- `dockerfile: source/Dockerfile`
	- `context: source/`

## Native CD deploy

`RepoWorkerBuildDeployV2` uses a native Harness Deployment stage (`K8sRollingDeploy`) with per-repo matrix mapping:

- Service: per repo via `serviceRef` matrix mapping
- Environment: `wegadev`
- Infrastructure: `wegadeveksinfra`

## Runtime inputs

Kickoff user-facing inputs:

- `selectedRepo`
- `executionMode`

## Assumptions for this version

- Build uses Harness Cloud CI runtime.
- Build stage pushes to ECR using AWS connector in `BuildAndPushECR` step.
- Deployment runs through Kubernetes delegate.

If your Harness Git repos require explicit auth during clone, add a Git connector or token-based clone secret.

## Add more repositories

Add one item in each matrix:

- Under `Build-and-Push-ECR -> strategy -> matrix`
- Under `Deploy-to-EKS -> strategy -> matrix`

Use the same service naming so image and deployment mapping is clear.

## Auto-sync from repos catalog

Use this helper to sync both:

- kickoff `selectedRepo` checklist options
- worker build/deploy matrix entries

Script: `scripts/sync_repo_catalog_to_pipelines.py`

Run:

- `pip install pyyaml`
- `python scripts/sync_repo_catalog_to_pipelines.py`

