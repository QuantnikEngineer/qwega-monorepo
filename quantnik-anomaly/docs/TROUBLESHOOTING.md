# QUANTNIK Anomaly Agent - Troubleshooting Guide

**Purpose:** Document common issues encountered during setup and deployment, with solutions.  
**Platform:** Ubuntu 22.04 LTS (AWS EC2)  
**Last Updated:** 2026-04-30

---

## Table of Contents

1. [Python Issues](#1-python-issues)
2. [Docker Issues](#2-docker-issues)
3. [Kubernetes/EKS Issues](#3-kuberneteseks-issues)
4. [AWS ECR Issues](#4-aws-ecr-issues)
5. [API/Application Issues](#5-apiapplication-issues)
6. [Harness CI/CD Issues](#6-harness-cicd-issues)

---

## 1. Python Issues

### 1.1 Python 3.11 Not Found

**Error:**
```
Command 'python3.11' not found, but can be installed with:
apt install python3.11

E: Unable to locate package python3.11
E: Couldn't find any package by glob 'python3.11'
```

**Cause:**  
Python 3.11 is not available in Ubuntu 22.04's default repositories.

**Solution:**  
Use the default Python 3.10 that comes with Ubuntu 22.04:

```bash
# Use python3 instead of python3.11
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Alternative (if Python 3.11 is required):**
```bash
# Add deadsnakes PPA
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Then use python3.11
python3.11 -m venv venv
```

---

## 2. Docker Issues

### 2.1 Docker Container Not Using .env File

**Symptom:**
- Updated `.env` file with real API keys
- Container still shows `ai_provider: false` and `monitoring: false`
- Health check shows components as unhealthy

**Error:**
```json
{"status":"unhealthy","version":"1.0.0","components":{"api":true,"config":true,"ai_provider":false,"monitoring":false}}
```

**Cause:**  
Docker containers don't automatically read `.env` files from the host. When you run `docker run -e KEY=value`, those values override everything. The `.env` file only works for local Python development.

**Solution Option 1: Pass real keys via -e flags**
```bash
# Stop and remove old container
docker stop quantnik-anomaly-test
docker rm quantnik-anomaly-test

# Run with real API keys
docker run -d \
  --name quantnik-anomaly-test \
  -p 8080:8080 \
  -e MONITORING_ADAPTER=datadog \
  -e AI_PROVIDER=gemini \
  -e AI_API_KEY="YOUR_REAL_GEMINI_API_KEY" \
  -e MONITORING_API_KEY="YOUR_REAL_DATADOG_API_KEY" \
  -e MONITORING_APP_KEY="YOUR_REAL_DATADOG_APP_KEY" \
  -e K8S_IN_CLUSTER=false \
  -e DEBUG=true \
  quantnik-quantnik-anomaly:latest
```

**Solution Option 2: Use --env-file flag**
```bash
docker run -d \
  --name quantnik-anomaly-test \
  -p 8080:8080 \
  --env-file .env \
  quantnik-quantnik-anomaly:latest
```

### 2.2 Docker Permission Denied

**Error:**
```
Got permission denied while trying to connect to the Docker daemon socket
```

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# IMPORTANT: Logout and login again
exit
# Reconnect via SSH

# Verify
docker ps
```

### 2.3 Docker Build Fails

**Troubleshooting:**
```bash
# View detailed build logs
docker build -t quantnik-anomaly:latest . 2>&1 | tee build.log

# Check if Dockerfile exists
ls -la Dockerfile

# Check requirements.txt
cat requirements.txt
```

---

## 3. Kubernetes/EKS Issues

### 3.1 CreateContainerConfigError - runAsNonRoot with Non-Numeric User

**Error:**
```
Error: container has runAsNonRoot and image has non-numeric user (agent), cannot verify user is non-root
```

**Cause:**  
The EKS cluster has a Pod Security Policy or Security Context that requires `runAsNonRoot: true`. Kubernetes cannot verify that a named user (e.g., `agent`) is non-root - it requires a numeric UID for verification.

**Solution:**  
Update the Dockerfile to use a numeric UID instead of a username. This is a **security best practice**.

**Step 1: Update Dockerfile**
```dockerfile
# Create non-root user with explicit UID for security
# Using UID 10001 (non-privileged range) for Kubernetes runAsNonRoot compatibility
ARG APP_UID=10001
ARG APP_GID=10001

RUN groupadd --gid ${APP_GID} agent && \
    useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /bin/bash agent && \
    chown -R ${APP_UID}:${APP_GID} /app

# ... (rest of Dockerfile)

# Switch to non-root user using numeric UID (required for runAsNonRoot verification)
USER 10001
```

**Step 2: Rebuild and push image**
```bash
# Set version (increment from previous)
export VERSION="1.0.1"
export ECR_URI="145748108830.dkr.ecr.ap-south-1.amazonaws.com/quantnik-quantnik-anomaly"

# Rebuild
docker build -t quantnik-quantnik-anomaly:${VERSION} .

# Tag for ECR
docker tag quantnik-quantnik-anomaly:${VERSION} ${ECR_URI}:${VERSION}
docker tag quantnik-quantnik-anomaly:${VERSION} ${ECR_URI}:latest

# Login to ECR
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin 145748108830.dkr.ecr.ap-south-1.amazonaws.com

# Push
docker push ${ECR_URI}:${VERSION}
docker push ${ECR_URI}:latest
```

**Step 3: Update deployment and restart**
```bash
# Update image version in deployment.yaml
sed -i "s|quantnik-quantnik-anomaly:1.0.0|quantnik-quantnik-anomaly:${VERSION}|g" deploy/kubernetes/deployment.yaml

# Or manually edit to use new version
nano deploy/kubernetes/deployment.yaml

# Re-apply
kubectl apply -f deploy/kubernetes/deployment.yaml

# Watch pods
kubectl get pods -n quantnik-system -w
```

**Why UID 10001?**
- UIDs below 1000 are typically reserved for system users
- UID 10001 is in the non-privileged range
- Explicit numeric UID allows Kubernetes to verify non-root compliance
- This maintains security (container runs as non-root) while satisfying cluster policies

---

### 3.2 ErrImagePull / ImagePullBackOff

**Error:**
```
quantnik-anomaly-agent-xxx   0/1     ErrImagePull      0          31s
quantnik-anomaly-agent-xxx   0/1     ImagePullBackOff  0          59s
```

**Cause 1: Wrong image name in deployment.yaml**

The `sed` command may not have updated the image correctly.

**Diagnosis:**
```bash
# Check what image is in deployment.yaml
grep "image:" deploy/kubernetes/deployment.yaml

# If it still shows "wipro/quantnik-anomaly-agent:latest", the sed didn't work
```

**Solution:**
```bash
# Check your variables
echo "ECR_URI: $ECR_URI"
echo "VERSION: $VERSION"

# Manually edit deployment.yaml
nano deploy/kubernetes/deployment.yaml

# Find the line with "image:" and update it to your ECR image:
#   image: 145748108830.dkr.ecr.ap-south-1.amazonaws.com/quantnik-quantnik-anomaly:1.0.1

# Save and exit (Ctrl+X, Y, Enter)

# Delete and re-apply
kubectl delete deployment quantnik-anomaly-agent -n quantnik-system
kubectl apply -f deploy/kubernetes/deployment.yaml

# Watch pods
kubectl get pods -n quantnik-system -w
```

**Cause 2: EKS nodes can't pull from ECR**

The EKS worker nodes need IAM permissions to pull images from ECR.

**Diagnosis:**
```bash
# Describe the pod to see detailed error
kubectl describe pod -l app=quantnik-anomaly-agent -n quantnik-system | grep -A 10 "Events:"
```

**Solution:**
```bash
# Ensure the EKS node IAM role has ECR permissions
# The role needs: AmazonEC2ContainerRegistryReadOnly policy

# Or create an ECR pull secret (alternative)
kubectl create secret docker-registry ecr-secret \
  --docker-server=145748108830.dkr.ecr.ap-south-1.amazonaws.com \
  --docker-username=AWS \
  --docker-password=$(aws ecr get-login-password --region ap-south-1) \
  -n quantnik-system

# Then add to deployment.yaml under spec.template.spec:
#   imagePullSecrets:
#     - name: ecr-secret
```

### 3.2 Pod CrashLoopBackOff

**Error:**
```
quantnik-anomaly-agent-xxx   0/1     CrashLoopBackOff   5          5m
```

**Diagnosis:**
```bash
# Check pod logs
kubectl logs -l app=quantnik-anomaly-agent -n quantnik-system --tail=100

# Check previous container logs (if restarted)
kubectl logs -l app=quantnik-anomaly-agent -n quantnik-system --previous

# Describe pod for events
kubectl describe pod -l app=quantnik-anomaly-agent -n quantnik-system
```

**Common Causes:**
- Missing secrets (AI_API_KEY, etc.)
- Invalid configuration
- Application error on startup

**Solution:**
```bash
# Check if secrets exist
kubectl get secrets -n quantnik-system

# Check if configmap exists
kubectl get configmap quantnik-anomaly-config -n quantnik-system

# Recreate secrets if missing
kubectl create secret generic quantnik-anomaly-secrets \
    --namespace quantnik-system \
    --from-literal=ai_api_key="YOUR_KEY" \
    --from-literal=monitoring_api_key="YOUR_KEY" \
    --from-literal=monitoring_app_key="YOUR_KEY"
```

### 3.3 Namespace Not Found

**Error:**
```
Error from server (NotFound): namespaces "quantnik-system" not found
```

**Solution:**
```bash
kubectl create namespace quantnik-system
```

### 3.4 sed Command Not Updating File

**Problem:**  
The `sed -i "s|old|new|g" file` command doesn't update the file.

**Cause:**  
The pattern doesn't match exactly. Check for:
- Different image name (e.g., `quantnik-anomaly-agent` vs `quantnik-quantnik-anomaly`)
- Extra spaces
- Different tag

**Solution:**
```bash
# Check the actual content
grep "image:" deploy/kubernetes/deployment.yaml

# Use the exact pattern shown in the output
# Or manually edit the file
nano deploy/kubernetes/deployment.yaml
```

---

## 4. AWS ECR Issues

### 4.1 ECR Login Expired

**Error:**
```
denied: Your authorization token has expired. Reauthenticate and try again.
```

**Solution:**
```bash
# Re-login to ECR (token expires after 12 hours)
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin 145748108830.dkr.ecr.ap-south-1.amazonaws.com
```

### 4.2 Repository Not Found

**Error:**
```
name unknown: The repository with name 'xxx' does not exist
```

**Solution:**
```bash
# Create the repository
aws ecr create-repository \
    --repository-name quantnik-quantnik-anomaly \
    --region ap-south-1

# Verify
aws ecr describe-repositories --region ap-south-1
```

### 4.3 Push Access Denied

**Error:**
```
denied: User: arn:aws:iam::xxx is not authorized to perform: ecr:PutImage
```

**Solution:**
Ensure your IAM user/role has ECR permissions:
- `ecr:GetAuthorizationToken`
- `ecr:BatchCheckLayerAvailability`
- `ecr:GetDownloadUrlForLayer`
- `ecr:PutImage`
- `ecr:InitiateLayerUpload`
- `ecr:UploadLayerPart`
- `ecr:CompleteLayerUpload`

---

## 5. API/Application Issues

### 5.1 Health Check Shows Unhealthy

**Response:**
```json
{"status":"unhealthy","version":"1.0.0","components":{"api":true,"config":true,"ai_provider":false,"monitoring":false}}
```

**Cause:**  
AI provider or monitoring adapter can't connect (usually invalid API keys).

**Diagnosis:**
```bash
# Check container logs
docker logs quantnik-anomaly-test

# Look for errors like:
# HTTP/1.1 400 Bad Request (Gemini - invalid key)
# HTTP/1.1 403 Forbidden (Datadog - invalid key)
```

**Solution:**
1. Verify API keys are correct
2. Ensure keys are passed to container (see Section 2.1)
3. Check if API keys have proper permissions

### 5.2 Connection Refused on Port 8080

**Error:**
```
curl: (7) Failed to connect to localhost port 8080: Connection refused
```

**Diagnosis:**
```bash
# Check if container is running
docker ps

# Check if port is mapped
docker ps --format "table {{.Names}}\t{{.Ports}}"

# Check container logs
docker logs quantnik-anomaly-test
```

**Solution:**
```bash
# Ensure container is running with port mapping
docker run -d -p 8080:8080 ...
```

---

## 6. ALB/Ingress Issues

### 6.1 ALB Not Provisioning (ADDRESS Empty)

**Symptom:**
```bash
kubectl get ingress -n quantnik-system
NAME                 CLASS   HOSTS   ADDRESS   PORTS   AGE
quantnik-anomaly-agent   alb     *                 80      5m
```

**Cause 1: ALB Controller IAM Missing Permissions**

**Error in events:**
```
Failed deploy model due to failed to create listener rule: AccessDenied: User is not authorized to perform: elasticloadbalancing:AddTags
```

**Solution:**
Add this policy to the ALB Controller IAM role:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "elasticloadbalancing:RemoveTags",
                "elasticloadbalancing:DescribeTags",
                "elasticloadbalancing:AddTags"
            ],
            "Resource": "*"
        }
    ]
}
```

Then recreate the ingress:
```bash
kubectl delete ingress quantnik-anomaly-agent -n quantnik-system
kubectl apply -f deploy/kubernetes/ingress.yaml
```

**Cause 2: AWS Load Balancer Controller Not Installed**

**Diagnosis:**
```bash
kubectl get pods -n kube-system | grep aws-load-balancer
```

If no pods found, the controller needs to be installed.

### 6.2 ALB 504 Gateway Timeout

**Symptom:**
```bash
curl http://$ALB_URL/health
# Returns: 504 Gateway Time-out
```

**Cause 1: Target Group Health Check Failing**

**Diagnosis:**
- Go to AWS Console → EC2 → Target Groups
- Check if targets show "Unhealthy"

**Solution:**
The default health check path is `/` but the app uses `/health`. Add health check annotations to ingress:

```yaml
annotations:
  alb.ingress.kubernetes.io/healthcheck-path: /health
  alb.ingress.kubernetes.io/healthcheck-port: "8080"
```

**Cause 2: Security Group Blocking Traffic**

**Diagnosis:**
- ALB can reach targets but security group blocks port 8080

**Solution:**
Add inbound rule to EKS worker node security group:
```bash
# Find worker node security group
aws ec2 describe-security-groups \
    --filters "Name=tag:aws:eks:cluster-name,Values=YOUR_CLUSTER_NAME" \
    --query 'SecurityGroups[*].[GroupId,GroupName]' \
    --output table --region ap-south-1

# Add inbound rule (replace SG IDs)
aws ec2 authorize-security-group-ingress \
    --group-id WORKER_NODE_SG_ID \
    --protocol tcp \
    --port 8080 \
    --source-group ALB_SG_ID \
    --region ap-south-1
```

Or via AWS Console:
1. EC2 → Security Groups → Find EKS worker node SG
2. Edit inbound rules → Add:
   - Type: Custom TCP
   - Port: 8080
   - Source: ALB Security Group ID

### 6.3 ALB Targets Showing Unhealthy

**Symptom:**
AWS Console → Target Groups shows targets as "Unhealthy"

**Diagnosis:**
1. Check health check configuration in Target Group
2. Verify pods are running: `kubectl get pods -n quantnik-system`
3. Test health endpoint from within pod:
   ```bash
   kubectl exec -it $(kubectl get pod -l app=quantnik-anomaly-agent -n quantnik-system -o jsonpath='{.items[0].metadata.name}') -n quantnik-system -- curl -s http://localhost:8080/health
   ```

**Common Fixes:**
1. Update health check path from `/` to `/health`
2. Update health check port to `8080`
3. Add security group rule for port 8080

---

## 7. Harness CI/CD Issues

### 6.1 Pipeline Can't Clone Repository

**Cause:**  
Incorrect connector configuration for Harness Code Repository.

**Solution:**
1. Go to Harness → Project Settings → Connectors
2. Verify the Harness Code connector exists
3. Check the connector ID matches what's in the pipeline YAML

### 6.2 Build Stage Fails

**Diagnosis:**
- Check the step logs in Harness UI
- Look for dependency installation errors
- Verify Dockerfile is correct

### 6.3 Deploy Stage Fails

**Common Causes:**
- Kubernetes connector not configured
- Delegate doesn't have EKS access
- Service/Environment not created in Harness

---

## Quick Diagnostic Commands

```bash
# ===== Docker =====
docker ps                                    # List running containers
docker logs <container>                      # View container logs
docker inspect <container>                   # Detailed container info

# ===== Kubernetes =====
kubectl get pods -n quantnik-system              # List pods
kubectl logs -l app=quantnik-anomaly-agent -n quantnik-system   # Pod logs
kubectl describe pod <pod-name> -n quantnik-system          # Pod details
kubectl get events -n quantnik-system --sort-by='.lastTimestamp'  # Recent events

# ===== AWS =====
aws sts get-caller-identity                  # Verify AWS credentials
aws ecr describe-repositories --region ap-south-1       # List ECR repos
aws eks describe-cluster --name <cluster> --region ap-south-1  # EKS info

# ===== Network =====
curl http://localhost:8080/health            # Test health endpoint
curl http://localhost:8080/live              # Test liveness
curl http://localhost:8080/ready             # Test readiness
```

---

## Adding New Issues

When you encounter a new issue, add it to this document with:

1. **Error message** - The exact error you see
2. **Cause** - What caused the issue
3. **Diagnosis** - How to investigate
4. **Solution** - Step-by-step fix

---

**End of Troubleshooting Guide**
