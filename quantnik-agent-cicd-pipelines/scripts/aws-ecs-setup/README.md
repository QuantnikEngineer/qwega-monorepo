# AWS ECS Setup Scripts for QUANTNIK 3.0

Scripts to set up AWS ECS infrastructure for QUANTNIK 3.0 deployments.

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Existing VPC with subnets
3. Security group allowing traffic on port 8080
4. ECR repositories created for all QUANTNIK images
5. IAM role `ecsTaskExecutionRole` with permissions

## Scripts

### 1. setup-ecs-clusters.sh

Creates ECS Fargate clusters for each environment:
- `quantnik-ecs-dev`
- `quantnik-ecs-qa`
- `quantnik-ecs-stage`

```bash
# Default region (ap-south-1)
./setup-ecs-clusters.sh

# Custom region
AWS_REGION=us-east-1 ./setup-ecs-clusters.sh
```

### 2. setup-ecs-services.sh

Creates task definitions and ECS services for all 23 QUANTNIK services.

**Before running, update these variables:**

```bash
export VPC_ID="vpc-xxxxxxxxx"
export SUBNET_IDS="subnet-xxxxxxxx,subnet-yyyyyyyy"
export SECURITY_GROUP_ID="sg-xxxxxxxxx"
export AWS_ACCOUNT_ID="145748108830"
export AWS_REGION="us-east-1"
```

**Run for each environment:**

```bash
# Dev environment
./setup-ecs-services.sh dev

# QA environment
./setup-ecs-services.sh qa

# Stage environment
./setup-ecs-services.sh stage
```

## Cluster Naming Convention

| Environment | Cluster Name |
|-------------|--------------|
| Dev | `quantnik-ecs-dev` |
| QA | `quantnik-ecs-qa` |
| Stage | `quantnik-ecs-stage` |
| Production | `quantnik-ecs-prod` |

## Service Naming Convention

Services are named: `{env}-{service-name}`

Examples:
- `dev-quantnik-brd`
- `dev-quantnik-sdlc`
- `qa-quantnik-auth-service`

## Required IAM Permissions

The ECS Task Execution Role needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

## Create ECR Repositories

Before running deployments, create ECR repos:

```bash
# Create all ECR repositories
for repo in quantnik-brd-backend quantnik-sdlc-frontend quantnik-auth-service-backend ...; do
  aws ecr create-repository --repository-name "$repo" --region ap-south-1
done
```

## Network Requirements

| Component | Requirement |
|-----------|-------------|
| VPC | At least 2 subnets in different AZs |
| Security Group | Allow inbound on port 8080 |
| Internet Access | Required for pulling images from ECR |

## Integration with Harness

The existing Harness pipeline `RepoWorkerBuildDeployECS` is already configured to:
1. Build images and push to ECR
2. Deploy to ECS using `aws ecs update-service --force-new-deployment`

After running these setup scripts, the Harness pipeline will work automatically.
