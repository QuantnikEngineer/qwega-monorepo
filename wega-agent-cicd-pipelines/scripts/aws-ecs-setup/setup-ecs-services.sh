#!/bin/bash
# AWS ECS Service Setup Script for WEGA 3.0
# Creates ECS task definitions and services for all WEGA services

set -e

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-145748108830}"
CLUSTER_PREFIX="${CLUSTER_PREFIX:-wega-ecs}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Auto-discover Default VPC if not provided
echo "Discovering default VPC configuration..."

if [ -z "$VPC_ID" ]; then
  VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")
  echo "  Found Default VPC: $VPC_ID"
fi

if [ -z "$SUBNET_IDS" ]; then
  SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[*].SubnetId' --output text --region "$AWS_REGION" | tr '\t' ',')
  echo "  Found Subnets: $SUBNET_IDS"
fi

if [ -z "$SECURITY_GROUP_ID" ]; then
  # Check if wega-ecs-sg exists, create if not
  SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=wega-ecs-sg" --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION" 2>/dev/null)
  
  if [ "$SECURITY_GROUP_ID" = "None" ] || [ -z "$SECURITY_GROUP_ID" ]; then
    echo "  Creating security group: wega-ecs-sg"
    SECURITY_GROUP_ID=$(aws ec2 create-security-group --group-name wega-ecs-sg --description "WEGA ECS Fargate services" --vpc-id "$VPC_ID" --region "$AWS_REGION" --query 'GroupId' --output text)
    
    # Allow inbound on port 8080
    aws ec2 authorize-security-group-ingress --group-id "$SECURITY_GROUP_ID" --protocol tcp --port 8080 --cidr 0.0.0.0/0 --region "$AWS_REGION"
    echo "  Created and configured security group: $SECURITY_GROUP_ID"
  else
    echo "  Found Security Group: $SECURITY_GROUP_ID"
  fi
fi

# ECS Task Execution Role ARN
EXECUTION_ROLE_ARN="${EXECUTION_ROLE_ARN:-arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole}"

# Environment to setup
ENVIRONMENT="${1:-dev}"
CLUSTER_NAME="${CLUSTER_PREFIX}-${ENVIRONMENT}"

echo "==========================================="
echo "AWS ECS Service Setup for WEGA 3.0"
echo "Environment: $ENVIRONMENT"
echo "Cluster: $CLUSTER_NAME"
echo "Region: $AWS_REGION"
echo "==========================================="

# WEGA Services list
SERVICES=(
  "wega-brd:wega-brd-backend:8080"
  "wega-userstory-to-testcases-agent:wega-userstory-to-testcases-agent-backend:8080"
  "wega-brd-summary-agent:wega-brd-summary-agent-backend:8080"
  "wega-testcase-to-scripts-agent:wega-testcase-to-scripts-agent-backend:8080"
  "wega-sdlc:wega-sdlc-frontend:8080"
  "wega-sdlc-orchestrator:wega-sdlc-orchestrator-backend:8080"
  "wega-planning-orchestrator:wega-planning-orchestrator-backend:8080"
  "wega-test-orchestrator:wega-test-orchestrator-backend:8080"
  "wega-code-assistant-agent:wega-code-assistant-agent-backend:8080"
  "wega-testcases-to-testdata-agent:wega-testcases-to-testdata-agent-backend:8080"
  "wega-userstory:wega-userstory-backend:8080"
  "wega-userstory-validator:wega-userstory-validator-backend:8080"
  "wega-auth-service:wega-auth-service-backend:8080"
  "wega-api-gateway:wega-api-gateway-backend:8080"
  "wega-common-integration-service:wega-common-integration-service-backend:8080"
  "wega-usermanual:wega-usermanual-backend:8080"
  "wega-rag:wega-rag-backend:8080"
  "wega-code-to-documentation:wega-code-to-documentation-backend:8080"
  "wega-deployment-orchestrator:wega-deployment-orchestrator-backend:8080"
  "wega-cicd-agent:wega-cicd-agent-backend:8080"
  "wega-userstory-estimator:wega-userstory-estimator-backend:8080"
  "wega-cara:wega-cara-backend:8080"
  "wega-claude:wega-claude-frontend:8080"
)

# Create CloudWatch log group for environment
LOG_GROUP="/ecs/wega-${ENVIRONMENT}"
echo "Creating log group: $LOG_GROUP"
aws logs create-log-group --log-group-name "$LOG_GROUP" --region "$AWS_REGION" 2>/dev/null || echo "Log group already exists"

for SERVICE_ENTRY in "${SERVICES[@]}"; do
  IFS=':' read -r SERVICE_NAME IMAGE_NAME CONTAINER_PORT <<< "$SERVICE_ENTRY"
  
  FULL_SERVICE_NAME="${ENVIRONMENT}-${SERVICE_NAME}"
  TASK_FAMILY="wega-${ENVIRONMENT}-${SERVICE_NAME}"
  IMAGE_URI="${ECR_REGISTRY}/${IMAGE_NAME}:latest"
  
  echo ""
  echo "Setting up: $FULL_SERVICE_NAME"
  echo "  Task Family: $TASK_FAMILY"
  echo "  Image: $IMAGE_URI"
  
  # Create task definition JSON
  TASK_DEF=$(cat <<EOF
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "${EXECUTION_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "${SERVICE_NAME}",
      "image": "${IMAGE_URI}",
      "portMappings": [
        {
          "containerPort": ${CONTAINER_PORT},
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "environment": [
        {"name": "ENVIRONMENT", "value": "${ENVIRONMENT}"},
        {"name": "SERVICE_NAME", "value": "${SERVICE_NAME}"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "${LOG_GROUP}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "${SERVICE_NAME}"
        }
      }
    }
  ]
}
EOF
)
  
  # Register task definition
  echo "  Registering task definition..."
  echo "$TASK_DEF" > /tmp/task-def.json
  aws ecs register-task-definition --cli-input-json file:///tmp/task-def.json --region "$AWS_REGION" > /dev/null
  
  # Check if service exists
  SERVICE_EXISTS=$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$FULL_SERVICE_NAME" \
    --region "$AWS_REGION" --query 'services[0].status' --output text 2>/dev/null || echo "MISSING")
  
  if [ "$SERVICE_EXISTS" = "ACTIVE" ]; then
    echo "  Service exists - updating..."
    aws ecs update-service \
      --cluster "$CLUSTER_NAME" \
      --service "$FULL_SERVICE_NAME" \
      --task-definition "$TASK_FAMILY" \
      --force-new-deployment \
      --region "$AWS_REGION" > /dev/null
  else
    echo "  Creating new service..."
    aws ecs create-service \
      --cluster "$CLUSTER_NAME" \
      --service-name "$FULL_SERVICE_NAME" \
      --task-definition "$TASK_FAMILY" \
      --desired-count 1 \
      --launch-type FARGATE \
      --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_IDS}],securityGroups=[${SECURITY_GROUP_ID}],assignPublicIp=ENABLED}" \
      --region "$AWS_REGION" > /dev/null
  fi
  
  echo "  Done: $FULL_SERVICE_NAME"
done

echo ""
echo "==========================================="
echo "Service setup complete for $ENVIRONMENT!"
echo "==========================================="

# List services
echo ""
echo "Services in $CLUSTER_NAME:"
aws ecs list-services --cluster "$CLUSTER_NAME" --region "$AWS_REGION" --query 'serviceArns[*]' --output table
