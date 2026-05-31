# Secrets Setup Scripts

One-time setup scripts to populate cloud secret managers.

## Files

| File | Purpose |
|------|---------|
| `secrets-values.yaml` | Template with all secrets (fill in actual values) |
| `setup-gcp-secrets.sh` | Creates secrets in GCP Secret Manager |
| `setup-azure-secrets.sh` | Creates secrets in Azure Key Vault |
| `setup-aws-secrets.sh` | Creates secrets in AWS Secrets Manager |

## Usage

### Step 1: Fill in actual secret values

Edit `secrets-values.yaml` and replace all `REPLACE_WITH_*` placeholders with actual values:

```yaml
environments:
  dev:
    DB_PASSWORD: "actual_dev_password_here"
    OPENAI_API_KEY: "sk-actual-key-here"
    ...
```

### Step 2: Run setup script for each cloud

```bash
# GCP
./setup-gcp-secrets.sh wega-gcp-project

# Azure
./setup-azure-secrets.sh wega-azure-rg eastus

# AWS
./setup-aws-secrets.sh us-east-1
```

### Step 3: Delete secrets-values.yaml

```bash
rm secrets-values.yaml
# Or securely delete
shred -u secrets-values.yaml
```

## Security

- **NEVER commit `secrets-values.yaml` to Git**
- Delete the file immediately after running scripts
- Only DevOps/Platform team should have access
- Use a password manager to store the original values

## Adding New Secrets Later

1. Add to `secrets-values.yaml` (create fresh copy)
2. Run the appropriate setup script (it will update existing, create new)
3. Delete `secrets-values.yaml`
4. Update `config/secrets.yaml` in service repos to reference new secret
