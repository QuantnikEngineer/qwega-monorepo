# Environment Variables & Secrets Management
## Harness CI/CD Implementation Plan for WEGA Pipelines

**Version:** 3.0 | **Date:** May 2026 | **Platform:** Harness CI/CD

---

## Key Design Decisions

| What | Where | Who Maintains |
|------|-------|---------------|
| **Environment Variables** | `config/` folder in each service repo | Developers |
| **Secrets** | Cloud secret managers (GCP/Azure/AWS) | DevOps (one-time setup) |
| **Code Changes** | None required | - |

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EACH SERVICE REPOSITORY                          │
│                                                                     │
│   wega-brd/                                                         │
│   ├── source/                                                       │
│   │   ├── Dockerfile                                                │
│   │   └── main.py                                                   │
│   └── config/                 ← Developer maintains this folder     │
│       ├── common.yaml                                               │
│       ├── secrets.yaml                                              │
│       ├── gcp/{dev,qa,staging,prod}.yaml                            │
│       ├── azure/{dev,qa,staging,prod}.yaml                          │
│       └── aws/{dev,qa,staging,prod}.yaml                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       HARNESS PIPELINE                              │
│                                                                     │
│   1. Clone service repo                                             │
│   2. Read config/common.yaml + config/{cloud}/common.yaml           │
│      + config/{cloud}/{env}.yaml + config/secrets.yaml              │
│   3. Build & push Docker image                                      │
│   4. Deploy with:                                                   │
│      - Env vars from merged YAML                                    │
│      - Secrets from cloud secret manager                            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
        ┌───────────────┬───────────────┬───────────────┐
        │ GCP Cloud Run │  Azure ACA    │   AWS ECS     │
        │ --set-env-vars│ --set-env-vars│ environment:[]│
        │ --set-secrets │ --secrets     │ secrets: []   │
        └───────────────┴───────────────┴───────────────┘
```

---

## 2. Config Folder Structure

### Folder Location
```
wega-brd/
├── source/
│   ├── Dockerfile
│   └── main.py
└── config/                      ← This folder
    ├── common.yaml              # All clouds, all environments
    ├── secrets.yaml             # Secret references
    ├── gcp/
    │   ├── common.yaml          # GCP all environments
    │   ├── dev.yaml
    │   ├── qa.yaml
    │   ├── staging.yaml
    │   └── prod.yaml
    ├── azure/
    │   ├── common.yaml
    │   ├── dev.yaml
    │   ├── qa.yaml
    │   ├── staging.yaml
    │   └── prod.yaml
    └── aws/
        ├── common.yaml
        ├── dev.yaml
        ├── qa.yaml
        ├── staging.yaml
        └── prod.yaml
```

### File Examples

**config/common.yaml** (All clouds, all environments)
```yaml
service:
  name: wega-brd

env:
  PYTHONUNBUFFERED: "1"
  LOG_FORMAT: json
  API_TIMEOUT: "30"
```

**config/secrets.yaml** (Secret references)
```yaml
secrets:
  - envVar: DB_PASSWORD
  - envVar: OPENAI_API_KEY
  - envVar: JWT_SECRET
```

**config/gcp/common.yaml** (GCP all environments)
```yaml
env:
  CLOUD_PROVIDER: gcp
  GCP_PROJECT_ID: wega-gcp-project
```

**config/gcp/dev.yaml** (GCP Dev)
```yaml
env:
  ENVIRONMENT: dev
  LOG_LEVEL: DEBUG
  API_BASE_URL: https://dev-api.wega.example.com
```

**config/gcp/prod.yaml** (GCP Production)
```yaml
env:
  ENVIRONMENT: prod
  LOG_LEVEL: WARN
  MAX_RETRIES: "5"
