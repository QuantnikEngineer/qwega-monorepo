#!/bin/bash
# Startup script for Wega-Validator-GCP on Google Cloud Compute Engine

set -e

# Log output
exec > >(tee -a /var/log/startup-script.log)
exec 2>&1

echo "Starting Wega-Userstory-Validator setup..."

# Update system packages
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git

# Set application directory
APP_DIR="/opt/Wega-userstory-validator"
sudo mkdir -p $APP_DIR

# Download application files from Cloud Storage bucket
# Alternative: files can be uploaded via metadata or SCP
# Uncomment if storing code in Cloud Storage:
# gsutil cp -r gs://your-bucket/wega-validator-gcp/* $APP_DIR/

# For now, we'll assume files are copied manually
# Copy from tmp if available
if [ -d "/tmp/wega-validator-gcp" ]; then
    echo "Copying application files from /tmp..."
    sudo cp -r /tmp/wega-validator-gcp/* $APP_DIR/
fi

cd $APP_DIR

# Create Python virtual environment
echo "Creating Python virtual environment..."
sudo python3 -m venv venv
sudo chown -R root:root venv

# Activate virtual environment and install dependencies
echo "Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Load environment variables from .env file
if [ -f "$APP_DIR/.env" ]; then
    echo "Loading environment variables from .env file..."
    set -a
    source $APP_DIR/.env
    set +a
else
    echo "WARNING: .env file not found at $APP_DIR/.env"
    echo "Please create .env file with CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN, and GOOGLE_CLOUD_API_KEY"
fi

# Set default values for optional variables
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-digital-rig-poc}"
export PORT="${PORT:-8080}"

# Configure firewall for port 8080 (run once)
echo "Configuring firewall..."
gcloud compute firewall-rules describe allow-wega-validator-8080 --project=digital-rig-poc 2>/dev/null || \
gcloud compute firewall-rules create allow-wega-validator-8080 \
    --project=digital-rig-poc \
    --allow=tcp:8080 \
    --description="Allow Wega Validator API on port 8080" \
    --direction=INGRESS

# Install and start systemd service
echo "Setting up systemd service..."
if [ -f "$APP_DIR/Wega-userstory-validator.service" ]; then
    sudo cp $APP_DIR/Wega-userstory-validator.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable Wega-userstory-validator
    sudo systemctl start Wega-userstory-validator
    echo "Wega-Validator service started"
fi

echo "Wega-Userstory-Validator startup complete!"
echo "Check service status: sudo systemctl status Wega-userstory-validator"
echo "View logs: sudo journalctl -u Wega-userstory-validator -f"
