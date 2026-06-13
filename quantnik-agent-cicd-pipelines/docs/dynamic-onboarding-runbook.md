# Dynamic Onboarding Runbook

Goal: Add new repos only in `onboardingrepos.yaml`, then run sync pipelines to auto-update all worker and orchestrator pipelines.

---

## Key Files

| File | Purpose |
|------|---------|
| [.harness/catalog/onboardingrepos.yaml](../.harness/catalog/onboardingrepos.yaml) | Repository catalog (source of truth) |
| [scripts/sync_repo_catalog_to_pipelines.py](../scripts/sync_repo_catalog_to_pipelines.py) | Syncs catalog to all pipelines |
| [.harness/pipeline-sync-onboardingrepos-catalog.yaml](../.harness/pipeline-sync-onboardingrepos-catalog.yaml) | Pipeline to run catalog sync |
| [.harness/pipeline-sync-orchestrator-branches.yaml](../.harness/pipeline-sync-orchestrator-branches.yaml) | Pipeline to sync branch options |

---

## Onboard a New Repository

### Step 1: Update the Catalog

1. Open [.harness/catalog/onboardingrepos.yaml](../.harness/catalog/onboardingrepos.yaml)
2. Add a new entry under `repos:`:

```yaml
- repoName: your-new-repo
  branch: develop
  quantnikVersion: "3.0"          # "1.0" for EKS, "3.0" for CloudRun/ACA
  deployTarget: cloudrun      # cloudrun, eks, gke, aks
  backend:
    dockerfile: source/Dockerfile
    context: source/
    imageName: your-new-repo-backend
    cloudRunService: your-new-repo
  serviceRef: yourNewRepoService
```

3. Commit and push the change.

### Step 2: Run Catalog Sync Pipeline

1. Go to Harness → Pipelines → `SyncOnboardingReposCatalog`
2. Click **Run**
3. This will update all worker pipelines:
   - `RepoWorkerBuildDeployCloudRun`
   - `RepoWorkerBuildDeployACA`
   - `RepoWorkerBuildDeployEKS`
   - `RepoWorkerBuildDeployGKE`
   - `RepoWorkerBuildDeployAKS`
   - Orchestrator pipelines (QUANTNIK 1.0 and 3.0)

### Step 3: Run Branch Sync Pipeline

1. Go to Harness → Pipelines → `SyncOrchestratorBranchOptions`
2. Click **Run**
3. This will fetch live branches from the new repo and update branch allowed values

> **Note**: Branch sync runs automatically every 30 minutes. You can run it manually for immediate updates.

---

## What Gets Updated

When you run the catalog sync:

| Component | What's Updated |
|-----------|----------------|
| Build stage matrix | New repo added to build matrix |
| Deploy stage matrix | New repo added to all deploy stages (Dev, QA, Stage, Prod) |
| Branch variables | New `branch<RepoName>` variable added |
| Branch resolver | New case statement added for repo → branch mapping |
| Orchestrator selectedRepo | New repo added to dropdown |

---

## Automated Sync Schedule

| Pipeline | Schedule | Purpose |
|----------|----------|---------|
| `SyncOrchestratorBranchOptions` | Every 30 minutes | Syncs live repo branches |
| `SyncOnboardingReposCatalog` | Manual | Syncs catalog to pipelines |

---

## Remove a Repository

1. Delete the repo entry from `onboardingrepos.yaml`
2. Commit and push
3. Run `SyncOnboardingReposCatalog` pipeline
4. The sync will remove:
   - Repo from all matrices
   - Branch variable
   - Branch resolver case

---

## Verify Onboarding

After running sync pipelines, verify changes in orchestrator and worker pipelines:

### Step 1: Verify in QUANTNIK 3.0 Orchestrator (Primary)

1. Open `QUANTNIK30Orchestrator` pipeline (or `QUANTNIK10Orchestrator` for 1.0 repos)
2. Click **Run** to see the input form
3. Check `selectedRepo` dropdown includes your new repo
4. Check `branch<YourRepoName>` variable exists
5. Verify branch options are populated (from branch sync)

### Step 2: Verify in Worker Pipelines

1. Open the appropriate worker pipeline:
   - `RepoWorkerBuildDeployCloudRun` (for QUANTNIK 3.0)
   - `RepoWorkerBuildDeployACA` (for QUANTNIK 3.0)
   - `RepoWorkerBuildDeployEKS` (for QUANTNIK 1.0)
2. Check the Build stage matrix includes your new repo
3. Check all Deploy stages (Dev, QA, Stage, Prod) include your new repo
4. Verify branch variable and branch resolver case exist

### Flow Diagram

```
Orchestrator (QUANTNIK 3.0)          Worker Pipeline (CloudRun/ACA)
        │                                    │
        ▼                                    ▼
┌─────────────────┐              ┌─────────────────────────┐
│ Select Repos    │──────────────▶ Build Matrix (all repos)│
│ Select Branches │              │ Deploy_Dev Matrix       │
│ Select Env      │              │ Deploy_QA Matrix        │
└─────────────────┘              │ Deploy_Stage Matrix     │
                                 │ Deploy_Prod Matrix      │
                                 └─────────────────────────┘
```

> **Important**: The orchestrator pipeline triggers the worker pipelines. If a repo is missing from the orchestrator's `selectedRepo` dropdown, it cannot be built/deployed.

---

## Troubleshooting

### Repo not appearing in pipelines
- Ensure catalog sync pipeline completed successfully
- Check the Python script logs for errors
- Verify the repo entry in `onboardingrepos.yaml` is valid YAML

### Branch options not showing
- Run `SyncOrchestratorBranchOptions` pipeline manually
- Ensure the repo exists in Git and has branches
- Wait for the 30-minute auto-sync

### Old repos still appearing
- The sync script now removes old entries not in catalog
- Run catalog sync again to clean up stale entries

