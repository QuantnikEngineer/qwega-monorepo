#!/bin/bash
# ---------------------------------------------------------------
# Cloud Run Deployment Script for quantnik-code-assistant-agent
# ---------------------------------------------------------------
# Prerequisites:
# 1. gcloud CLI installed and authenticated
# 2. FACTORY_API_KEY generated from https://app.factory.ai/settings/api-keys
# 3. Docker image built and pushed to Artifact Registry
# ---------------------------------------------------------------

set -e

# Configuration - UPDATE THESE VALUES
GCP_PROJECT_ID="${GCP_PROJECT_ID:-your-gcp-project-id}"
GCP_REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-dev-quantnik-code-assistant-agent}"
IMAGE="${CLOUD_RUN_IMAGE:-us-central1-docker.pkg.dev/${GCP_PROJECT_ID}/quantnik-repo/quantnik-code-assistant-agent:latest}"

# Required secrets - SET THESE BEFORE RUNNING
FACTORY_API_KEY="${FACTORY_API_KEY:?Error: FACTORY_API_KEY environment variable is required}"
REPO_LOCK_GIT_TOKEN="${REPO_LOCK_GIT_TOKEN:-}"

# App configuration
DROID_MODEL_ID="${DROID_MODEL_ID:-glm-5}"
DROID_REASONING="${DROID_REASONING:-low}"
REPO_LOCK_REMOTE_URL="${REPO_LOCK_REMOTE_URL:-}"
REPO_LOCK_ROOT_DIR="${REPO_LOCK_ROOT_DIR:-/app}"
REPO_LOCK_GIT_USERNAME="${REPO_LOCK_GIT_USERNAME:-git}"

echo "=== Cloud Run Deployment ==="
echo "Project: ${GCP_PROJECT_ID}"
echo "Region: ${GCP_REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Image: ${IMAGE}"
echo ""

# ---------------------------------------------------------------
# STEP 1: Build Docker Image
# ---------------------------------------------------------------
echo "=== Building Docker Image ==="
docker build -t quantnik-code-assistant-agent .

# ---------------------------------------------------------------
# STEP 2: Tag Image for Artifact Registry
# ---------------------------------------------------------------
echo "=== Tagging Image for Artifact Registry ==="
docker tag quantnik-code-assistant-agent "${IMAGE}"

# ---------------------------------------------------------------
# STEP 3: Configure Docker for GCP (if not already done)
# ---------------------------------------------------------------
echo "=== Configuring Docker Authentication ==="
gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

# ---------------------------------------------------------------
# STEP 4: Push Image to Artifact Registry
# ---------------------------------------------------------------
echo "=== Pushing Image to Artifact Registry ==="
docker push "${IMAGE}"

echo ""

# Build environment variables string (non-secret configs only)
ENV_VARS="NODE_ENV=production"
ENV_VARS="${ENV_VARS},HOST=0.0.0.0"
ENV_VARS="${ENV_VARS},PORT=8080"
ENV_VARS="${ENV_VARS},DROID_MODEL_ID=${DROID_MODEL_ID}"
ENV_VARS="${ENV_VARS},DROID_REASONING=${DROID_REASONING}"

if [ -n "${REPO_LOCK_REMOTE_URL}" ]; then
  ENV_VARS="${ENV_VARS},REPO_LOCK_REMOTE_URL=${REPO_LOCK_REMOTE_URL}"
fi

if [ -n "${REPO_LOCK_ROOT_DIR}" ]; then
  ENV_VARS="${ENV_VARS},REPO_LOCK_ROOT_DIR=${REPO_LOCK_ROOT_DIR}"
fi

if [ -n "${REPO_LOCK_GIT_USERNAME}" ]; then
  ENV_VARS="${ENV_VARS},REPO_LOCK_GIT_USERNAME=${REPO_LOCK_GIT_USERNAME}"
fi

