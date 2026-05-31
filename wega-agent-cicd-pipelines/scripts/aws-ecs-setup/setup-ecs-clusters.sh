#!/bin/bash
# AWS ECS Cluster Setup Script for WEGA 3.0
# Creates ECS clusters for dev, qa, stage environments

set -e

AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER_PREFIX="${CLUSTER_PREFIX:-wega-ecs}"

echo "==========================================="
echo "AWS ECS Cluster Setup for WEGA 3.0"
echo "Region: $AWS_REGION"
echo "Cluster Prefix: $CLUSTER_PREFIX"
echo "==========================================="

# Environments to create
ENVIRONMENTS=("dev" "qa" "stage")

for ENV in "${ENVIRONMENTS[@]}"; do
  CLUSTER_NAME="${CLUSTER_PREFIX}-${ENV}"
  
  echo ""
  echo "Creating cluster: $CLUSTER_NAME"
  
  # Check if cluster exists
  EXISTING=$(aws ecs describe-clusters --clusters "$CLUSTER_NAME" --region "$AWS_REGION" \
    --query 'clusters[0].status' --output text 2>/dev/null || echo "MISSING")
  
  if [ "$EXISTING" = "ACTIVE" ]; then
    echo "  Cluster $CLUSTER_NAME already exists - skipping"
  else
    aws ecs create-cluster \
      --cluster-name "$CLUSTER_NAME" \
      --capacity-providers FARGATE FARGATE_SPOT \
      --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
      --region "$AWS_REGION" \
      --tags key=Environment,value="$ENV" key=Project,value=WEGA key=ManagedBy,value=Harness
    
    echo "  Created cluster: $CLUSTER_NAME"
  fi
done

echo ""
echo "==========================================="
echo "Cluster setup complete!"
echo "==========================================="

# List all clusters
echo ""
echo "ECS Clusters:"
aws ecs list-clusters --region "$AWS_REGION" --query 'clusterArns[*]' --output table
