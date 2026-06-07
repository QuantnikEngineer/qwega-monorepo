#!/bin/bash
# Deployment script for Wega-Userstory-Validator to digital-rig-poc project

set -e

# Configuration
PROJECT_ID="digital-rig-poc"
ZONE="us-central1-a"
INSTANCE_NAME="wega-validator-instance"
MACHINE_TYPE="e2-medium"
SERVICE_ACCOUNT="204952354085-compute@developer.gserviceaccount.com"

echo "=========================================="
echo "Deploying Wega-Userstory-Validator to GCP"
echo "Project: $PROJECT_ID"
echo "Instance: $INSTANCE_NAME"
echo "=========================================="

# Step 1: Set project
echo "Step 1: Setting project..."
gcloud config set project $PROJECT_ID

# Step 2: Enable required APIs
echo "Step 2: Enabling required APIs..."
gcloud services enable compute.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage-api.googleapis.com

# Step 3: Grant IAM permissions to service account
echo "Step 3: Granting IAM permissions to service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/storage.objectViewer"

# Step 4: Create firewall rule for port 8080
echo "Step 4: Creating firewall rule..."
gcloud compute firewall-rules create allow-brd-agent-8080 \
    --project=$PROJECT_ID \
    --allow=tcp:8080 \
    --description="Allow BRD Agent API on port 8080" \
    --direction=INGRESS \
    --target-tags=brd-agent || echo "Firewall rule already exists"

# Step 5: Package application files
echo "Step 5: Packaging application files..."
cd "$(dirname "$0")"
tar -czf brd-agent-gcp.tar.gz server.py requirements.txt brd-agent.service

# Step 6: Create Compute Engine instance
echo "Step 6: Creating Compute Engine instance..."
gcloud compute instances create $INSTANCE_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --service-account=$SERVICE_ACCOUNT \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --image-family=debian-11 \
    --image-project=debian-cloud \
    --boot-disk-size=20GB \
    --boot-disk-type=pd-standard \
    --tags=brd-agent \
    --metadata-from-file=startup-script=startup-script.sh

# Step 7: Wait for instance to be ready
echo "Step 7: Waiting for instance to be ready..."
sleep 30

# Step 8: Copy application files to instance
echo "Step 8: Copying application files to instance..."
gcloud compute scp brd-agent-gcp.tar.gz $INSTANCE_NAME:/tmp/ --zone=$ZONE

# Step 9: SSH and setup application
echo "Step 9: Setting up application on instance..."
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="
    cd /tmp && \
    tar -xzf brd-agent-gcp.tar.gz && \
    sudo mkdir -p /opt/brd-agent-gcp && \
    sudo cp server.py requirements.txt brd-agent.service /opt/brd-agent-gcp/ && \
    cd /opt/brd-agent-gcp && \
    sudo python3 -m venv venv && \
    sudo /opt/brd-agent-gcp/venv/bin/pip install --upgrade pip && \
    sudo /opt/brd-agent-gcp/venv/bin/pip install -r requirements.txt && \
    sudo cp brd-agent.service /etc/systemd/system/ && \
    sudo systemctl daemon-reload && \
    sudo systemctl enable brd-agent && \
    sudo systemctl start brd-agent
"

# Step 10: Get instance IP
echo "Step 10: Getting instance external IP..."
EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
    --zone=$ZONE \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo "Instance Name: $INSTANCE_NAME"
echo "External IP: $EXTERNAL_IP"
echo "API Endpoint: http://$EXTERNAL_IP:8080"
echo ""
echo "Test the API:"
echo "  curl http://$EXTERNAL_IP:8080/health"
echo ""
echo "View logs:"
echo "  gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='sudo journalctl -u brd-agent -f'"
echo ""
echo "SSH into instance:"
echo "  gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo "=========================================="

# Cleanup
rm -f brd-agent-gcp.tar.gz

echo "Done!"
