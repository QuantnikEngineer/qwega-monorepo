# Deploy Quantnik-userstory-validator to digital-rig-poc Project

Complete guide to deploy the Quantnik-Userstory-Validator application to Google Cloud Compute Engine in the `digital-rig-poc` project.

## Prerequisites

1. `gcloud` CLI installed and authenticated
2. Access to `digital-rig-poc` project
3. Your local ADC credentials set up (already done at `/Users/pr20347584/.config/gcloud/application_default_credentials.json`)

## Quick Deploy (Automated)

The easiest way to deploy:

```bash
# Make the deploy script executable
chmod +x deploy.sh

# Run the deployment script
./deploy.sh
```

This script will:
- Set up the GCP project
- Enable required APIs
- Grant IAM permissions
- Create firewall rules
- Create and configure the Compute Engine instance
- Install and start the application

## Manual Deployment Steps

If you prefer to deploy manually:

### Step 1: Set Up Project

```bash
export PROJECT_ID="digital-rig-poc"
export ZONE="us-central1-a"
export INSTANCE_NAME="quantnik-validator-instance"

gcloud config set project $PROJECT_ID
```

### Step 2: Enable APIs

```bash
gcloud services enable compute.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable storage-api.googleapis.com
```

### Step 3: Configure Service Account Permissions

The Compute Engine default service account needs these permissions:

```bash
# Grant Vertex AI access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:204952354085-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"

# Grant Cloud Storage access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:204952354085-compute@developer.gserviceaccount.com" \
    --role="roles/storage.objectViewer"
```

### Step 4: Create Firewall Rule

```bash
gcloud compute firewall-rules create allow-quantnik-validator-8080 \
    --project=$PROJECT_ID \
    --allow=tcp:8080 \
    --description="Allow Quantnik Userstory Validator API on port 8080" \
    --direction=INGRESS \
    --target-tags=quantnik-validator
```

### Step 5: Create Compute Engine Instance

```bash
gcloud compute instances create $INSTANCE_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=e2-medium \
    --service-account=204952354085-compute@developer.gserviceaccount.com \
    --scopes=https://www.googleapis.com/auth/cloud-platform \
    --image-family=debian-11 \
    --image-project=debian-cloud \
    --boot-disk-size=20GB \
    --tags=brd-agent
```

### Step 6: Package and Upload Application

```bash
# Package application files
tar -czf Quantnik-userstory-validator.tar.gz server.py requirements.txt Quantnik-userstory-validator.service

# Copy to instance
gcloud compute scp Quantnik-userstory-validator.tar.gz $INSTANCE_NAME:/tmp/ --zone=$ZONE
```

### Step 7: Install Application on Instance

```bash
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE
```

Once connected, run:

```bash
# Extract files
cd /tmp
tar -xzf Quantnik-userstory-validator.tar.gz

# Create application directory
sudo mkdir -p /opt/Quantnik-userstory-validator
sudo cp server.py requirements.txt Quantnik-userstory-validator.service /opt/Quantnik-userstory-validator/
cd /opt/Quantnik-userstory-validator

# Create virtual environment
sudo python3 -m venv venv

# Install dependencies
sudo /opt/Quantnik-userstory-validator/venv/bin/pip install --upgrade pip
sudo /opt/Quantnik-userstory-validator/venv/bin/pip install -r requirements.txt

# Set up systemd service
sudo cp Quantnik-userstory-validator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable Quantnik-userstory-validator
sudo systemctl start Quantnik-userstory-validator

# Check status
sudo systemctl status brd-agent
```

### Step 8: Get Instance IP and Test

```bash
# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
    --zone=$ZONE \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "API Endpoint: http://$EXTERNAL_IP:8080"

# Test health endpoint
curl http://$EXTERNAL_IP:8080/health

# Test query endpoint
curl -X POST http://$EXTERNAL_IP:8080/query \
    -H "Content-Type: application/json" \
    -d '{"question": "What are the Internet Banking features?"}'
```

## Authentication: How ADC Works on Compute Engine

**Important:** You don't need to copy your local ADC credentials file to the Compute Engine instance!

### How Authentication Works:

1. **Locally (Development):**
   - Your app uses: `/Users/pr20347584/.config/gcloud/application_default_credentials.json`
   - Set up with: `gcloud auth application-default login`

2. **On Compute Engine (Production):**
   - The instance automatically gets credentials from the **metadata server**
   - Uses the **service account** attached to the instance
   - No credentials file needed!
   - The Python library automatically detects it's running on GCP

### The Service Account

The Compute Engine instance uses this service account:
```
204952354085-compute@developer.gserviceaccount.com
```

This service account has been granted:
- `roles/aiplatform.user` - Access Vertex AI APIs
- `roles/storage.objectViewer` - Read files from Cloud Storage

### Why This Works

When your Flask app runs on the Compute Engine instance:

```python
client = genai.Client(vertexai=True)
```

The Google Auth library automatically:
1. Detects it's running on GCP
2. Fetches credentials from the instance metadata server
3. Uses the attached service account
4. Authenticates all API calls

**No credential files needed!** ✨

## Alternative: Use Your Local Credentials (Not Recommended)

If you really want to use your local ADC file on the instance:

```bash
# Copy your ADC file to the instance
gcloud compute scp ~/.config/gcloud/application_default_credentials.json \
    $INSTANCE_NAME:/tmp/ --zone=$ZONE

# SSH into instance
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE

# Move file and set permissions
sudo mkdir -p /opt/credentials
sudo mv /tmp/application_default_credentials.json /opt/credentials/
sudo chmod 600 /opt/credentials/application_default_credentials.json

# Update the service file
sudo nano /etc/systemd/system/brd-agent.service

# Add this line under [Service]:
Environment="GOOGLE_APPLICATION_CREDENTIALS=/opt/credentials/application_default_credentials.json"

# Restart service
sudo systemctl daemon-reload
sudo systemctl restart brd-agent
```

**⚠️ Warning:** This approach is NOT recommended because:
- Security risk (your personal credentials on a server)
- Credentials may expire
- Harder to manage and rotate
- Violates principle of least privilege

## Monitoring and Management

### View Logs

```bash
# View service logs
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE \
    --command="sudo journalctl -u brd-agent -f"

# View startup script logs
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE \
    --command="sudo cat /var/log/startup-script.log"
```

### Restart Service

```bash
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE \
    --command="sudo systemctl restart brd-agent"
```

### Check Service Status

```bash
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE \
    --command="sudo systemctl status brd-agent"
```

### Stop/Start Instance

```bash
# Stop instance
gcloud compute instances stop $INSTANCE_NAME --zone=$ZONE

# Start instance
gcloud compute instances start $INSTANCE_NAME --zone=$ZONE
```

### Update Application

```bash
# Package new version
tar -czf brd-agent-gcp.tar.gz server.py requirements.txt brd-agent.service

# Copy to instance
gcloud compute scp brd-agent-gcp.tar.gz $INSTANCE_NAME:/tmp/ --zone=$ZONE

# SSH and update
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="
    cd /tmp && \
    tar -xzf brd-agent-gcp.tar.gz && \
    sudo cp server.py requirements.txt /opt/brd-agent-gcp/ && \
    sudo systemctl restart brd-agent
"
```

## Testing the Deployed API

### Using curl

```bash
# Get instance IP
EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
    --zone=$ZONE \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

# Health check
curl http://$EXTERNAL_IP:8080/health

# Query the BRD
curl -X POST http://$EXTERNAL_IP:8080/query \
    -H "Content-Type: application/json" \
    -d '{
        "question": "What are the Internet Banking features?"
    }'

# With custom document
curl -X POST http://$EXTERNAL_IP:8080/query \
    -H "Content-Type: application/json" \
    -d '{
        "question": "What are the security requirements?",
        "document_uri": "gs://digital-rig-poc-gemini-document/YOUR_DOCUMENT.pdf"
    }'
```

### Using Postman

Update your Postman environment:
- Variable: `base_url`
- Value: `http://EXTERNAL_IP:8080`

Then use your existing Postman collection!

## Troubleshooting

### Check if service is running

```bash
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE \
    --command="sudo systemctl status brd-agent"
```

### View detailed logs

```bash
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE \
    --command="sudo journalctl -u brd-agent -n 100 --no-pager"
```

### Test authentication

```bash
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="
    sudo -i
    export GOOGLE_APPLICATION_CREDENTIALS=
    cd /opt/brd-agent-gcp
    source venv/bin/activate
    python -c 'from google.auth import default; creds, project = default(); print(f\"Project: {project}\"); print(f\"Credentials: {type(creds)}\")'
"
```

### Check network connectivity

```bash
# Test if port 8080 is open
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE \
    --command="sudo netstat -tlnp | grep 8080"

# Test locally on instance
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE \
    --command="curl http://localhost:8080/health"
```

### Common Issues

1. **Authentication Error:**
   - Verify service account has proper IAM roles
   - Check: `gcloud projects get-iam-policy digital-rig-poc`

2. **Connection Refused:**
   - Check firewall rules
   - Verify service is running
   - Check port 8080 is listening

3. **Document Access Error:**
   - Verify service account has `storage.objectViewer` role
   - Check document URI uses `gs://` format
   - Verify bucket permissions

## Cost Optimization

```bash
# Use smaller instance for testing
--machine-type=e2-micro

# Use preemptible instance (cheaper)
--preemptible

# Stop instance when not in use
gcloud compute instances stop $INSTANCE_NAME --zone=$ZONE
```

## Cleanup

To delete all resources:

```bash
# Delete instance
gcloud compute instances delete $INSTANCE_NAME --zone=$ZONE

# Delete firewall rule
gcloud compute firewall-rules delete allow-brd-agent-8080

# Revoke IAM permissions (if needed)
gcloud projects remove-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:204952354085-compute@developer.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

## Next Steps

1. Set up **Cloud Load Balancer** for high availability
2. Use **Managed Instance Groups** for auto-scaling
3. Implement **Cloud Monitoring** and alerts
4. Add **authentication** (API keys, OAuth)
5. Use **Secret Manager** for sensitive configuration
6. Set up **CI/CD** with Cloud Build

## Summary

✅ **Recommended Approach (What we deployed):**
- Compute Engine instance with attached service account
- Service account has proper IAM roles
- Application uses automatic ADC from metadata server
- No credential files needed
- Secure and follows GCP best practices

❌ **Not Recommended:**
- Copying your local ADC credentials to the instance
- Using personal credentials on servers
- Manual credential management

Your BRD-Agent-GCP is now deployed and using proper GCP authentication! 🚀