```

### Merge Order

```
config/common.yaml → config/{cloud}/common.yaml → config/{cloud}/{env}.yaml + secrets.yaml
```

| Step | What Happens |
|------|--------------|
| 1 | Pipeline clones service repo |
| 2 | Reads `config/common.yaml` (global defaults) |
| 3 | Merges `config/{cloud}/common.yaml` (cloud-specific) |
| 4 | Merges `config/{cloud}/{env}.yaml` (environment-specific) |
| 5 | Maps secrets from `config/secrets.yaml` to cloud secret manager |
| 6 | Deploys with combined env vars + secrets |

---

## 3. Secrets Storage (One-Time Setup)

> **Secrets are stored ONCE in cloud secret managers.**
> The `config/secrets.yaml` only contains the **names** of secrets, not the values.

### Naming Convention

| Cloud | Secret Name Format | Example |
|-------|-------------------|---------|
| GCP | `wega-{env}-{secret-name}` | `wega-dev-db-password` |
| Azure | Vault: `wega-kv-{env}`, Secret: `{name}` | `wega-kv-dev/db-password` |
| AWS | `wega/{env}/{secret-name}` | `wega/dev/db-password` |

### Bulk Secrets Setup Scripts

Scripts are provided in `scripts/secrets-setup/` to create all secrets at once:

```
scripts/secrets-setup/
├── secrets-values.yaml      ← Fill in ALL secret values here
├── setup-gcp-secrets.sh     ← Run once for GCP
├── setup-azure-secrets.sh   ← Run once for Azure
├── setup-aws-secrets.sh     ← Run once for AWS
└── README.md
```

#### Step 1: Fill in secrets-values.yaml

```yaml
# scripts/secrets-setup/secrets-values.yaml
# ⚠️ WARNING: Contains ACTUAL VALUES - DO NOT COMMIT TO GIT
# ⚠️ DELETE AFTER USE

environments:
  dev:
    DB_PASSWORD: "actual_dev_db_password"
    OPENAI_API_KEY: "sk-actual-key-here"
    JWT_SECRET: "actual_jwt_secret"
    REDIS_PASSWORD: "actual_redis_password"
    
  qa:
    DB_PASSWORD: "actual_qa_db_password"
    OPENAI_API_KEY: "sk-actual-key-here"
    # ... same structure
    
  staging:
    # ... same structure
    
  prod:
    # ... same structure
```

#### Step 2: Run Setup Scripts

```bash
# GCP - Creates secrets in GCP Secret Manager
./scripts/secrets-setup/setup-gcp-secrets.sh wega-gcp-project

# Azure - Creates Key Vaults and secrets
./scripts/secrets-setup/setup-azure-secrets.sh wega-azure-rg eastus

# AWS - Creates secrets in AWS Secrets Manager
./scripts/secrets-setup/setup-aws-secrets.sh us-east-1
```

#### Step 3: Delete secrets-values.yaml

```bash
# IMPORTANT: Delete immediately after running scripts!
rm scripts/secrets-setup/secrets-values.yaml
```

> ⚠️ **Security:**
> - `secrets-values.yaml` is in `.gitignore` - will not be committed
> - Delete the file immediately after running the scripts
> - Only DevOps/Platform team should have access to actual values
> - Store original values in a password manager

### What the Scripts Do

| Script | Creates | Grants Access To |
|--------|---------|------------------|
| `setup-gcp-secrets.sh` | `wega-{env}-{secret}` in GCP Secret Manager | Cloud Run service account |
| `setup-azure-secrets.sh` | `wega-kv-{env}` vaults + secrets | ACA managed identity |
| `setup-aws-secrets.sh` | `wega/{env}/{secret}` in AWS Secrets Manager | ECS task role |

---

## 4. Pipeline Integration

### Cloud Run Pipeline
```yaml
- step:
    type: Run
    name: Deploy_To_CloudRun
    spec:
      command: |
        ENV="<+pipeline.variables.environment>"
        REPO_PATH="<+pipeline.variables.repoPath>"
        
        # Merge: common → gcp/common → gcp/{env}
        ALL_VARS=$(yq -s 'add | .env | to_entries | map("\(.key)=\(.value)") | join(",")' \
          "$REPO_PATH/config/common.yaml" \
          "$REPO_PATH/config/gcp/common.yaml" \
          "$REPO_PATH/config/gcp/${ENV}.yaml")
        
        # Parse secrets
        SECRETS=$(yq -r '.secrets[].envVar' "$REPO_PATH/config/secrets.yaml" | while read secret; do
          echo "${secret}=wega-${ENV}-$(echo $secret | tr '[:upper:]' '[:lower:]' | tr '_' '-'):latest"
        done | paste -sd ',' -)
        
        gcloud run deploy "$SERVICE_NAME" --image="$IMAGE" \
          --set-env-vars="$ALL_VARS" --set-secrets="$SECRETS"
