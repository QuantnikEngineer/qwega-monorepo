# Deploying BRD-Agent-GCP to Google Cloud Compute Engine

This guide walks you through deploying the BRD-Agent-GCP application on a Google Cloud Compute Engine instance.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and configured (`gcloud init`)
3. **Required APIs** enabled:
   - Compute Engine API
   - Vertex AI API
   - Cloud Storage API

## Deployment Steps

### 1. Enable Required APIs

```bash
gcloud services enable compute.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage-api.googleapis.com
```

### 2. Set Environment Variables

```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export ZONE="us-central1-a"
export INSTANCE_NAME="brd-agent-instance"
export MACHINE_TYPE="e2-medium"  # Adjust based on needs

gcloud config set project $PROJECT_ID
```

### 3. Create a Service Account (Recommended)

```bash
# Create service account
gcloud iam service-accounts create brd-agent-sa \
    --display-name="BRD Agent Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:brd-agent-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:brd-agent-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

### 4. Create Compute Engine Instance

#### Option A: Using gcloud CLI (Recommended)

```bash
gcloud compute instances create $INSTANCE_NAME \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
    --service-account=brd-agent-sa@$PROJECT_ID.iam.gserviceaccount.com \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --image-family=debian-11 \
    --image-project=debian-cloud \
    --boot-disk-size=20GB \
    --boot-disk-type=pd-standard \
    --metadata-from-file=startup-script=startup-script.sh \
    --tags=http-server,https-server
```

#### Option B: Using Google Cloud Console

1. Go to **Compute Engine > VM instances**
2. Click **Create Instance**
3. Configure:
   - **Name**: `brd-agent-instance`
   - **Region**: `us-central1`
   - **Zone**: `us-central1-a`
   - **Machine type**: `e2-medium` (or higher)
   - **Boot disk**: Debian 11
4. Under **Identity and API access**:
   - Select the service account: `brd-agent-sa@...`
   - Access scopes: "Allow full access to all Cloud APIs"
5. Under **Management > Automation**:
   - Paste contents of `startup-script.sh` into "Startup script"
6. Click **Create**

### 5. Upload Application Files

After the instance is created, upload your application files:

```bash
# Create a tarball of your application
tar -czf brd-agent-gcp.tar.gz server.py requirements.txt brd-agent.service

# Copy to the instance
gcloud compute scp brd-agent-gcp.tar.gz $INSTANCE_NAME:/tmp/ --zone=$ZONE

# SSH into the instance
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE
```

### 6. Install and Configure on the Instance

Once SSH'd into the instance:

```bash
# Extract the application files
cd /tmp
tar -xzf brd-agent-gcp.tar.gz

# Create application directory
sudo mkdir -p /opt/brd-agent-gcp
sudo cp server.py requirements.txt /opt/brd-agent-gcp/
cd /opt/brd-agent-gcp

# Create virtual environment
sudo python3 -m venv venv
sudo chown -R $USER:$USER venv

# Install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Test the application
python server.py
```

### 7. Set Up as a System Service (Optional)

To run the application as a background service:

```bash
# Copy service file
sudo cp /tmp/brd-agent.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start the service
sudo systemctl enable brd-agent
sudo systemctl start brd-agent

# Check status
sudo systemctl status brd-agent

# View logs
sudo journalctl -u brd-agent -f
```

## Configuration

### Authentication

The application uses **Application Default Credentials (ADC)**, which are automatically available on Compute Engine instances with the proper service account.

Ensure your service account has:
- `roles/aiplatform.user` - For Vertex AI API access
- `roles/storage.objectViewer` - For Cloud Storage access

### Environment Variables

If you need to set additional environment variables, edit the service file:

```bash
sudo nano /etc/systemd/system/brd-agent.service
```

Add under `[Service]`:
```ini
Environment="GOOGLE_CLOUD_PROJECT=your-project-id"
Environment="CUSTOM_VAR=value"
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart brd-agent
```

## Monitoring and Maintenance

### View Logs

```bash
# System service logs
sudo journalctl -u brd-agent -f

# Startup script logs
sudo journalctl -u google-startup-scripts.service
```

### SSH Access

```bash
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE
```

### Stop/Start Instance

```bash
# Stop
gcloud compute instances stop $INSTANCE_NAME --zone=$ZONE

# Start
gcloud compute instances start $INSTANCE_NAME --zone=$ZONE
```

### Delete Instance

```bash
gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE
```

## Firewall Rules (If Running a Web Server)

If you modify the application to expose HTTP/HTTPS endpoints:

```bash
# Allow HTTP traffic
gcloud compute firewall-rules create allow-http \
    --allow tcp:80 \
    --target-tags http-server \
    --description="Allow HTTP traffic"

# Allow HTTPS traffic
gcloud compute firewall-rules create allow-https \
    --allow tcp:443 \
    --target-tags https-server \
    --description="Allow HTTPS traffic"
```

## Cost Optimization

- Use **e2-micro** or **e2-small** for development/testing
- Use **preemptible instances** for non-critical workloads
- Set up **auto-shutdown** when not in use:
  ```bash
  gcloud compute instances add-metadata $INSTANCE_NAME \
      --zone=$ZONE \
      --metadata=shutdown-script='#!/bin/bash
      echo "Instance shutting down"'
  ```

## Troubleshooting

### Check Instance Status
```bash
gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE
```

### View Serial Console Output
```bash
gcloud compute instances get-serial-port-output $INSTANCE_NAME --zone=$ZONE
```

### Common Issues

1. **Authentication Error**: Ensure service account has proper roles
2. **API Not Enabled**: Enable required APIs in Cloud Console
3. **Network Issues**: Check firewall rules and VPC settings
4. **Out of Memory**: Increase machine type size

## Next Steps

1. Consider using **Cloud Run** for serverless deployment
2. Set up **Cloud Monitoring** for alerts and metrics
3. Use **Secret Manager** for sensitive configuration
4. Implement **Cloud Load Balancer** for high availability
5. Set up **CI/CD pipeline** with Cloud Build

## Additional Resources

- [Compute Engine Documentation](https://cloud.google.com/compute/docs)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)
