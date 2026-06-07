#!/bin/bash
# Docker-based deployment script for BRD Summary Agent to GCP Cloud Run

set -e

# Configuration
PROJECT_ID="digital-rig-poc"
REGION="us-central1"
SERVICE_NAME="brd-summary-agent"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Environment variables (set these before running or pass as arguments)
# GOOGLE_CLOUD_API_KEY - Your Vertex AI API key
# CONFLUENCE_EMAIL - Your Confluence email
# CONFLUENCE_API_TOKEN - Your Confluence API token

echo "=========================================="
echo "Deploying BRD Summary Agent to GCP Cloud Run"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "=========================================="

# Step 1: Set project
echo "Step 1: Setting project..."
gcloud config set project $PROJECT_ID

# Step 2: Enable required APIs
echo "Step 2: Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage-api.googleapis.com

# Step 3: Build Docker image
echo "Step 3: Building Docker image..."
docker build -t ${IMAGE_NAME}:latest .

# Step 4: Configure Docker to use gcloud as credential helper
echo "Step 4: Configuring Docker authentication..."
gcloud auth configure-docker

# Step 5: Push image to Google Container Registry
echo "Step 5: Pushing image to GCR..."
docker push ${IMAGE_NAME}:latest

# Step 6: Check for required environment variables
if [ -z "$GOOGLE_CLOUD_API_KEY" ] || [ -z "$CONFLUENCE_EMAIL" ] || [ -z "$CONFLUENCE_API_TOKEN" ]; then
    echo ""
    echo "WARNING: Environment variables not set!"
    echo "Please set the following variables before deploying:"
    echo "  - GOOGLE_CLOUD_API_KEY"
    echo "  - CONFLUENCE_EMAIL"
    echo "  - CONFLUENCE_API_TOKEN"
    echo ""
    read -p "Do you want to continue and set them via Cloud Run Console later? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 1
    fi
    SKIP_ENV_VARS=true
fi

# Step 7: Deploy to Cloud Run
echo "Step 7: Deploying to Cloud Run..."
if [ "$SKIP_ENV_VARS" = true ]; then
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
        --min-instances 0
    
    echo ""
    echo "=========================================="
    echo "IMPORTANT: Set environment variables in Cloud Run Console!"
    echo "Go to: https://console.cloud.google.com/run/detail/${REGION}/${SERVICE_NAME}/variables"
    echo "Add these variables:"
    echo "  - GOOGLE_CLOUD_API_KEY"
    echo "  - CONFLUENCE_EMAIL"
    echo "  - CONFLUENCE_API_TOKEN"
    echo "=========================================="
else
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
        --set-env-vars="CONFLUENCE_API_TOKEN=${CONFLUENCE_API_TOKEN}" \
        --set-env-vars="PORT=8080"
fi

# Step 8: Get service URL
echo ""
echo "Step 8: Getting service URL..."
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --format 'value(status.url)')

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Test the deployment:"
echo "  Health Check: curl ${SERVICE_URL}/health"
echo ""
echo "  API Documentation: ${SERVICE_URL}/docs"
echo ""
echo "  Generate BRD Summary:"
echo "  curl -X POST ${SERVICE_URL}/v1/brdsummary \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"confluence_link\": \"your-confluence-url\"}'"
echo "=========================================="