```

### ACA Pipeline
```yaml
- step:
    type: Run
    name: Deploy_To_ACA
    spec:
      command: |
        ENV="<+pipeline.variables.environment>"
        REPO_PATH="<+pipeline.variables.repoPath>"
        VAULT_NAME="wega-kv-${ENV}"
        
        # Merge: common → azure/common → azure/{env}
        ENV_ARGS=$(yq -s 'add | .env | to_entries | map("--set-env-vars \(.key)=\(.value)") | .[]' \
          "$REPO_PATH/config/common.yaml" \
          "$REPO_PATH/config/azure/common.yaml" \
          "$REPO_PATH/config/azure/${ENV}.yaml")
        
        # Build secret refs
        SECRET_ARGS=$(yq -r '.secrets[].envVar' "$REPO_PATH/config/secrets.yaml" | while read s; do
          name=$(echo $s | tr '[:upper:]' '[:lower:]' | tr '_' '-')
          echo "--secrets ${name}=keyvaultref:https://${VAULT_NAME}.vault.azure.net/secrets/${name}"
        done)
        
        az containerapp update --name "$SERVICE" --resource-group "$RG" $ENV_ARGS $SECRET_ARGS
```

### ECS Pipeline
```yaml
- step:
    type: Run
    name: Generate_Task_Definition
    spec:
      command: |
        ENV="<+pipeline.variables.environment>"
        REPO_PATH="<+pipeline.variables.repoPath>"
        
        # Merge: common → aws/common → aws/{env}
        ENV_JSON=$(yq -s 'add | .env | to_entries | map({name: .key, value: .value})' \
          "$REPO_PATH/config/common.yaml" \
          "$REPO_PATH/config/aws/common.yaml" \
          "$REPO_PATH/config/aws/${ENV}.yaml" -o json)
        
        # Generate secrets JSON
        SECRETS_JSON=$(yq -r ".secrets | map({name: .envVar, valueFrom: \"arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT}:secret:wega/${ENV}/\" + (.envVar | ascii_downcase | gsub(\"_\"; \"-\"))})" \
          "$REPO_PATH/config/secrets.yaml" -o json)
        
        cat > task-def.json << EOF
        {"containerDefinitions": [{"environment": $ENV_JSON, "secrets": $SECRETS_JSON}]}
        EOF
```

---

## 5. Implementation Phases

### Phase 1: Template & Pilot (1-2 Days)
- [ ] Create template config/ folder structure
- [ ] Document structure and guidelines
- [ ] Add config/ folder to pilot service (wega-brd)

### Phase 2: Secret Manager Setup (3-5 Days)
- [ ] Run GCP setup script
- [ ] Run Azure setup script  
- [ ] Run AWS setup script
- [ ] Populate actual secret values

### Phase 3: Pipeline Updates (1 Week)
- [ ] Add yq installation step to pipelines
- [ ] Add config/ folder parsing to cloudrun.yaml
- [ ] Add config/ folder parsing to aca.yaml
- [ ] Add config/ folder parsing to ecs.yaml
- [ ] Test with pilot service

### Phase 4: Rollout (1 Week)
- [ ] Create config/ folder for all 23 WEGA 3.0 services
- [ ] Deploy to Dev
- [ ] Deploy to QA
- [ ] Deploy to Staging
- [ ] Deploy to Production
- [ ] Remove manual configs from cloud UIs

---

## 6. Developer Guide

### Adding a New Environment Variable

| Scope | File to Edit |
|-------|--------------|
| All clouds, all envs | `config/common.yaml` |
| One cloud, all envs | `config/{cloud}/common.yaml` |
| One cloud, one env | `config/{cloud}/{env}.yaml` |

```yaml
# config/common.yaml - All clouds/envs
env:
  NEW_FEATURE_FLAG: "true"

# config/gcp/prod.yaml - GCP production only
env:
  NEW_FEATURE_FLAG: "false"
```

### Adding a New Secret
1. Request secret creation in cloud secret managers (DevOps team)
2. Add reference to `config/secrets.yaml`
3. Pipeline injects at deploy time

```yaml
# config/secrets.yaml
secrets:
  - envVar: DB_PASSWORD
  - envVar: NEW_API_SECRET    # ← Add reference
```

### Accessing in Code
```python
# No changes needed!
import os

db_password = os.getenv('DB_PASSWORD')
log_level = os.getenv('LOG_LEVEL')
new_secret = os.getenv('NEW_API_SECRET')
```

---

## Summary

| Component | Location | Maintainer |
|-----------|----------|------------|
| Env vars | `config/` folder per repo | Developers |
| Structure | `config/{cloud}/{env}.yaml` | Developers |
| Secrets | Cloud secret managers | DevOps (one-time) |
| Pipeline | Merges YAML, maps secrets, deploys | Automated |
| Code | No changes, uses `os.getenv()` | - |

---

*WEGA CI/CD - Environment & Secrets Management Plan v3.0*
*Last Updated: May 2026 | Platform: Harness CI/CD*