if [ -n "${JIRA_URL}" ]; then
  ENV_VARS="${ENV_VARS},JIRA_URL=${JIRA_URL}"
fi

if [ -n "${ADO_ORGANIZATION_URL}" ]; then
  ENV_VARS="${ENV_VARS},ADO_ORGANIZATION_URL=${ADO_ORGANIZATION_URL}"
fi

if [ -n "${ADO_ORG}" ]; then
  ENV_VARS="${ENV_VARS},ADO_ORG=${ADO_ORG}"
fi

# Note: REPO_LOCK_GIT_TOKEN is now managed via Secret Manager
# See setup-secrets.sh to configure secrets

# Build secrets string for Secret Manager references
SECRETS=""
if gcloud secrets describe FACTORY_API_KEY --project="${GCP_PROJECT_ID}" &>/dev/null; then
  SECRETS="FACTORY_API_KEY=FACTORY_API_KEY:latest"
fi
if gcloud secrets describe REPO_LOCK_GIT_TOKEN --project="${GCP_PROJECT_ID}" &>/dev/null; then
  [ -n "$SECRETS" ] && SECRETS="${SECRETS},"
  SECRETS="${SECRETS}REPO_LOCK_GIT_TOKEN=REPO_LOCK_GIT_TOKEN:latest"
fi
if gcloud secrets describe JIRA_EMAIL --project="${GCP_PROJECT_ID}" &>/dev/null; then
  [ -n "$SECRETS" ] && SECRETS="${SECRETS},"
  SECRETS="${SECRETS}JIRA_EMAIL=JIRA_EMAIL:latest"
fi
if gcloud secrets describe JIRA_API_TOKEN --project="${GCP_PROJECT_ID}" &>/dev/null; then
  [ -n "$SECRETS" ] && SECRETS="${SECRETS},"
  SECRETS="${SECRETS}JIRA_API_TOKEN=JIRA_API_TOKEN:latest"
fi
if gcloud secrets describe JIRA_AUTH_BASE64 --project="${GCP_PROJECT_ID}" &>/dev/null; then
  [ -n "$SECRETS" ] && SECRETS="${SECRETS},"
  SECRETS="${SECRETS}JIRA_AUTH_BASE64=JIRA_AUTH_BASE64:latest"
fi
if gcloud secrets describe ADO_PAT --project="${GCP_PROJECT_ID}" &>/dev/null; then
  [ -n "$SECRETS" ] && SECRETS="${SECRETS},"
  SECRETS="${SECRETS}ADO_PAT=ADO_PAT:latest"
fi

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."

# Build deploy command
DEPLOY_CMD="gcloud run deploy ${SERVICE_NAME} \
  --project=${GCP_PROJECT_ID} \
  --region=${GCP_REGION} \
  --image=${IMAGE} \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=900 \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=10 \
  --set-env-vars=${ENV_VARS}"

# Add secrets if configured in Secret Manager
if [ -n "$SECRETS" ]; then
  echo "Using secrets from Secret Manager: $SECRETS"
  DEPLOY_CMD="${DEPLOY_CMD} --set-secrets=${SECRETS}"
else
  echo "Warning: No secrets found in Secret Manager. Using environment variables."
  # Fallback to env vars (for backward compatibility)
  if [ -n "${FACTORY_API_KEY:-}" ]; then
    ENV_VARS="${ENV_VARS},FACTORY_API_KEY=${FACTORY_API_KEY}"
  fi
  if [ -n "${REPO_LOCK_GIT_TOKEN:-}" ]; then
    ENV_VARS="${ENV_VARS},REPO_LOCK_GIT_TOKEN=${REPO_LOCK_GIT_TOKEN}"
  fi
fi

eval "$DEPLOY_CMD"

echo ""
echo "=== Deployment Complete ==="
gcloud run services describe "${SERVICE_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --region="${GCP_REGION}" \
  --format="value(status.url)"
