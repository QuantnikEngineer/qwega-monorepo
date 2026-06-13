# Docker Deployment Guide for BRD Summary Agent

This guide explains how to deploy the BRD Summary Agent using Docker, both locally and on Google Cloud Platform (GCP).

## Table of Contents
- [Prerequisites](#prerequisites)
- [Local Development with Docker](#local-development-with-docker)
- [GCP Cloud Run Deployment](#gcp-cloud-run-deployment)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software
- Docker Desktop (v20.0+) - [Install Docker](https://docs.docker.com/get-docker/)
- Docker Compose (v2.0+) - Usually included with Docker Desktop
- Google Cloud SDK (gcloud CLI) - For GCP deployment

### Required Credentials
1. **Google Cloud API Key** for Vertex AI
   - Get from: https://console.cloud.google.com/apis/credentials
   
2. **Confluence API Token**
   - Generate at: https://id.atlassian.com/manage-profile/security/api-tokens
   
3. **Confluence Email** - Your Confluence account email

## Local Development with Docker

### Step 1: Clone and Setup

```bash
cd Quantnik-brd-summary-agent

# Create .env file from example
cp .env.example .env

# Edit .env file with your credentials
nano .env  # or use your preferred editor
```

### Step 2: Configure Environment Variables

Edit the `.env` file:

```bash
GOOGLE_CLOUD_API_KEY=your-actual-api-key
CONFLUENCE_EMAIL=your-email@company.com
CONFLUENCE_API_TOKEN=your-actual-token
PORT=8080
```

### Step 3: Build and Run with Docker Compose

```bash
# Build and start the container
docker-compose up --build

# Or run in detached mode
docker-compose up -d --build
```

The service will be available at: `http://localhost:8080`

### Step 4: Test Locally

```bash
# Health check
curl http://localhost:8080/health

# View API documentation
open http://localhost:8080/docs

# Test BRD summary generation
curl -X POST http://localhost:8080/v1/brdsummary \
  -H "Content-Type: application/json" \
  -d '{
    "confluence_link": "https://your-confluence.atlassian.net/wiki/pages/12345/BRD"
  }'
```

### Step 5: Stop the Container

```bash
# Stop and remove containers
docker-compose down

# Stop, remove containers, and remove volumes
docker-compose down -v
```

## Manual Docker Build (without Docker Compose)

```bash
# Build the image
docker build -t brd-summary-agent:latest .

# Run the container with environment variables
docker run -d \
  --name brd-summary-agent \
  -p 8080:8080 \
  -e GOOGLE_CLOUD_API_KEY="your-api-key" \
  -e CONFLUENCE_EMAIL="your-email@company.com" \
  -e CONFLUENCE_API_TOKEN="your-token" \
  brd-summary-agent:latest

# View logs
docker logs -f brd-summary-agent

# Stop and remove
docker stop brd-summary-agent
docker rm brd-summary-agent
```

## GCP Cloud Run Deployment

Cloud Run is a fully managed serverless platform that automatically scales your containerized application.

### Option 1: Automated Deployment Script

```bash
# Set environment variables
export GOOGLE_CLOUD_API_KEY="your-api-key"
export CONFLUENCE_EMAIL="your-email@company.com"
export CONFLUENCE_API_TOKEN="your-token"

# Make the script executable
chmod +x deploy-docker.sh

# Run the deployment
./deploy-docker.sh
```

The script will:
1. Configure your GCP project
2. Enable required APIs
3. Build the Docker image
4. Push to Google Container Registry
5. Deploy to Cloud Run
6. Configure environment variables
7. Display the service URL

### Option 2: Manual Cloud Run Deployment

#### Step 1: Authenticate and Configure

```bash
# Login to GCP
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com
```

#### Step 2: Build and Push Image

```bash
# Set variables
PROJECT_ID="your-gcp-project-id"
SERVICE_NAME="brd-summary-agent"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Build the image
docker build -t ${IMAGE_NAME}:latest .

# Configure Docker authentication
gcloud auth configure-docker

# Push to GCR
docker push ${IMAGE_NAME}:latest
```

#### Step 3: Deploy to Cloud Run

```bash
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars="GOOGLE_CLOUD_API_KEY=${GOOGLE_CLOUD_API_KEY}" \
  --set-env-vars="CONFLUENCE_EMAIL=${CONFLUENCE_EMAIL}" \
  --set-env-vars="CONFLUENCE_API_TOKEN=${CONFLUENCE_API_TOKEN}"
```

#### Step 4: Get Service URL

```bash
gcloud run services describe ${SERVICE_NAME} \
  --platform managed \
  --region ${REGION} \
  --format 'value(status.url)'
```

### Option 3: Deploy via GCP Console

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click **Create Service**
3. Select **Deploy one revision from an existing container image**
4. Choose your image from GCR: `gcr.io/PROJECT_ID/brd-summary-agent:latest`
5. Configure:
   - Service name: `brd-summary-agent`
   - Region: `us-central1`
   - CPU allocation: **CPU is always allocated**
   - Authentication: **Allow unauthenticated invocations**
   - Container port: `8080`
   - Memory: `2 GiB`
   - CPU: `2`
   - Maximum requests per container: `80`
   - Timeout: `300 seconds`
6. Click **Container, Variables & Secrets, Connections, Security**
7. Add environment variables:
   - `GOOGLE_CLOUD_API_KEY`
   - `CONFLUENCE_EMAIL`
   - `CONFLUENCE_API_TOKEN`
   - `PORT=8080`
8. Click **Create**

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_CLOUD_API_KEY` | Vertex AI API key | `AIza...` |
| `CONFLUENCE_EMAIL` | Confluence account email | `user@company.com` |
| `CONFLUENCE_API_TOKEN` | Confluence API token | `ATATT3xF...` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Application port | `8080` |
| `FLASK_ENV` | Flask environment | `production` |

### Setting Environment Variables in Cloud Run

#### Via gcloud CLI:
```bash
gcloud run services update brd-summary-agent \
  --region us-central1 \
  --set-env-vars="GOOGLE_CLOUD_API_KEY=your-key"
```

#### Via Console:
1. Go to Cloud Run service
2. Click **Edit & Deploy New Revision**
3. Go to **Variables & Secrets** tab
4. Add/Edit environment variables
5. Click **Deploy**

## Testing

### Local Testing

```bash
# Health check
curl http://localhost:8080/health

# API documentation (open in browser)
open http://localhost:8080/docs

# Generate BRD summary
curl -X POST http://localhost:8080/v1/brdsummary \
  -H "Content-Type: application/json" \
  -d '{
    "confluence_link": "https://your-confluence.atlassian.net/wiki/pages/12345/BRD",
    "query_text": "Focus on authentication requirements"
  }'
```

### Production Testing (Cloud Run)

```bash
# Replace SERVICE_URL with your Cloud Run URL
SERVICE_URL="https://brd-summary-agent-xxxxx-uc.a.run.app"

# Health check
curl ${SERVICE_URL}/health

# Generate BRD summary
curl -X POST ${SERVICE_URL}/v1/brdsummary \
  -H "Content-Type: application/json" \
  -d '{
    "confluence_link": "https://your-confluence.atlassian.net/wiki/pages/12345/BRD"
  }'
```

## Updating the Deployment

### Update Code and Redeploy

```bash
# Make your code changes, then rebuild and push
docker build -t gcr.io/${PROJECT_ID}/brd-summary-agent:latest .
docker push gcr.io/${PROJECT_ID}/brd-summary-agent:latest

# Deploy the new version
gcloud run deploy brd-summary-agent \
  --image gcr.io/${PROJECT_ID}/brd-summary-agent:latest \
  --region us-central1
```

Or simply run:
```bash
./deploy-docker.sh
```

## Monitoring and Logs

### View Logs

```bash
# Cloud Run logs
gcloud run logs read brd-summary-agent \
  --region us-central1 \
  --limit 50 \
  --format json

# Follow logs in real-time
gcloud run logs tail brd-summary-agent \
  --region us-central1
```

### View Metrics

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click on your service
3. View the **Metrics** tab for:
   - Request count
   - Request latency
   - Container CPU utilization
   - Container memory utilization
   - Billable container instance time

## Troubleshooting

### Common Issues

#### 1. Container Fails to Start

**Symptom**: Cloud Run shows "Container failed to start"

**Solution**: Check logs:
```bash
gcloud run logs read brd-summary-agent --region us-central1 --limit 100
```

Common causes:
- Missing environment variables
- Port configuration mismatch
- Application errors on startup

#### 2. Environment Variables Not Working

**Symptom**: API returns errors about missing credentials

**Solution**: Verify environment variables are set:
```bash
gcloud run services describe brd-summary-agent \
  --region us-central1 \
  --format yaml | grep -A 10 env:
```

#### 3. Image Push Fails

**Symptom**: Cannot push to GCR

**Solution**: 
```bash
# Reconfigure Docker authentication
gcloud auth configure-docker

# Ensure GCR API is enabled
gcloud services enable containerregistry.googleapis.com
```

#### 4. Memory or Timeout Issues

**Symptom**: Requests timing out or container killed

**Solution**: Increase resources:
```bash
gcloud run services update brd-summary-agent \
  --region us-central1 \
  --memory 4Gi \
  --timeout 600
```

#### 5. SSL/Certificate Errors with Confluence

**Symptom**: SSL certificate verification errors

**Note**: The application disables SSL verification for Confluence connections. If you need proper SSL verification, update the code to use valid certificates.

### Debug Container Locally

```bash
# Run container interactively
docker run -it --rm \
  -e GOOGLE_CLOUD_API_KEY="your-key" \
  -e CONFLUENCE_EMAIL="email" \
  -e CONFLUENCE_API_TOKEN="token" \
  -p 8080:8080 \
  brd-summary-agent:latest bash

# Inside container, test manually
python brd_analyzer.py
```

### Check Container Health

```bash
# Local Docker
docker ps
docker logs brd-summary-agent

# Cloud Run
gcloud run services describe brd-summary-agent \
  --region us-central1 \
  --format "get(status.conditions)"
```

## Cost Optimization

### Cloud Run Pricing Tips

1. **Set minimum instances to 0** (default) - Only pay when handling requests
2. **Configure max instances** - Limit concurrent containers to control costs
3. **Right-size resources** - Start with 2 GiB RAM, adjust based on usage
4. **Enable request-based auto-scaling** - Scales down to zero when idle

```bash
gcloud run services update brd-summary-agent \
  --region us-central1 \
  --min-instances 0 \
  --max-instances 5 \
  --memory 2Gi
```

## Security Best Practices

1. **Never commit .env files** - Already in .gitignore
2. **Use Secret Manager for sensitive data** (recommended for production):
   ```bash
   gcloud run services update brd-summary-agent \
     --region us-central1 \
     --set-secrets="GOOGLE_CLOUD_API_KEY=api-key:latest"
   ```
3. **Enable authentication** for production workloads
4. **Use IAM roles** instead of API keys when possible
5. **Regularly rotate API tokens**

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Docker Documentation](https://docs.docker.com/)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Confluence API Documentation](https://developer.atlassian.com/cloud/confluence/rest/v1/intro/)

## Support

For issues and questions, please check:
1. Application logs (see Monitoring section)
2. This troubleshooting guide
3. GCP Console for service status
