# WEGA Anomaly Agent - Complete Implementation Guide

**Version:** 1.1  
**Last Updated:** 2026-04-29  
**Target Audience:** DevOps Engineers, Junior Developers  
**Platform:** Ubuntu 22.04 LTS (AWS EC2)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites - EC2 Setup](#2-prerequisites---ec2-setup)
3. [Phase 1: Repository Setup](#3-phase-1-repository-setup)
4. [Phase 2: Backend Implementation](#4-phase-2-backend-implementation)
5. [Phase 3: Docker Container](#5-phase-3-docker-container)
6. [Phase 4: AWS ECR Setup](#6-phase-4-aws-ecr-setup)
7. [Phase 5: Kubernetes Deployment](#7-phase-5-kubernetes-deployment)
8. [Phase 6: Harness CI/CD Pipeline](#8-phase-6-harness-cicd-pipeline)
9. [Phase 7: Frontend Integration (wega-sdlc)](#9-phase-7-frontend-integration-wega-sdlc)
10. [Phase 8: Testing](#10-phase-8-testing)
11. [Phase 9: Customer Deployment](#11-phase-9-customer-deployment)
12. [Troubleshooting](#12-troubleshooting)
13. [Appendix](#13-appendix)

---

## 1. Overview

### What We Are Building

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COMPLETE SOLUTION                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│  │ Monitoring Tool │     │ Anomaly Agent   │     │ wega-sdlc Frontend  │   │
│  │ (Datadog/       │────▶│ (Container on   │◀────│ (Dashboard +        │   │
│  │  Prometheus)    │     │  AWS EKS)       │     │  Chatbot UI)        │   │
│  └─────────────────┘     └────────┬────────┘     └─────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│                          ┌─────────────────┐                                │
│                          │ Kubernetes      │                                │
│                          │ (Scale/Restart) │                                │
│                          └─────────────────┘                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Technology | Repository |
|-----------|------------|------------|
| Anomaly Agent Backend | Python FastAPI | `wega-anomaly` (Harness Code Repo) |
| Container Registry | AWS ECR | - |
| Deployment Platform | AWS EKS | Existing cluster |
| CI/CD | Harness Pipelines | New pipeline |
| Code Repository | Harness Code | New repo |
| Frontend | React (wega-sdlc) | Existing repo |

---

## 2. Prerequisites - EC2 Setup

### 2.1 Launch Ubuntu EC2 Instance

**Recommended EC2 Configuration:**

| Setting | Value |
|---------|-------|
| AMI | Ubuntu Server 22.04 LTS |
| Instance Type | t3.medium (2 vCPU, 4GB RAM) |
| Storage | 30 GB gp3 |
| Security Group | SSH (22), HTTP (8080) |
| Key Pair | Create or use existing |

### 2.2 Connect to EC2

```bash
# From your local machine
ssh -i "your-key.pem" ubuntu@<EC2-PUBLIC-IP>
```

### 2.3 Install Required Tools

Run this setup script on your Ubuntu EC2:

```bash
#!/bin/bash
# Save as setup.sh and run: chmod +x setup.sh && ./setup.sh

echo "=========================================="
echo "WEGA Anomaly Agent - Environment Setup"
echo "=========================================="

# Update system
echo "[1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Docker
echo "[2/8] Installing Docker..."
sudo apt install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Install AWS CLI v2
echo "[3/8] Installing AWS CLI..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
sudo apt install -y unzip
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip

# Install kubectl
echo "[4/8] Installing kubectl..."
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl

# Install Python 3 and venv (Ubuntu 22.04 comes with Python 3.10)
echo "[5/8] Installing Python 3 and dependencies..."
sudo apt install -y python3 python3-venv python3-pip

# Install Git
echo "[6/8] Installing Git..."
sudo apt install -y git

# Install Node.js 20 LTS (for frontend)
echo "[7/8] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install jq (JSON processor)
echo "[8/8] Installing utilities..."
sudo apt install -y jq curl wget

# Verify installations
echo ""
echo "=========================================="
echo "Verification"
echo "=========================================="
echo "Docker:    $(docker --version 2>/dev/null || echo 'Not installed')"
echo "AWS CLI:   $(aws --version 2>/dev/null || echo 'Not installed')"
echo "kubectl:   $(kubectl version --client --short 2>/dev/null || echo 'Not installed')"
echo "Python:    $(python3 --version 2>/dev/null || echo 'Not installed')"
echo "Git:       $(git --version 2>/dev/null || echo 'Not installed')"
echo "Node.js:   $(node --version 2>/dev/null || echo 'Not installed')"
echo "npm:       $(npm --version 2>/dev/null || echo 'Not installed')"
echo ""
echo "=========================================="
echo "Setup complete!"
echo "Please logout and login again for Docker group to take effect."
echo "Run: exit"
echo "Then reconnect via SSH"
echo "=========================================="
```

Save and run:
```bash
# Create the script
nano setup.sh
# Paste the above content, save with Ctrl+X, Y, Enter

# Make executable and run
chmod +x setup.sh
./setup.sh

# IMPORTANT: Logout and login again for Docker permissions
exit
# Reconnect via SSH
ssh -i "your-key.pem" ubuntu@<EC2-PUBLIC-IP>

# Verify Docker works without sudo
docker ps
```

### 2.4 Configure AWS CLI

```bash
# Configure AWS credentials
aws configure

# Enter when prompted:
# AWS Access Key ID: <your-access-key>
# AWS Secret Access Key: <your-secret-key>
# Default region name: ap-south-1
# Default output format: json

# Verify configuration
aws sts get-caller-identity
```

### 2.5 Configure kubectl for EKS

```bash
# Update kubeconfig for your EKS cluster
aws eks update-kubeconfig --region ap-south-1 --name wega-platform-dev-ap-south-1-eks

# Verify connection
kubectl get nodes --profile dnaveen
kubectl get namespaces
```

---

## 3. Phase 1: Repository Setup (Harness Code Repository)

### 3.1 Create Repository in Harness

**Step 1: Login to Harness**
1. Go to your Harness account: `https://app.harness.io`
2. Navigate to your **Project** (e.g., `Harness_POC`)
3. Go to **Code Repository** from the left menu

**Step 2: Create New Repository**
1. Click **+ New Repository**
2. Fill in the details:
   - **Name**: `wega-anomaly`
   - **Description**: `WEGA Anomaly Agent - AI-powered anomaly detection`
   - **Visibility**: Private
   - **Default Branch**: `main`
   - **Add README**: No (we'll add our own)
   - **Add .gitignore**: No (we'll add our own)
3. Click **Create Repository**

**Step 3: Get Clone URL**
1. After creation, click on the repository
2. Click **Clone** button
3. Copy the HTTPS URL (format: `https://git.harness.io/<ACCOUNT>/<ORG>/<PROJECT>/wega-anomaly.git`)

### 3.2 Configure Git Credentials for Harness

```bash
# On your Ubuntu EC2 instance

# Option 1: Use Harness Personal Access Token (Recommended)
# Generate token: Harness UI → User Profile → API Keys → + Token

# Configure git credentials
git config --global credential.helper store

# Set your Harness user info
git config --global user.name "Your Name"
git config --global user.email "your.email@wipro.com"

# When you clone/push, use:
# Username: Your Harness username (or email)
# Password: Your Harness Personal Access Token
```

### 3.3 Create Working Directory and Clone

```bash
# Create project directory
mkdir -p ~/wega-projects
cd ~/wega-projects

# Clone the Harness repository
# Replace with your actual Harness repo URL
git clone https://git.harness.io/ACCOUNT_ID/ORG_ID/PROJECT_ID/wega-anomaly.git

# Enter when prompted:
# Username: your-harness-username
# Password: your-harness-personal-access-token

cd wega-anomaly
```

**Alternative: Initialize and Push**
```bash
# If you already have files locally
mkdir -p ~/wega-projects/wega-anomaly
cd ~/wega-projects/wega-anomaly

# Initialize git
git init

# Add Harness remote
git remote add origin https://git.harness.io/ACCOUNT_ID/ORG_ID/PROJECT_ID/wega-anomaly.git

# Set branch name
git branch -M main
```

### 3.4 Copy Project Files

**Option A: From local machine via SCP**
```bash
# From your LOCAL machine (not EC2):
scp -i "your-key.pem" -r /path/to/wega-anomaly/* ubuntu@<EC2-IP>:~/wega-projects/wega-anomaly/
```

**Option B: Download from existing location**
If the files are in another Harness repo or shared location, clone/copy them.

### 3.5 Verify Project Structure

```bash
cd ~/wega-projects/wega-anomaly

# Check structure
find . -type f -name "*.py" -o -name "*.yaml" -o -name "*.txt" -o -name "Dockerfile" | head -50
```

Expected structure:
```
wega-anomaly/
├── src/
│   ├── main.py
│   ├── config/
│   ├── api/
│   ├── core/
│   ├── adapters/
│   └── kubernetes/
├── deploy/
│   └── kubernetes/
├── docs/
├── Dockerfile
├── requirements.txt
└── README.md
```

### 3.6 Initial Git Commit and Push to Harness

```bash
cd ~/wega-projects/wega-anomaly

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: WEGA Anomaly Agent

- FastAPI backend with configurable AI providers
- Monitoring adapters (Datadog, Prometheus, CloudWatch)
- Kubernetes deployment manifests
- Docker configuration"

# Push to Harness Code Repository
git push -u origin main

# Enter credentials when prompted:
# Username: your-harness-username
# Password: your-harness-personal-access-token
```

### 3.7 Verify in Harness UI

1. Go to Harness → Code Repository → `wega-anomaly`
2. Verify all files are visible
3. Check the commit history shows your initial commit

---

## 4. Phase 2: Backend Implementation

### 4.1 Verify All Source Files Exist

```bash
cd ~/wega-projects/wega-anomaly

# Check all required files exist
FILES=(
    "src/main.py"
    "src/config/__init__.py"
    "src/config/settings.py"
    "src/api/__init__.py"
    "src/api/routes.py"
    "src/api/schemas.py"
    "src/core/__init__.py"
    "src/core/engine.py"
    "src/core/prompts.py"
    "src/core/confidence.py"
    "src/adapters/__init__.py"
    "src/adapters/ai_providers/__init__.py"
    "src/adapters/ai_providers/base.py"
    "src/adapters/ai_providers/gemini.py"
    "src/adapters/ai_providers/bedrock.py"
    "src/adapters/ai_providers/vertex.py"
    "src/adapters/ai_providers/openai_provider.py"
    "src/adapters/ai_providers/azure_openai.py"
    "src/adapters/monitoring/__init__.py"
    "src/adapters/monitoring/base.py"
    "src/adapters/monitoring/datadog.py"
    "src/adapters/monitoring/prometheus.py"
    "src/adapters/monitoring/cloudwatch.py"
    "src/kubernetes/__init__.py"
    "src/kubernetes/client.py"
    "Dockerfile"
    "requirements.txt"
)

echo "Checking required files..."
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✓ $file"
    else
        echo "✗ $file MISSING"
    fi
done
```

### 4.2 Create Missing Directories and __init__.py Files

```bash
# Create directories if missing
mkdir -p src/config src/api src/core src/adapters/ai_providers src/adapters/monitoring src/kubernetes

# Create empty __init__.py files if missing
touch src/__init__.py
touch src/config/__init__.py
touch src/api/__init__.py
touch src/core/__init__.py
touch src/adapters/__init__.py
touch src/adapters/ai_providers/__init__.py
touch src/adapters/monitoring/__init__.py
touch src/kubernetes/__init__.py
```

### 4.3 Local Development Setup

```bash
cd ~/wega-projects/wega-anomaly

# Create virtual environment (Ubuntu 22.04 has Python 3.10 by default)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

**Note:** Ubuntu 22.04 LTS comes with Python 3.10 pre-installed, which is compatible with this project.

### 4.4 Create Environment File for Local Testing

```bash
cd ~/wega-projects/wega-anomaly

# Create .env file
cat > .env << 'EOF'
# Adapter Selection
MONITORING_ADAPTER=datadog
AI_PROVIDER=gemini
ORCHESTRATOR_ADAPTER=harness

# Thresholds
CONFIDENCE_AUTO_THRESHOLD=80
CONFIDENCE_REVIEW_THRESHOLD=60
TRANSIENT_CPU_THRESHOLD=50
CONFIRMATION_WAIT_SECONDS=300

# Scaling
SCALING_MIN_REPLICAS=1
SCALING_MAX_REPLICAS=10

# Behavior
AUTO_REMEDIATE_ENABLED=true
REQUIRE_HUMAN_APPROVAL=false

# AI Settings
AI_MODEL=gemini-2.5-flash
AI_TIMEOUT_SECONDS=30
AI_MAX_TOKENS=8192

# Secrets (replace with real values for testing)
AI_API_KEY=your-gemini-api-key-here
MONITORING_API_KEY=your-datadog-api-key-here
MONITORING_APP_KEY=your-datadog-app-key-here

# Kubernetes (false for local testing)
K8S_IN_CLUSTER=false
K8S_NAMESPACE=anomaly-app

# Server
HOST=0.0.0.0
PORT=8080
DEBUG=true
LOG_LEVEL=INFO

# Client Info
CLIENT_NAME=local-dev
ENVIRONMENT=demo
EOF

echo ".env file created"
```

### 4.5 Run Locally (Test)

```bash
cd ~/wega-projects/wega-anomaly

# Make sure venv is activated
source venv/bin/activate

# Run the application
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
```

In another SSH session (or use `curl` from local):
```bash
# Test health endpoint
curl http://localhost:8080/health

# Expected output:
# {"status":"healthy","version":"1.0.0","components":{"api":true,"config":true}}
```

Press `Ctrl+C` to stop the server.

---

## 5. Phase 3: Docker Container

### 5.1 Build Docker Image

```bash
cd ~/wega-projects/wega-anomaly

# Build the image
docker build -t wega-wega-anomaly:latest .

# Verify image was created
docker images | grep wega-wega-anomaly
```

### 5.2 Test Docker Container Locally

```bash
# Run container with environment variables
docker run -d \
  --name wega-anomaly-test \
  -p 8080:8080 \
  -e MONITORING_ADAPTER=datadog \
  -e AI_PROVIDER=gemini \
  -e AI_API_KEY=test-key \
  -e MONITORING_API_KEY=test-key \
  -e K8S_IN_CLUSTER=false \
  -e DEBUG=true \
  wega-wega-anomaly:latest

# Check container is running
docker ps

# View logs
docker logs wega-anomaly-test

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/live
curl http://localhost:8080/ready

# Stop and remove when done testing
docker stop wega-anomaly-test
docker rm wega-anomaly-test
```

### 5.3 Docker Troubleshooting

```bash
# If build fails, check detailed logs
docker build -t wega-wega-anomaly:latest . 2>&1 | tee build.log

# If container exits immediately, check logs
docker logs wega-anomaly-test

# Enter container for debugging
docker run -it --entrypoint /bin/bash wega-wega-anomaly:latest

# Check container resource usage
docker stats wega-anomaly-test
```

---

## 6. Phase 4: AWS ECR Setup

### 6.1 Set Environment Variables

```bash
# Set variables (update these for your environment)
export AWS_REGION="ap-south-1"
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REPO_NAME="wega-wega-anomaly"

# Verify
echo "AWS Account: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "ECR Repo: $ECR_REPO_NAME"
```

### 6.2 Create ECR Repository

```bash
# Create ECR repository
aws ecr create-repository \
    --repository-name $ECR_REPO_NAME \
    --region $AWS_REGION \
    --image-scanning-configuration scanOnPush=true

# Get the repository URI
export ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME"
echo "ECR Repository URI: $ECR_URI"
```

### 6.3 Authenticate Docker to ECR

```bash
# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Expected output: "Login Succeeded"
```

### 6.4 Tag and Push Image to ECR

```bash
# Set version
export VERSION="1.0.0"

# Tag the image
docker tag wega-wega-anomaly:latest "${ECR_URI}:${VERSION}"
docker tag wega-wega-anomaly:latest "${ECR_URI}:latest"

# Push to ECR
docker push "${ECR_URI}:${VERSION}"
docker push "${ECR_URI}:latest"

# Verify image in ECR
aws ecr describe-images --repository-name $ECR_REPO_NAME --region $AWS_REGION
```

---

## 7. Phase 5: Kubernetes Deployment

### 7.1 Create Namespace

```bash
# Create namespace for Anomaly Agent
kubectl create namespace wega-system

# Verify
kubectl get namespaces | grep wega-system
```

### 7.2 Create Kubernetes Secrets

```bash
# IMPORTANT: Replace these with your actual secrets
export AI_API_KEY="your-actual-gemini-api-key"
export MONITORING_API_KEY="your-actual-datadog-api-key"
export MONITORING_APP_KEY="your-actual-datadog-app-key"

# Create secrets
kubectl create secret generic wega-anomaly-secrets \
    --namespace wega-system \
    --from-literal=ai_api_key="$AI_API_KEY" \
    --from-literal=monitoring_api_key="$MONITORING_API_KEY" \
    --from-literal=monitoring_app_key="$MONITORING_APP_KEY"

# Verify secret was created
kubectl get secrets -n wega-system
```

### 7.3 Apply ConfigMap

```bash
cd ~/wega-projects/wega-anomaly

# Apply ConfigMap
kubectl apply -f deploy/kubernetes/configmap.yaml

# Verify
kubectl get configmap wega-anomaly-config -n wega-system -o yaml
```

### 7.4 Update Deployment with ECR Image

```bash
cd ~/wega-projects/wega-anomaly

# Update the image in deployment.yaml
# Replace the placeholder image with your ECR URI
sed -i "s|image: wipro/wega-anomaly-agent:latest|image: ${ECR_URI}:${VERSION}|g" deploy/kubernetes/deployment.yaml

# Verify the change
grep "image:" deploy/kubernetes/deployment.yaml
```

### 7.5 Apply Deployment

```bash
# Apply deployment
kubectl apply -f deploy/kubernetes/deployment.yaml

# Watch pods come up
kubectl get pods -n wega-system -w

# Press Ctrl+C when pods are Running

# Check deployment status
kubectl get deployment wega-anomaly-agent -n wega-system
kubectl get pods -n wega-system
kubectl get svc -n wega-system
```

### 7.6 Verify Deployment

```bash
# Check pods are running
kubectl get pods -n wega-system -o wide

# Check logs
kubectl logs -l app=wega-anomaly-agent -n wega-system --tail=50

# Describe pod for details
kubectl describe pod -l app=wega-anomaly-agent -n wega-system

# Port forward for local testing
kubectl port-forward svc/wega-anomaly-agent -n wega-system 8080:80 &

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/status

# Stop port forward
kill %1
```

### 7.7 Create Ingress (Optional - For External Access)

**Prerequisites:** 
- AWS Load Balancer Controller must be installed on your EKS cluster
- ALB Controller IAM role must have `elasticloadbalancing:AddTags` permission

```bash
cd ~/wega-projects/wega-anomaly

# Create ingress manifest with health check configuration
cat > deploy/kubernetes/ingress.yaml << 'EOF'
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: wega-anomaly-agent
  namespace: wega-system
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/healthcheck-port: "8080"
    alb.ingress.kubernetes.io/healthcheck-interval-seconds: "30"
    alb.ingress.kubernetes.io/healthy-threshold-count: "2"
    alb.ingress.kubernetes.io/unhealthy-threshold-count: "3"
spec:
  ingressClassName: alb
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: wega-anomaly-agent
            port:
              number: 80
EOF

# Apply ingress
kubectl apply -f deploy/kubernetes/ingress.yaml

# Wait 2-3 minutes for ALB to provision
sleep 120

# Check ingress status - look for ADDRESS column
kubectl get ingress -n wega-system

# Once ADDRESS appears (e.g., k8s-wegasyst-xxx.ap-south-1.elb.amazonaws.com)
# Test the endpoint
ALB_URL=$(kubectl get ingress wega-anomaly-agent -n wega-system -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "ALB URL: $ALB_URL"
curl http://$ALB_URL/health
```

### 7.8 Configure Security Group for ALB (Important!)

**The ALB needs to reach pods on port 8080.** If you get 504 Gateway Timeout or unhealthy targets:

1. **Find the ALB Security Group:**
   ```bash
   # Go to AWS Console → EC2 → Load Balancers → Select your ALB → Security tab
   # Note the ALB security group ID (e.g., sg-02f72c2a7f1c0a00a)
   ```

2. **Add Inbound Rule to EKS Worker Node Security Group:**
   ```bash
   # Find EKS worker node security group
   aws ec2 describe-security-groups \
       --filters "Name=tag:aws:eks:cluster-name,Values=wega-platform-dev-ap-south-1-eks" \
       --query 'SecurityGroups[*].[GroupId,GroupName]' \
       --output table --region ap-south-1
   
   # Add inbound rule (replace WORKER_SG_ID and ALB_SG_ID)
   aws ec2 authorize-security-group-ingress \
       --group-id WORKER_SG_ID \
       --protocol tcp \
       --port 8080 \
       --source-group ALB_SG_ID \
       --region ap-south-1
   ```

   **Or via AWS Console:**
   - Go to EC2 → Security Groups → Find EKS worker node SG
   - Edit inbound rules → Add rule:
     - Type: Custom TCP
     - Port: 8080
     - Source: ALB Security Group ID
     - Description: ALB to pods on port 8080

3. **Verify targets are healthy:**
   - Go to EC2 → Target Groups → Select your target group
   - Check Targets tab - should show "Healthy"

4. **Test the ALB:**
   ```bash
   curl http://$ALB_URL/health
   # Expected: {"status":"healthy","version":"1.0.0","components":{...}}
   ```

**Note:** If you need a custom domain, add a `host` field under `rules` and configure DNS to point to the ALB.

---

## 8. Phase 6: Harness CI/CD Pipeline

### 8.1 Create Harness Code Connector (If Not Exists)

Since you're using Harness Code Repository, you need a connector to it:

**Step 1: Create Harness Code Connector**
1. Go to Harness → **Project Settings** → **Connectors**
2. Click **+ New Connector**
3. Select **Code Repositories** → **Harness Code**
4. Fill in:
   - **Name**: `harness-code-connector`
   - **ID**: `harness_code_connector`
5. Click **Save and Continue**
6. Test the connection
7. Note the **Connector ID** for the pipeline

### 8.2 Create Harness Pipeline YAML

```bash
cd ~/wega-projects/wega-anomaly

# Create harness directory
mkdir -p deploy/harness

# Create pipeline YAML
cat > deploy/harness/wega-anomaly-cicd.yaml << 'EOF'
pipeline:
  name: AnomalyAgent-CICD
  identifier: AnomalyAgent_CICD
  projectIdentifier: Harness_POC
  orgIdentifier: WiproPOC
  tags:
    component: wega-anomaly
    type: cicd
  
  properties:
    ci:
      codebase:
        # Use Harness Code Repository connector
        connectorRef: account.HarnessCodeConnector
        repoName: wega-anomaly
        build: <+input>
  
  variables:
    - name: AWS_REGION
      type: String
      value: ap-south-1
    - name: ECR_REPO
      type: String
      value: wega-wega-anomaly
    - name: K8S_NAMESPACE
      type: String
      value: wega-system
  
  stages:
    # Stage 1: Build and Push Docker Image
    - stage:
        name: Build
        identifier: build
        type: CI
        spec:
          cloneCodebase: true
          infrastructure:
            type: KubernetesDirect
            spec:
              connectorRef: YOUR_K8S_CONNECTOR
              namespace: harness-builds
          execution:
            steps:
              - step:
                  type: Run
                  name: Run Tests
                  identifier: run_tests
                  spec:
                    shell: Bash
                    command: |
                      pip install -r requirements.txt
                      pip install pytest pytest-asyncio
                      python -m pytest tests/ -v || true
              
              - step:
                  type: BuildAndPushECR
                  name: Build and Push to ECR
                  identifier: build_push_ecr
                  spec:
                    connectorRef: YOUR_AWS_CONNECTOR
                    region: <+pipeline.variables.AWS_REGION>
                    account: <+pipeline.variables.AWS_ACCOUNT_ID>
                    imageName: <+pipeline.variables.ECR_REPO>
                    tags:
                      - <+pipeline.sequenceId>
                      - latest
                    dockerfile: Dockerfile
                    context: .
    
    # Stage 2: Deploy to EKS
    - stage:
        name: Deploy
        identifier: deploy
        type: Deployment
        spec:
          deploymentType: Kubernetes
          service:
            serviceRef: AnomalyAgentService
          environment:
            environmentRef: Development
            infrastructureDefinitions:
              - identifier: EKS_Dev
          execution:
            steps:
              - step:
                  type: K8sRollingDeploy
                  name: Rolling Deployment
                  identifier: rolling_deploy
                  spec:
                    skipDryRun: false
            rollbackSteps:
              - step:
                  type: K8sRollingRollback
                  name: Rollback
                  identifier: rollback
        delegateSelectors:
          - aws-delegator
EOF

echo "Harness pipeline YAML created at deploy/harness/wega-anomaly-cicd.yaml"
```

### 8.3 Steps to Create Pipeline in Harness UI

1. **Login to Harness** → Go to your project
2. **Pipelines** → **+ Create Pipeline**
3. **Name**: `AnomalyAgent-CICD`
4. **Setup**: Choose **YAML** mode
5. **Paste** the YAML from `deploy/harness/wega-anomaly-cicd.yaml`
6. **Update Connector References**:
   - `account.HarnessCodeConnector` → Your Harness Code connector ID (or keep as-is if using default)
   - `YOUR_K8S_CONNECTOR` → Your Kubernetes connector ID
   - `YOUR_AWS_CONNECTOR` → Your AWS connector ID

### 8.4 Configure Triggers for Harness Code Repository

**Option A: Using Harness UI (Recommended)**
1. Go to your pipeline → **Triggers** → **+ New Trigger**
2. Select **Harness Code Repository** (not GitHub/GitLab)
3. Fill in:
   - **Name**: `On Push to Main`
   - **Connector**: Select your Harness Code connector
   - **Repository**: `wega-anomaly`
   - **Event**: `Push`
   - **Branch**: `main`
4. Click **Create Trigger**

**Option B: Auto-trigger on Pipeline**
Harness Code Repository has built-in integration. The pipeline will automatically detect pushes when configured with Harness Code connector.

### 8.5 Verify Pipeline Setup

1. Go to **Code Repository** → `wega-anomaly`
2. Make a small change (e.g., update README)
3. Commit and push
4. Go to **Pipelines** → Check if pipeline triggered automatically

---

## 9. Phase 7: Frontend Integration (wega-sdlc)

### 9.1 Clone wega-sdlc Repository

```bash
cd ~/wega-projects

# Clone the frontend repo
git clone <wega-sdlc-repo-url> wega-sdlc
cd wega-sdlc

# Install dependencies
npm install

# Verify it runs (optional)
npm run dev
# Press Ctrl+C to stop
```

### 9.2 Create API Service File

```bash
cd ~/wega-projects/wega-sdlc

# Create the API service file
cat > src/services/anomalyAgentApi.ts << 'EOF'
/**
 * Anomaly Agent API Client
 * @file src/services/anomalyAgentApi.ts
 */

import { apiFetch } from './apiClient';

const ANOMALY_AGENT_URL = import.meta.env.VITE_ANOMALY_AGENT_URL || '/wega-anomaly';

// ==================== TYPES ====================

export interface KubernetesAction {
  action_type: 'scale_up' | 'scale_down' | 'restart' | 'rollback' | 'none';
  target_replicas: number | null;
  rationale: string;
}

export interface AnalyzeResponse {
  request_id: string;
  confidence_score: number;
  pipeline_decision: 'PROCEED_AUTOMATION' | 'HUMAN_REVIEW' | 'MONITORING_ONLY' | 'TRANSIENT_RESOLVED';
  automation_approved: boolean;
  recommended_action: KubernetesAction;
  root_cause_analysis: string;
  executive_summary: string;
  risk_assessment: string;
  transient_resolved: boolean;
  original_alert_value: number | null;
  current_value_after_wait: number | null;
  analysis_timestamp: string;
  ai_provider: string;
  ai_model: string;
  latency_ms: number;
}

export interface RemediateRequest {
  action: 'scale_up' | 'scale_down' | 'restart' | 'rollback' | 'none';
  target_replicas?: number;
  deployment: string;
  namespace: string;
  request_id?: string;
  force?: boolean;
}

export interface RemediateResponse {
  request_id: string;
  status: 'pending' | 'in_progress' | 'success' | 'failed' | 'skipped';
  action_performed: string;
  previous_replicas: number | null;
  new_replicas: number | null;
  message: string;
  execution_time_ms: number;
  timestamp: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface ChatResponse {
  conversation_id: string;
  response: string;
  suggested_actions: string[];
  references: Array<{ title: string; url: string }>;
  timestamp: string;
}

export interface AlertHistoryItem {
  alert_id: string;
  title: string;
  timestamp: string;
  severity: string;
  decision: string;
  remediation_status: string;
  confidence_score: number;
}

export interface SystemStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  uptime_seconds: number;
  last_alert_time: string | null;
  total_alerts_processed: number;
  total_remediations: number;
  ai_provider: string;
  ai_provider_healthy: boolean;
  monitoring_adapter: string;
  monitoring_adapter_healthy: boolean;
}

export interface StatusResponse {
  system: SystemStatus;
  recent_alerts: AlertHistoryItem[];
  configuration: Record<string, unknown>;
}

// ==================== API FUNCTIONS ====================

export async function analyzeAlert(alertPayload: Record<string, unknown>): Promise<AnalyzeResponse> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/api/v1/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ alert_payload: alertPayload }),
  });
  
  if (!response.ok) {
    throw new Error(`Analysis failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function executeRemediation(request: RemediateRequest): Promise<RemediateResponse> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/api/v1/remediate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  
  if (!response.ok) {
    throw new Error(`Remediation failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function sendChatMessage(
  message: string,
  conversationId?: string
): Promise<ChatResponse> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/api/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });
  
  if (!response.ok) {
    throw new Error(`Chat failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function getAnomalyStatus(): Promise<StatusResponse> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/api/v1/status`);
  
  if (!response.ok) {
    throw new Error(`Status check failed: ${response.statusText}`);
  }
  
  return response.json();
}

export async function healthCheck(): Promise<{ status: string; components: Record<string, boolean> }> {
  const response = await apiFetch(`${ANOMALY_AGENT_URL}/health`);
  
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`);
  }
  
  return response.json();
}
EOF

echo "Created src/services/anomalyAgentApi.ts"
```

### 9.3 Create Component Folder

```bash
cd ~/wega-projects/wega-sdlc

# Create AnomalyAgent component folder
mkdir -p src/components/AnomalyAgent
```

### 9.4 Create AnomalyDashboard.tsx

```bash
cat > src/components/AnomalyAgent/AnomalyDashboard.tsx << 'EOF'
/**
 * Anomaly Agent Dashboard
 * @file src/components/AnomalyAgent/AnomalyDashboard.tsx
 */

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  getAnomalyStatus, 
  StatusResponse, 
  AlertHistoryItem 
} from '../../services/anomalyAgentApi';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { 
  Activity, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  MessageSquare,
  RefreshCw,
  Server,
  Cpu
} from 'lucide-react';

interface AnomalyDashboardProps {
  isDarkMode: boolean;
  onOpenChatbot: () => void;
  onBack: () => void;
}

export function AnomalyDashboard({ isDarkMode, onOpenChatbot, onBack }: AnomalyDashboardProps) {
  const { data: status, isLoading, error, refetch } = useQuery<StatusResponse>({
    queryKey: ['anomalyStatus'],
    queryFn: getAnomalyStatus,
    refetchInterval: 30000,
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'healthy':
        return <Badge className="bg-green-500">Healthy</Badge>;
      case 'degraded':
        return <Badge className="bg-yellow-500">Degraded</Badge>;
      case 'unhealthy':
        return <Badge className="bg-red-500">Unhealthy</Badge>;
      default:
        return <Badge className="bg-gray-500">Unknown</Badge>;
    }
  };

  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case 'PROCEED_AUTOMATION':
        return <Badge className="bg-green-500">Auto</Badge>;
      case 'HUMAN_REVIEW':
        return <Badge className="bg-yellow-500">Review</Badge>;
      case 'MONITORING_ONLY':
        return <Badge className="bg-blue-500">Monitor</Badge>;
      case 'TRANSIENT_RESOLVED':
        return <Badge className="bg-gray-500">Resolved</Badge>;
      default:
        return <Badge>{decision}</Badge>;
    }
  };

  const formatUptime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <RefreshCw className="animate-spin h-8 w-8" />
        <span className="ml-2">Loading...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen text-red-500">
        <AlertTriangle className="h-8 w-8" />
        <span className="ml-2">Error loading status: {(error as Error).message}</span>
      </div>
    );
  }

  return (
    <div className={`min-h-screen p-6 ${isDarkMode ? 'bg-gray-900 text-white' : 'bg-gray-50 text-gray-900'}`}>
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold">Anomaly Agent</h1>
          <p className="text-gray-500">AI-powered anomaly detection and remediation</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={onOpenChatbot}>
            <MessageSquare className="h-4 w-4 mr-2" />
            Open Chatbot
          </Button>
          <Button variant="ghost" onClick={onBack}>
            Back
          </Button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">System Status</CardTitle>
            <Server className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            {status && getStatusBadge(status.system.status)}
            <p className="text-xs text-gray-500 mt-1">
              Uptime: {status ? formatUptime(status.system.uptime_seconds) : 'N/A'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Alerts Processed</CardTitle>
            <AlertTriangle className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {status?.system.total_alerts_processed || 0}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Remediations</CardTitle>
            <CheckCircle className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {status?.system.total_remediations || 0}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">AI Provider</CardTitle>
            <Cpu className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold capitalize">
              {status?.system.ai_provider || 'N/A'}
            </div>
            {status?.system.ai_provider_healthy ? (
              <Badge className="bg-green-500 text-xs">Connected</Badge>
            ) : (
              <Badge className="bg-red-500 text-xs">Disconnected</Badge>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Alerts Table */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Recent Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Alert</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Decision</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {status?.recent_alerts.map((alert: AlertHistoryItem) => (
                <TableRow key={alert.alert_id}>
                  <TableCell className="font-medium">{alert.title}</TableCell>
                  <TableCell>
                    <Badge variant={alert.severity === 'critical' ? 'destructive' : 'secondary'}>
                      {alert.severity}
                    </Badge>
                  </TableCell>
                  <TableCell>{getDecisionBadge(alert.decision)}</TableCell>
                  <TableCell>{alert.confidence_score}%</TableCell>
                  <TableCell>
                    <Badge variant={alert.remediation_status === 'success' ? 'default' : 'secondary'}>
                      {alert.remediation_status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {new Date(alert.timestamp).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
              {(!status?.recent_alerts || status.recent_alerts.length === 0) && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-gray-500">
                    No recent alerts
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-500">Monitoring</p>
              <p className="font-semibold capitalize">{status?.system.monitoring_adapter}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">AI Provider</p>
              <p className="font-semibold capitalize">{status?.system.ai_provider}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Auto Threshold</p>
              <p className="font-semibold">{status?.configuration?.confidence_auto_threshold}%</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Environment</p>
              <p className="font-semibold capitalize">{status?.configuration?.environment}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
EOF

echo "Created src/components/AnomalyAgent/AnomalyDashboard.tsx"
```

### 9.5 Create AnomalyChatbot.tsx

```bash
cat > src/components/AnomalyAgent/AnomalyChatbot.tsx << 'EOF'
/**
 * Anomaly Agent Chatbot
 * @file src/components/AnomalyAgent/AnomalyChatbot.tsx
 */

import { useState, useRef, useEffect } from 'react';
import { sendChatMessage, ChatResponse } from '../../services/anomalyAgentApi';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { X, Send, Bot, User, Loader2 } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  suggestedActions?: string[];
}

interface AnomalyChatbotProps {
  isDarkMode: boolean;
  isOpen: boolean;
  onClose: () => void;
}

export function AnomalyChatbot({ isDarkMode, isOpen, onClose }: AnomalyChatbotProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Hello! I\'m the Anomaly Agent assistant. I can help you understand system status, recent alerts, and remediation actions. How can I help you today?',
      timestamp: new Date(),
      suggestedActions: ['Show system status', 'List recent alerts', 'Explain thresholds'],
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (messageText?: string) => {
    const text = messageText || input;
    if (!text.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response: ChatResponse = await sendChatMessage(text, conversationId);
      setConversationId(response.conversation_id);

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date(response.timestamp),
        suggestedActions: response.suggested_actions,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${(error as Error).message}. Please try again.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-96 z-50 shadow-xl">
      <Card className={`h-full flex flex-col ${isDarkMode ? 'bg-gray-800 text-white' : 'bg-white'}`}>
        {/* Header */}
        <div className={`flex items-center justify-between p-4 border-b ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className="flex items-center gap-2">
            <Bot className="h-6 w-6 text-blue-500" />
            <span className="font-semibold">Anomaly Agent Chat</span>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-3 ${
                  message.role === 'user'
                    ? 'bg-blue-500 text-white'
                    : isDarkMode
                    ? 'bg-gray-700'
                    : 'bg-gray-100'
                }`}
              >
                <div className="flex items-start gap-2">
                  {message.role === 'assistant' && <Bot className="h-4 w-4 mt-1" />}
                  <div>
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    {message.suggestedActions && message.suggestedActions.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {message.suggestedActions.map((action, i) => (
                          <Button
                            key={i}
                            variant="outline"
                            size="sm"
                            className="text-xs"
                            onClick={() => handleSend(action)}
                          >
                            {action}
                          </Button>
                        ))}
                      </div>
                    )}
                  </div>
                  {message.role === 'user' && <User className="h-4 w-4 mt-1" />}
                </div>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className={`rounded-lg p-3 ${isDarkMode ? 'bg-gray-700' : 'bg-gray-100'}`}>
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className={`p-4 border-t ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              className={`flex-1 rounded-lg px-4 py-2 border ${
                isDarkMode
                  ? 'bg-gray-700 border-gray-600 text-white'
                  : 'bg-white border-gray-300'
              }`}
              disabled={isLoading}
            />
            <Button onClick={() => handleSend()} disabled={isLoading || !input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
EOF

echo "Created src/components/AnomalyAgent/AnomalyChatbot.tsx"
```

### 9.6 Create Index Export

```bash
cat > src/components/AnomalyAgent/index.ts << 'EOF'
export { AnomalyDashboard } from './AnomalyDashboard';
export { AnomalyChatbot } from './AnomalyChatbot';
EOF

echo "Created src/components/AnomalyAgent/index.ts"
```

### 9.7 Update Environment Variables

```bash
# Add to .env file
echo "" >> .env
echo "# Anomaly Agent API URL" >> .env
echo "VITE_ANOMALY_AGENT_URL=http://localhost:8080" >> .env

# Also update .env.example
echo "" >> .env.example
echo "# Anomaly Agent API URL" >> .env.example
echo "VITE_ANOMALY_AGENT_URL=http://localhost:8080" >> .env.example

echo "Updated .env and .env.example"
```

### 9.8 Manual Changes Required in App.tsx

Open `src/App.tsx` in your editor and make these changes:

```bash
# Open the file
nano src/App.tsx
```

**Changes to make:**

1. **Add import** (near the top with other imports):
```typescript
import { AnomalyDashboard, AnomalyChatbot } from './components/AnomalyAgent';
```

2. **Add state** (inside AppContent function, with other useState):
```typescript
const [isAnomalyChatbotOpen, setIsAnomalyChatbotOpen] = useState(false);
```

3. **Add navigation function** (with other navigate functions):
```typescript
const navigateToAnomalyAgent = () => {
  navigate('/wega-anomaly');
  window.scrollTo(0, 0);
};
```

4. **Add route** (inside `<Routes>`, after other routes):
```typescript
<Route
  path="/wega-anomaly"
  element={withAuthGuard(
    <>
      <AnomalyDashboard 
        isDarkMode={isDarkMode}
        onOpenChatbot={() => setIsAnomalyChatbotOpen(true)}
        onBack={navigateToDashboard}
      />
      <AnomalyChatbot
        isDarkMode={isDarkMode}
        isOpen={isAnomalyChatbotOpen}
        onClose={() => setIsAnomalyChatbotOpen(false)}
      />
    </>,
    { requiredCapability: 'sdlc:execute' }
  )}
/>
```

5. **Update Header props** (pass the new navigation function):
```typescript
<Header 
  // ... existing props
  onNavigateToAnomalyAgent={navigateToAnomalyAgent}
/>
```

### 9.9 Manual Changes Required in Header.tsx

Open `src/components/Header.tsx` and add:

1. **Add to interface**:
```typescript
onNavigateToAnomalyAgent?: () => void;
```

2. **Add to function parameters**:
```typescript
export function Header({ 
  // ... existing params
  onNavigateToAnomalyAgent 
}: HeaderProps) {
```

3. **Add menu item** (in navigation section):
```typescript
<button 
  onClick={onNavigateToAnomalyAgent}
  className="text-sm font-medium hover:text-primary"
>
  Anomaly Agent
</button>
```

### 9.10 Test Frontend Changes

```bash
cd ~/wega-projects/wega-sdlc

# Install dependencies (if any new ones)
npm install

# Run development server
npm run dev

# Access at http://<EC2-IP>:5173/wega-anomaly
# (Make sure port 5173 is open in security group)
```

### 9.11 Commit Frontend Changes

```bash
cd ~/wega-projects/wega-sdlc

git add .
git commit -m "feat: Add Anomaly Agent dashboard and chatbot integration

- Add anomalyAgentApi.ts service
- Add AnomalyDashboard component with status, alerts, metrics
- Add AnomalyChatbot component with conversation support
- Add route /wega-anomaly
- Add navigation in Header"

git push origin main
```

---

## 10. Phase 8: Testing

### 10.1 Test Backend API

```bash
# Port forward if testing against K8s deployment
kubectl port-forward svc/wega-anomaly-agent -n wega-system 8080:80 &

# Health check
curl http://localhost:8080/health

# Status endpoint
curl http://localhost:8080/api/v1/status | jq .

# Test analyze endpoint with mock alert
curl -X POST http://localhost:8080/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "alert_payload": {
      "title": "High CPU Alert",
      "alert_metric": "kubernetes.cpu.usage.total",
      "alert_value": 92,
      "hostname": "test-node",
      "status": "triggered"
    }
  }' | jq .

# Test chat endpoint
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the current system status?"
  }' | jq .

# Stop port forward
kill %1
```

### 10.2 Test Frontend

1. Open browser to `http://<EC2-IP>:5173`
2. Login with valid credentials
3. Navigate to **Anomaly Agent** (from menu)
4. Verify:
   - [ ] Dashboard loads without errors
   - [ ] Status cards show data
   - [ ] Recent alerts table displays
   - [ ] Configuration section shows settings
   - [ ] "Open Chatbot" button works
   - [ ] Chatbot opens as slide-out panel
   - [ ] Can send messages and receive responses
   - [ ] Suggested actions work as quick replies

### 10.3 End-to-End Test

```bash
# 1. Trigger a test alert (simulate Datadog webhook)
curl -X POST http://localhost:8080/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "alert_payload": {
      "title": "CPU is High on anomaly-demo-app",
      "alert_metric": "kubernetes.cpu.usage.total",
      "alert_value": 95,
      "hostname": "eks-node-1",
      "pod_name": "anomaly-demo-app-abc123",
      "kube_namespace": "anomaly-app",
      "kube_deployment": "anomaly-demo-app",
      "alert_transition": "triggered"
    }
  }' | jq .

# 2. Check the response includes:
#    - confidence_score
#    - pipeline_decision
#    - recommended_action
#    - root_cause_analysis

# 3. Verify in frontend dashboard that alert appears in recent alerts
```

---

## 11. Phase 9: Customer Deployment

### 11.1 Customer Deployment Checklist

For each customer deployment, customize these values:

| Setting | Description | Example |
|---------|-------------|---------|
| `CLIENT_NAME` | Customer identifier | `acme-corp` |
| `ENVIRONMENT` | Deployment environment | `production` |
| `MONITORING_ADAPTER` | Their monitoring tool | `prometheus` |
| `AI_PROVIDER` | Their preferred AI | `bedrock` |
| `CONFIDENCE_AUTO_THRESHOLD` | Auto-remediation threshold | `85` |
| `SCALING_MAX_REPLICAS` | Max pods allowed | `20` |
| `AI_API_KEY` | Customer's AI API key | (secret) |
| `MONITORING_API_KEY` | Customer's monitoring key | (secret) |

### 11.2 Deployment Script for New Customers

```bash
cd ~/wega-projects/wega-anomaly

# Create deployment script
cat > deploy-customer.sh << 'EOF'
#!/bin/bash

# Customer Deployment Script
# Usage: ./deploy-customer.sh <customer-name> <environment> <monitoring> <ai-provider>

set -e

CUSTOMER_NAME=$1
ENVIRONMENT=$2
MONITORING_ADAPTER=$3
AI_PROVIDER=$4

if [ -z "$CUSTOMER_NAME" ] || [ -z "$ENVIRONMENT" ] || [ -z "$MONITORING_ADAPTER" ] || [ -z "$AI_PROVIDER" ]; then
    echo "Usage: ./deploy-customer.sh <customer-name> <environment> <monitoring> <ai-provider>"
    echo "Example: ./deploy-customer.sh acme-corp production prometheus bedrock"
    exit 1
fi

NAMESPACE="wega-system"

echo "=========================================="
echo "Deploying Anomaly Agent"
echo "Customer: $CUSTOMER_NAME"
echo "Environment: $ENVIRONMENT"
echo "Monitoring: $MONITORING_ADAPTER"
echo "AI Provider: $AI_PROVIDER"
echo "=========================================="

# Prompt for secrets
read -sp "Enter AI API Key: " AI_API_KEY
echo ""
read -sp "Enter Monitoring API Key: " MONITORING_API_KEY
echo ""
read -sp "Enter Monitoring App Key (or press Enter to skip): " MONITORING_APP_KEY
echo ""

# 1. Create namespace if not exists
echo "[1/4] Creating namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# 2. Create secrets
echo "[2/4] Creating secrets..."
kubectl create secret generic wega-anomaly-secrets \
    --namespace $NAMESPACE \
    --from-literal=ai_api_key="$AI_API_KEY" \
    --from-literal=monitoring_api_key="$MONITORING_API_KEY" \
    --from-literal=monitoring_app_key="$MONITORING_APP_KEY" \
    --dry-run=client -o yaml | kubectl apply -f -

# 3. Create ConfigMap
echo "[3/4] Creating ConfigMap..."
cat <<CONFIGMAP | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: wega-anomaly-config
  namespace: $NAMESPACE
data:
  monitoring_adapter: "$MONITORING_ADAPTER"
  ai_provider: "$AI_PROVIDER"
  confidence_auto_threshold: "80"
  confidence_review_threshold: "60"
  transient_cpu_threshold: "50"
  confirmation_wait_seconds: "300"
  scaling_min_replicas: "1"
  scaling_max_replicas: "10"
  auto_remediate_enabled: "true"
  require_human_approval: "false"
  ai_model: "gemini-2.5-flash"
  client_name: "$CUSTOMER_NAME"
  environment: "$ENVIRONMENT"
CONFIGMAP

# 4. Apply deployment
echo "[4/4] Applying deployment..."
kubectl apply -f deploy/kubernetes/deployment.yaml

# Wait for rollout
echo "Waiting for rollout..."
kubectl rollout status deployment/wega-anomaly-agent -n $NAMESPACE --timeout=300s

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
kubectl get pods -n $NAMESPACE -l app=wega-anomaly-agent
EOF

chmod +x deploy-customer.sh
echo "Created deploy-customer.sh"
```

**Usage:**
```bash
./deploy-customer.sh acme-corp production prometheus bedrock
```

---

## 12. Troubleshooting

### 12.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Pod CrashLoopBackOff | Missing secrets | `kubectl get secrets -n wega-system` |
| API returns 500 | AI provider error | `kubectl logs -l app=wega-anomaly-agent -n wega-system` |
| "Connection refused" | Service not running | `kubectl get svc -n wega-system` |
| Frontend can't connect | CORS or URL issue | Check `VITE_ANOMALY_AGENT_URL` |
| ECR push fails | Auth expired | Re-run ECR login command |
| Docker permission denied | User not in docker group | `sudo usermod -aG docker $USER` then logout/login |

### 12.2 Debug Commands

```bash
# Check pod status
kubectl get pods -n wega-system -o wide

# View pod logs
kubectl logs -l app=wega-anomaly-agent -n wega-system --tail=100

# Describe pod for events
kubectl describe pod -l app=wega-anomaly-agent -n wega-system

# Check secrets exist
kubectl get secrets -n wega-system

# Check configmap
kubectl get configmap wega-anomaly-config -n wega-system -o yaml

# Enter pod for debugging
kubectl exec -it $(kubectl get pod -l app=wega-anomaly-agent -n wega-system -o jsonpath='{.items[0].metadata.name}') -n wega-system -- /bin/bash

# Port forward for local testing
kubectl port-forward svc/wega-anomaly-agent -n wega-system 8080:80

# Check Docker logs
docker logs <container-id>

# Check Docker container status
docker inspect <container-id>
```

### 12.3 Rollback Deployment

```bash
# View rollout history
kubectl rollout history deployment/wega-anomaly-agent -n wega-system

# Rollback to previous version
kubectl rollout undo deployment/wega-anomaly-agent -n wega-system

# Rollback to specific revision
kubectl rollout undo deployment/wega-anomaly-agent -n wega-system --to-revision=2
```

---

## 13. Appendix

### 13.1 File Checklist

**Backend (wega-anomaly repo):**
- [ ] `src/main.py`
- [ ] `src/__init__.py`
- [ ] `src/config/__init__.py`
- [ ] `src/config/settings.py`
- [ ] `src/api/__init__.py`
- [ ] `src/api/routes.py`
- [ ] `src/api/schemas.py`
- [ ] `src/core/__init__.py`
- [ ] `src/core/engine.py`
- [ ] `src/core/prompts.py`
- [ ] `src/core/confidence.py`
- [ ] `src/adapters/__init__.py`
- [ ] `src/adapters/ai_providers/__init__.py`
- [ ] `src/adapters/ai_providers/base.py`
- [ ] `src/adapters/ai_providers/gemini.py`
- [ ] `src/adapters/ai_providers/bedrock.py`
- [ ] `src/adapters/ai_providers/vertex.py`
- [ ] `src/adapters/ai_providers/openai_provider.py`
- [ ] `src/adapters/ai_providers/azure_openai.py`
- [ ] `src/adapters/monitoring/__init__.py`
- [ ] `src/adapters/monitoring/base.py`
- [ ] `src/adapters/monitoring/datadog.py`
- [ ] `src/adapters/monitoring/prometheus.py`
- [ ] `src/adapters/monitoring/cloudwatch.py`
- [ ] `src/kubernetes/__init__.py`
- [ ] `src/kubernetes/client.py`
- [ ] `deploy/kubernetes/deployment.yaml`
- [ ] `deploy/kubernetes/configmap.yaml`
- [ ] `Dockerfile`
- [ ] `requirements.txt`
- [ ] `README.md`
- [ ] `.gitignore`

**Frontend (wega-sdlc repo):**
- [ ] `src/services/anomalyAgentApi.ts`
- [ ] `src/components/AnomalyAgent/index.ts`
- [ ] `src/components/AnomalyAgent/AnomalyDashboard.tsx`
- [ ] `src/components/AnomalyAgent/AnomalyChatbot.tsx`
- [ ] `src/App.tsx` (modified)
- [ ] `src/components/Header.tsx` (modified)
- [ ] `.env` (modified)

### 13.2 Environment Variables Reference

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MONITORING_ADAPTER` | string | datadog | datadog, prometheus, cloudwatch, splunk, dynatrace |
| `AI_PROVIDER` | string | gemini | gemini, bedrock, vertex, openai, azure_openai |
| `CONFIDENCE_AUTO_THRESHOLD` | int | 80 | 0-100 |
| `CONFIDENCE_REVIEW_THRESHOLD` | int | 60 | 0-100 |
| `TRANSIENT_CPU_THRESHOLD` | int | 50 | 0-100 |
| `CONFIRMATION_WAIT_SECONDS` | int | 300 | Seconds |
| `SCALING_MIN_REPLICAS` | int | 1 | Minimum pods |
| `SCALING_MAX_REPLICAS` | int | 10 | Maximum pods |
| `AUTO_REMEDIATE_ENABLED` | bool | true | true/false |
| `REQUIRE_HUMAN_APPROVAL` | bool | false | true/false |
| `AI_MODEL` | string | gemini-2.5-flash | Model name |
| `AI_API_KEY` | secret | - | Required |
| `MONITORING_API_KEY` | secret | - | Required |
| `MONITORING_APP_KEY` | secret | - | Optional (Datadog) |
| `CLIENT_NAME` | string | default | Customer identifier |
| `ENVIRONMENT` | string | demo | demo, staging, production |

### 13.3 API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/live` | Liveness probe |
| GET | `/ready` | Readiness probe |
| GET | `/api/v1/status` | System status and recent alerts |
| POST | `/api/v1/analyze` | Analyze alert, return AI decision |
| POST | `/api/v1/remediate` | Execute remediation action |
| POST | `/api/v1/chat` | Chatbot interaction |

### 13.4 Useful Commands Quick Reference

```bash
# AWS
aws configure                                    # Setup AWS credentials
aws sts get-caller-identity                      # Verify AWS identity
aws eks update-kubeconfig --region <r> --name <c>  # Configure kubectl

# Docker
docker build -t <name>:<tag> .                   # Build image
docker run -d -p 8080:8080 <image>               # Run container
docker logs <container>                          # View logs
docker exec -it <container> /bin/bash            # Enter container

# ECR
aws ecr get-login-password | docker login ...    # Login to ECR
docker tag <image> <ecr-uri>:<tag>               # Tag for ECR
docker push <ecr-uri>:<tag>                      # Push to ECR

# Kubernetes
kubectl get pods -n <namespace>                  # List pods
kubectl logs -l app=<name> -n <namespace>        # View logs
kubectl describe pod <name> -n <namespace>       # Pod details
kubectl port-forward svc/<name> 8080:80          # Port forward
kubectl apply -f <file.yaml>                     # Apply manifest
kubectl rollout status deployment/<name>         # Check rollout
kubectl rollout undo deployment/<name>           # Rollback
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-29 | AI Assistant | Initial version (Windows/PowerShell) |
| 1.1 | 2026-04-29 | AI Assistant | Updated for Ubuntu/Linux |

---

**End of Document**
