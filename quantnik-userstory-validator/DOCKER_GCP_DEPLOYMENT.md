# Docker Deployment Guide for GCP

This guide covers deploying the Quantnik Userstory Validator using Docker on Google Cloud Platform. It supports multiple deployment options: **Cloud Run** (recommended), **GKE**, and **Compute Engine**.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Local Development with Docker](#local-development-with-docker)
- [Deploy to Cloud Run](#deploy-to-cloud-run)
- [Deploy to GKE](#deploy-to-gke)
- [Deploy to Compute Engine](#deploy-to-compute-engine)
- [CI/CD with Cloud Build](#cicd-with-cloud-build)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

1. **Google Cloud SDK** installed and configured
   ```bash
   # Install gcloud CLI
   curl https://sdk.cloud.google.com | bash
   gcloud init
   ```

2. **Docker** installed locally
   ```bash
   # Verify Docker installation
   docker --version
   ```

3. **GCP Project** with billing enabled

4. **Required APIs** enabled:
   ```bash
   gcloud services enable \
       cloudbuild.googleapis.com \
       run.googleapis.com \
       artifactregistry.googleapis.com \
       aiplatform.googleapis.com \
       storage-api.googleapis.com
   ```

---

## Quick Start

### Build and Deploy to Cloud Run in 3 Steps

```bash
# 1. Set your project
export PROJECT_ID="your-project-id"
export REGION="us-central1"
gcloud config set project $PROJECT_ID

# 2. Build and push image using Cloud Build
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/quantnik-userstory-validator-repo/quantnik-userstory-validator

# 3. Deploy to Cloud Run
gcloud run deploy quantnik-userstory-validator \
    --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/quantnik-userstory-validator-repo/quantnik-userstory-validator \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated
```

---

## Local Development with Docker

### Build the Docker Image

```bash
# Build the image
docker build -t quantnik-userstory-validator:latest .

# Verify the image
docker images | grep quantnik-userstory-validator
```

### Run Locally

```bash
# Run with environment variables
docker run -p 8080:8080 \
    -e GOOGLE_CLOUD_API_KEY="your-api-key" \
    -e GOOGLE_CLOUD_PROJECT="your-project-id" \
    quantnik-userstory-validator:latest

# Or mount GCP credentials for local testing
docker run -p 8080:8080 \
    -v ~/.config/gcloud:/root/.config/gcloud:ro \
    -e GOOGLE_CLOUD_PROJECT="your-project-id" \
    quantnik-userstory-validator:latest
```

### Test the Application

```bash
# Health check
curl http://localhost:8080/health

# Home endpoint
curl http://localhost:8080/

# Test analysis (see POSTMAN_GUIDE.md for full examples)
curl -X POST http://localhost:8080/analyze \
    -H "Content-Type: application/json" \
    -d '{
        "query_text": "User login functionality",
        "us_document_uri": "gs://your-bucket/user-story.pdf",
        "brd_document_uri": "gs://your-bucket/brd-document.pdf"
    }'
```

---

## Deploy to Cloud Run

Cloud Run is the **recommended** deployment option for this application. It provides automatic scaling, pay-per-use pricing, and managed infrastructure.

### Step 1: Create Artifact Registry Repository

```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export REPO_NAME="quantnik-userstory-validator-repo"

# Create repository
gcloud artifacts repositories create ${REPO_NAME} \
    --repository-format=docker \
    --location=${REGION} \
    --description="Quantnik Userstory Validator Docker images"

# Configure Docker authentication
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

### Step 2: Build and Push Image

```bash
export IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/quantnik-userstory-validator"

# Option A: Build locally and push
docker build -t ${IMAGE_URI}:latest .
docker push ${IMAGE_URI}:latest

# Option B: Build using Cloud Build (recommended)
gcloud builds submit --tag ${IMAGE_URI}:latest
```

### Step 3: Create Service Account

```bash
# Create service account for Cloud Run
gcloud iam service-accounts create quantnik-validator-sa \
    --display-name="Quantnik Userstory Validator Service Account"

# Grant Vertex AI access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:quantnik-validator-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Grant Cloud Storage access
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:quantnik-validator-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

### Step 4: Deploy to Cloud Run

```bash
gcloud run deploy quantnik-userstory-validator \
    --image ${IMAGE_URI}:latest \
    --region ${REGION} \
    --platform managed \
    --service-account quantnik-validator-sa@${PROJECT_ID}.iam.gserviceaccount.com \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 10 \
    --allow-unauthenticated

# Get the service URL
gcloud run services describe quantnik-userstory-validator --region ${REGION} --format='value(status.url)'
```

### Cloud Run with Authentication (Recommended for Production)

```bash
# Deploy without public access
gcloud run deploy quantnik-userstory-validator \
    --image ${IMAGE_URI}:latest \
    --region ${REGION} \
    --platform managed \
    --service-account quantnik-validator-sa@${PROJECT_ID}.iam.gserviceaccount.com \
    --no-allow-unauthenticated

# Grant access to specific users/service accounts
gcloud run services add-iam-policy-binding quantnik-userstory-validator \
    --region ${REGION} \
    --member="user:developer@example.com" \
    --role="roles/run.invoker"
```

---

## Deploy to GKE

For workloads requiring more control or integration with existing Kubernetes infrastructure.

### Step 1: Create GKE Cluster

```bash
export CLUSTER_NAME="quantnik-validator-cluster"
export ZONE="us-central1-a"

gcloud container clusters create ${CLUSTER_NAME} \
    --zone ${ZONE} \
    --num-nodes 2 \
    --machine-type e2-medium \
    --enable-autoscaling \
    --min-nodes 1 \
    --max-nodes 5 \
    --workload-pool=${PROJECT_ID}.svc.id.goog

# Get credentials
gcloud container clusters get-credentials ${CLUSTER_NAME} --zone ${ZONE}
```

### Step 2: Create Kubernetes Deployment

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quantnik-userstory-validator
  labels:
    app: quantnik-userstory-validator
spec:
  replicas: 2
  selector:
    matchLabels:
      app: quantnik-userstory-validator
  template:
    metadata:
      labels:
        app: quantnik-userstory-validator
    spec:
      serviceAccountName: quantnik-validator-ksa
      containers:
        - name: quantnik-userstory-validator
          image: us-central1-docker.pkg.dev/PROJECT_ID/quantnik-userstory-validator-repo/quantnik-userstory-validator:latest
          ports:
            - containerPort: 8080
          env:
            - name: PORT
              value: "8080"
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: quantnik-validator-service
spec:
  type: LoadBalancer
  selector:
    app: quantnik-userstory-validator
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8080
```

### Step 3: Deploy to GKE

```bash
# Replace PROJECT_ID in the deployment file
sed -i "s/PROJECT_ID/${PROJECT_ID}/g" k8s/deployment.yaml

# Apply the deployment
kubectl apply -f k8s/deployment.yaml

# Check deployment status
kubectl get deployments
kubectl get pods
kubectl get services
```

---

## Deploy to Compute Engine

For traditional VM-based deployment using Docker.

### Step 1: Create VM with Container-Optimized OS

```bash
gcloud compute instances create-with-container quantnik-validator-vm \
    --zone ${ZONE} \
    --machine-type e2-medium \
    --container-image ${IMAGE_URI}:latest \
    --container-env PORT=8080 \
    --service-account quantnik-validator-sa@${PROJECT_ID}.iam.gserviceaccount.com \
    --scopes cloud-platform \
    --tags http-server

# Create firewall rule
gcloud compute firewall-rules create allow-quantnik-validator \
    --allow tcp:8080 \
    --target-tags http-server
```

---

## CI/CD with Cloud Build

The repository includes a `cloudbuild.yaml` for automated builds and deployments.

### Setup Cloud Build Trigger

```bash
# Connect your repository
gcloud builds triggers create github \
    --name="quantnik-validator-deploy" \
    --repo-name="Quantnik-userstory-validator" \
    --repo-owner="your-org" \
    --branch-pattern="^main$" \
    --build-config="cloudbuild.yaml" \
    --substitutions="_SERVICE_NAME=quantnik-userstory-validator,_REGION=us-central1"
```

### Grant Cloud Build Permissions

```bash
# Get Cloud Build service account
export CB_SA="$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')@cloudbuild.gserviceaccount.com"

# Grant Cloud Run Admin
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${CB_SA}" \
    --role="roles/run.admin"

# Grant Service Account User
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${CB_SA}" \
    --role="roles/iam.serviceAccountUser"
```

### Manual Build

```bash
# Submit build manually
gcloud builds submit --config cloudbuild.yaml \
    --substitutions=_SERVICE_NAME=quantnik-userstory-validator,_REGION=us-central1
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Port to listen on | `8080` |
| `GOOGLE_CLOUD_PROJECT` | GCP Project ID | Auto-detected |
| `GOOGLE_CLOUD_API_KEY` | API Key (optional with ADC) | - |

### Resource Recommendations

| Environment | CPU | Memory | Instances |
|-------------|-----|--------|-----------|
| Development | 0.5 | 512Mi | 1 |
| Staging | 1 | 1Gi | 1-3 |
| Production | 2 | 2Gi | 2-10 |

---

## Monitoring

### Cloud Run Metrics

```bash
# View service logs
gcloud run services logs read quantnik-userstory-validator --region ${REGION}

# Stream logs
gcloud run services logs tail quantnik-userstory-validator --region ${REGION}
```

### Set Up Alerts

```bash
# Create uptime check
gcloud monitoring uptime-checks create http quantnik-validator-uptime \
    --display-name="Quantnik Userstory Validator Health" \
    --uri="https://YOUR-CLOUD-RUN-URL/health"
```

---

## Troubleshooting

### Common Issues

**1. Image Build Fails**
```bash
# Check build logs
gcloud builds list --limit=5
gcloud builds log BUILD_ID
```

**2. Container Crashes on Start**
```bash
# Check Cloud Run logs
gcloud run services logs read quantnik-userstory-validator --region ${REGION} --limit=50
```

**3. Authentication Errors**
```bash
# Verify service account permissions
gcloud projects get-iam-policy ${PROJECT_ID} \
    --flatten="bindings[].members" \
    --filter="bindings.members:quantnik-validator-sa"
```

**4. Timeout Errors**
```bash
# Increase timeout (max 3600s for Cloud Run)
gcloud run services update quantnik-userstory-validator \
    --region ${REGION} \
    --timeout 600
```

### Health Check Commands

```bash
# Local Docker
docker exec -it CONTAINER_ID curl localhost:8080/health

# Cloud Run
curl https://YOUR-CLOUD-RUN-URL/health
```

---

## Cost Optimization

- Use **min-instances=0** for non-production to scale to zero
- Choose appropriate **CPU/memory** based on workload
- Enable **CPU allocation only during request processing** for Cloud Run
- Use **Artifact Registry cleanup policies** to remove old images

```bash
# Set CPU allocation on demand only
gcloud run services update quantnik-userstory-validator \
    --region ${REGION} \
    --no-cpu-always-allocated
```

---

## Security Best Practices

1. **Never embed secrets in images** - Use Secret Manager
2. **Use non-root user** - Dockerfile already configured
3. **Enable VPC connector** for private networking
4. **Require authentication** for production deployments
5. **Scan images** for vulnerabilities

```bash
# Enable vulnerability scanning
gcloud artifacts repositories update ${REPO_NAME} \
    --location ${REGION} \
    --cleanup-policy-dry-run=false
```
