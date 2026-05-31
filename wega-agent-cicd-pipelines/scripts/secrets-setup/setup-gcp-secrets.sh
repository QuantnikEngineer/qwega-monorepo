#!/bin/bash
# setup-gcp-secrets.sh
# Creates all secrets in GCP Secret Manager from secrets-values.yaml
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - yq installed (brew install yq / apt install yq)
#
# Usage:
#   ./setup-gcp-secrets.sh <project-id>
#   ./setup-gcp-secrets.sh wega-gcp-project

set -e

PROJECT_ID="${1:?Usage: $0 <gcp-project-id>}"
SECRETS_FILE="$(dirname "$0")/secrets-values.yaml"

if [ ! -f "$SECRETS_FILE" ]; then
    echo "ERROR: $SECRETS_FILE not found"
    exit 1
fi

echo "=========================================="
echo "GCP Secret Manager Setup"
echo "Project: $PROJECT_ID"
echo "=========================================="

# Get list of environments
ENVIRONMENTS=$(yq -r '.environments | keys | .[]' "$SECRETS_FILE")

for ENV in $ENVIRONMENTS; do
    echo ""
    echo "--- Environment: $ENV ---"
    
    # Get all secrets for this environment
    SECRETS=$(yq -r ".environments.${ENV} | keys | .[]" "$SECRETS_FILE")
    
    for SECRET_KEY in $SECRETS; do
        # Convert SECRET_KEY to lowercase with hyphens (e.g., DB_PASSWORD -> db-password)
        SECRET_NAME="wega-${ENV}-$(echo $SECRET_KEY | tr '[:upper:]' '[:lower:]' | tr '_' '-')"
        SECRET_VALUE=$(yq -r ".environments.${ENV}.${SECRET_KEY}" "$SECRETS_FILE")
        
        # Skip if placeholder value
        if [[ "$SECRET_VALUE" == *"REPLACE_WITH"* ]]; then
            echo "  SKIP: $SECRET_NAME (placeholder value - update secrets-values.yaml)"
            continue
        fi
        
        # Check if secret exists
        if gcloud secrets describe "$SECRET_NAME" --project="$PROJECT_ID" &>/dev/null; then
            echo "  UPDATE: $SECRET_NAME"
            echo -n "$SECRET_VALUE" | gcloud secrets versions add "$SECRET_NAME" \
                --project="$PROJECT_ID" \
                --data-file=-
        else
            echo "  CREATE: $SECRET_NAME"
            # Create secret
            gcloud secrets create "$SECRET_NAME" \
                --project="$PROJECT_ID" \
                --replication-policy="automatic" \
                --labels="environment=${ENV},managed-by=harness"
            
            # Add value
            echo -n "$SECRET_VALUE" | gcloud secrets versions add "$SECRET_NAME" \
                --project="$PROJECT_ID" \
                --data-file=-
            
            # Grant Cloud Run access (default compute service account)
            PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
            gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
                --project="$PROJECT_ID" \
                --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
                --role="roles/secretmanager.secretAccessor" \
                --quiet
        fi
    done
done

echo ""
echo "=========================================="
echo "GCP Secret Manager setup complete!"
echo "=========================================="
echo ""
echo "⚠️  IMPORTANT: Delete secrets-values.yaml after verification"
