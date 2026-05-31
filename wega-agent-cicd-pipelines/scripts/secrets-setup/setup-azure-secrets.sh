#!/bin/bash
# setup-azure-secrets.sh
# Creates all secrets in Azure Key Vault from secrets-values.yaml
#
# Prerequisites:
#   - az CLI installed and authenticated
#   - yq installed
#
# Usage:
#   ./setup-azure-secrets.sh <resource-group> <location>
#   ./setup-azure-secrets.sh wega-azure-rg eastus

set -e

RESOURCE_GROUP="${1:?Usage: $0 <resource-group> <location>}"
LOCATION="${2:?Usage: $0 <resource-group> <location>}"
SECRETS_FILE="$(dirname "$0")/secrets-values.yaml"

if [ ! -f "$SECRETS_FILE" ]; then
    echo "ERROR: $SECRETS_FILE not found"
    exit 1
fi

echo "=========================================="
echo "Azure Key Vault Setup"
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "=========================================="

# Get list of environments
ENVIRONMENTS=$(yq -r '.environments | keys | .[]' "$SECRETS_FILE")

for ENV in $ENVIRONMENTS; do
    VAULT_NAME="wega-kv-${ENV}"
    
    echo ""
    echo "--- Environment: $ENV (Vault: $VAULT_NAME) ---"
    
    # Create Key Vault if not exists
    if ! az keyvault show --name "$VAULT_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
        echo "  Creating Key Vault: $VAULT_NAME"
        az keyvault create \
            --name "$VAULT_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --enable-rbac-authorization true \
            --tags environment="$ENV" managed-by=harness
    fi
    
    # Get all secrets for this environment
    SECRETS=$(yq -r ".environments.${ENV} | keys | .[]" "$SECRETS_FILE")
    
    for SECRET_KEY in $SECRETS; do
        # Convert SECRET_KEY to lowercase with hyphens
        SECRET_NAME=$(echo $SECRET_KEY | tr '[:upper:]' '[:lower:]' | tr '_' '-')
        SECRET_VALUE=$(yq -r ".environments.${ENV}.${SECRET_KEY}" "$SECRETS_FILE")
        
        # Skip if placeholder value
        if [[ "$SECRET_VALUE" == *"REPLACE_WITH"* ]]; then
            echo "  SKIP: $SECRET_NAME (placeholder value)"
            continue
        fi
        
        echo "  SET: $SECRET_NAME"
        az keyvault secret set \
            --vault-name "$VAULT_NAME" \
            --name "$SECRET_NAME" \
            --value "$SECRET_VALUE" \
            --output none
    done
done

echo ""
echo "=========================================="
echo "Azure Key Vault setup complete!"
echo "=========================================="
echo ""
echo "⚠️  IMPORTANT: Delete secrets-values.yaml after verification"
echo ""
echo "Next: Grant ACA managed identity access to Key Vaults"
