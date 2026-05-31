#!/bin/bash
# setup-aws-secrets.sh
# Creates all secrets in AWS Secrets Manager from secrets-values.yaml
#
# Prerequisites:
#   - aws CLI installed and configured
#   - yq installed
#
# Usage:
#   ./setup-aws-secrets.sh <region>
#   ./setup-aws-secrets.sh us-east-1

set -e

REGION="${1:?Usage: $0 <aws-region>}"
SECRETS_FILE="$(dirname "$0")/secrets-values.yaml"

if [ ! -f "$SECRETS_FILE" ]; then
    echo "ERROR: $SECRETS_FILE not found"
    exit 1
fi

echo "=========================================="
echo "AWS Secrets Manager Setup"
echo "Region: $REGION"
echo "=========================================="

# Get list of environments
ENVIRONMENTS=$(yq -r '.environments | keys | .[]' "$SECRETS_FILE")

for ENV in $ENVIRONMENTS; do
    echo ""
    echo "--- Environment: $ENV ---"
    
    # Get all secrets for this environment
    SECRETS=$(yq -r ".environments.${ENV} | keys | .[]" "$SECRETS_FILE")
    
    for SECRET_KEY in $SECRETS; do
        # Convert SECRET_KEY to lowercase with hyphens
        SECRET_SUFFIX=$(echo $SECRET_KEY | tr '[:upper:]' '[:lower:]' | tr '_' '-')
        SECRET_NAME="wega/${ENV}/${SECRET_SUFFIX}"
        SECRET_VALUE=$(yq -r ".environments.${ENV}.${SECRET_KEY}" "$SECRETS_FILE")
        
        # Skip if placeholder value
        if [[ "$SECRET_VALUE" == *"REPLACE_WITH"* ]]; then
            echo "  SKIP: $SECRET_NAME (placeholder value)"
            continue
        fi
        
        # Check if secret exists
        if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$REGION" &>/dev/null; then
            echo "  UPDATE: $SECRET_NAME"
            aws secretsmanager put-secret-value \
                --secret-id "$SECRET_NAME" \
                --secret-string "$SECRET_VALUE" \
                --region "$REGION"
        else
            echo "  CREATE: $SECRET_NAME"
            aws secretsmanager create-secret \
                --name "$SECRET_NAME" \
                --secret-string "$SECRET_VALUE" \
                --region "$REGION" \
                --tags Key=Environment,Value="$ENV" Key=ManagedBy,Value=harness
        fi
    done
done

echo ""
echo "=========================================="
echo "AWS Secrets Manager setup complete!"
echo "=========================================="
echo ""
echo "⚠️  IMPORTANT: Delete secrets-values.yaml after verification"
