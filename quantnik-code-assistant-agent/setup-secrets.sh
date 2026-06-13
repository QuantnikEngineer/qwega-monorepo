#!/bin/bash
# ---------------------------------------------------------------
# Cloud Run Secret Manager Setup Script
# ---------------------------------------------------------------
# This script creates secrets in Google Cloud Secret Manager
# and configures Cloud Run to access them.
#
# Usage:
#   Interactive mode (prompts for secrets):
#      ./setup-secrets.sh
#
#   With environment file (for project config only):
#      ./setup-secrets.sh .env.dev
#
#   Non-interactive mode (reads from env vars):
#      export FACTORY_API_KEY="your-key"
#      ./setup-secrets.sh --non-interactive
# ---------------------------------------------------------------

set -e

# Parse arguments
INTERACTIVE=true
ENV_FILE=""
for arg in "$@"; do
  case $arg in
    --non-interactive)
      INTERACTIVE=false
      ;;
    *.env*|.env*)
      ENV_FILE="$arg"
      ;;
  esac
done

# Load environment config if available (for non-secret values only)
if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
  echo "Loading config from $ENV_FILE..."
  set -a
  source "$ENV_FILE"
  set +a
elif [ -f ".env.dev" ]; then
  echo "Loading config from .env.dev..."
  set -a
  source ".env.dev"
  set +a
fi

# Prompt for GCP project if not set
if [ -z "$GCP_PROJECT_ID" ]; then
  read -p "Enter GCP Project ID: " GCP_PROJECT_ID
fi

GCP_PROJECT_ID="${GCP_PROJECT_ID:?Error: GCP_PROJECT_ID is required}"
GCP_REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-dev-quantnik-code-assistant-agent}"

echo ""
echo "=== Cloud Run Secret Manager Setup ==="
echo "Project: ${GCP_PROJECT_ID}"
echo "Region: ${GCP_REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Function to prompt for a secret value (hidden input)
prompt_secret() {
  local secret_name=$1
  local is_required=$2
  local current_value=$3
  
  if [ -n "$current_value" ]; then
    echo "$current_value"
    return
  fi
  
  local prompt_text="Enter $secret_name"
  [ "$is_required" = "optional" ] && prompt_text="$prompt_text (optional, press Enter to skip)"
  prompt_text="$prompt_text: "
  
  read -s -p "$prompt_text" secret_value
  echo ""  # newline after hidden input
  echo "$secret_value"
}

# Function to create or update a secret
create_or_update_secret() {
  local secret_name=$1
  local secret_value=$2
  
  if [ -z "$secret_value" ]; then
    echo "Skipping $secret_name (not set)"
    return 0
  fi
  
  echo "Creating/updating secret: $secret_name"
  
  # Check if secret exists
  if gcloud secrets describe "$secret_name" --project="$GCP_PROJECT_ID" &>/dev/null; then
    # Add new version
    echo -n "$secret_value" | gcloud secrets versions add "$secret_name" \
      --project="$GCP_PROJECT_ID" \
      --data-file=-
    echo "  Updated existing secret: $secret_name"
  else
    # Create new secret
    echo -n "$secret_value" | gcloud secrets create "$secret_name" \
      --project="$GCP_PROJECT_ID" \
      --replication-policy="automatic" \
      --data-file=-
    echo "  Created new secret: $secret_name"
  fi
}

# Collect secrets
if [ "$INTERACTIVE" = true ]; then
  echo "=== Enter Secrets (input is hidden) ==="
  echo ""
  FACTORY_API_KEY=$(prompt_secret "FACTORY_API_KEY" "required" "${FACTORY_API_KEY:-}")
  REPO_LOCK_GIT_TOKEN=$(prompt_secret "REPO_LOCK_GIT_TOKEN" "required" "${REPO_LOCK_GIT_TOKEN:-}")
  JIRA_EMAIL=$(prompt_secret "JIRA_EMAIL (Atlassian account email)" "optional" "${JIRA_EMAIL:-}")
  JIRA_API_TOKEN=$(prompt_secret "JIRA_API_TOKEN (from id.atlassian.com/manage/api-tokens)" "optional" "${JIRA_API_TOKEN:-}")
  ADO_PAT=$(prompt_secret "ADO_PAT" "optional" "${ADO_PAT:-}")
  echo ""
fi

# Create secrets
echo "=== Creating Secrets ==="

# Required secrets
create_or_update_secret "FACTORY_API_KEY" "${FACTORY_API_KEY:-}"
create_or_update_secret "REPO_LOCK_GIT_TOKEN" "${REPO_LOCK_GIT_TOKEN:-}"

# Optional secrets
create_or_update_secret "JIRA_EMAIL" "${JIRA_EMAIL:-}"
create_or_update_secret "JIRA_API_TOKEN" "${JIRA_API_TOKEN:-}"
create_or_update_secret "ADO_PAT" "${ADO_PAT:-}"

echo ""
echo "=== Granting Cloud Run Access ==="

# Get the Cloud Run service account
SERVICE_ACCOUNT=$(gcloud run services describe "$SERVICE_NAME" \
  --project="$GCP_PROJECT_ID" \
  --region="$GCP_REGION" \
  --format="value(spec.template.spec.serviceAccountName)" 2>/dev/null || echo "")

if [ -z "$SERVICE_ACCOUNT" ]; then
  # Use default compute service account
  PROJECT_NUMBER=$(gcloud projects describe "$GCP_PROJECT_ID" --format="value(projectNumber)")
  SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
fi

echo "Service Account: $SERVICE_ACCOUNT"

# Grant access to secrets
for secret_name in FACTORY_API_KEY REPO_LOCK_GIT_TOKEN JIRA_EMAIL JIRA_API_TOKEN ADO_PAT; do
  if gcloud secrets describe "$secret_name" --project="$GCP_PROJECT_ID" &>/dev/null; then
    gcloud secrets add-iam-policy-binding "$secret_name" \
      --project="$GCP_PROJECT_ID" \
      --member="serviceAccount:$SERVICE_ACCOUNT" \
      --role="roles/secretmanager.secretAccessor" \
      --quiet 2>/dev/null || true
    echo "  Granted access to $secret_name"
  fi
done

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Secrets are now configured in Secret Manager."
echo "Update your Cloud Run deployment to reference them:"
echo ""
echo "  --set-secrets=FACTORY_API_KEY=FACTORY_API_KEY:latest"
echo "  --set-secrets=REPO_LOCK_GIT_TOKEN=REPO_LOCK_GIT_TOKEN:latest"
echo "  --set-secrets=JIRA_EMAIL=JIRA_EMAIL:latest"
echo "  --set-secrets=JIRA_API_TOKEN=JIRA_API_TOKEN:latest"
echo "  --set-secrets=ADO_PAT=ADO_PAT:latest"
echo ""
