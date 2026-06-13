# Quantnik Userstory Validator

A Flask-based AI-powered Business Requirements Document (BRD) analyzer that uses Google's Vertex AI (Gemini) to compare user stories against BRD documents and identify gaps, missing requirements, and provide recommendations.

## Features

- **Document Analysis**: Compares user stories against BRD documents using Gemini AI
- **Gap Detection**: Identifies missing requirements and content gaps
- **Recommendations**: Provides actionable recommendations for user story improvements
- **REST API**: Simple HTTP endpoints for integration
- **Docker Support**: Containerized for easy deployment on GCP
- **Multiple Deployment Options**: Cloud Run, GKE, or Compute Engine

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Client/API     │────▶│  Quantnik Userstory  │────▶│   Vertex AI      │
│   Consumer       │     │  Validator       │     │   (Gemini)       │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                 │
                                 ▼
                         ┌──────────────────┐
                         │  Cloud Storage   │
                         │  (PDF Documents) │
                         └──────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Google Cloud Project with Vertex AI enabled
- Docker (for containerized deployment)

### Local Development

```bash
# Clone the repository
git clone https://github.com/your-org/Quantnik-userstory-validator.git
cd Quantnik-userstory-validator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_API_KEY="your-api-key"  # Optional with ADC

# Run the server
python server.py
```

### Docker Deployment

```bash
# Build the image
docker build -t quantnik-userstory-validator:latest .

# Run the container
docker run -p 8080:8080 \
    -e GOOGLE_CLOUD_PROJECT="your-project-id" \
    quantnik-userstory-validator:latest
```

### Deploy to Cloud Run (Quick)

```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"

# Build and deploy in one command
gcloud run deploy quantnik-userstory-validator \
    --source . \
    --region ${REGION} \
    --allow-unauthenticated
```

## API Endpoints

### Health Check
```http
GET /health
```
**Response:**
```json
{
  "status": "healthy",
  "service": "Quantnik Userstory Validator"
}
```

### Home
```http
GET /
```
**Response:**
```json
{
  "service": "Quantnik Userstory Validator",
  "version": "1.0",
  "endpoints": {
    "/": "Home - this page",
    "/health": "Health check",
    "/analyze": "POST - Analyze BRD documents"
  }
}
```

### Analyze Documents
```http
POST /analyze
Content-Type: application/json

{
  "query_text": "User authentication with OAuth 2.0",
  "us_document_uri": "gs://your-bucket/user-story.pdf",
  "brd_document_uri": "gs://your-bucket/brd-document.pdf"
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query_text` | string | Yes | The user story or feature to analyze |
| `us_document_uri` | string | Yes | GCS URI of the user story document (gs://) |
| `brd_document_uri` | string | Yes | GCS URI of the BRD document (gs://) |

**Response:**
```json
{
  "status": "success",
  "message": "Analysis completed",
  "result": "Detailed analysis with covered requirements, gaps, and recommendations..."
}
```

## Project Structure

```
Quantnik-userstory-validator/
├── server.py                  # Main Flask application
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker configuration
├── .dockerignore             # Docker ignore file
├── cloudbuild.yaml           # Cloud Build CI/CD config
├── README.md                 # This file
├── DEPLOYMENT.md             # Compute Engine deployment guide
├── DOCKER_GCP_DEPLOYMENT.md  # Docker/Cloud Run deployment guide
├── POSTMAN_GUIDE.md          # API testing guide
├── deploy.sh                 # Deployment script
├── startup-script.sh         # VM startup script
├── Quantnik-userstory-validator.service # Systemd service file
└── Procfile                  # Heroku/process config
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `8080` |
| `GOOGLE_CLOUD_PROJECT` | GCP Project ID | Auto-detected |
| `GOOGLE_CLOUD_API_KEY` | Vertex AI API Key | - |

### Document Requirements

- Documents must be stored in Google Cloud Storage
- Use `gs://` URIs (not HTTPS URLs)
- Supported format: PDF
- Service account must have `storage.objectViewer` role

## Deployment Options

| Option | Best For | Guide |
|--------|----------|-------|
| **Cloud Run** | Serverless, auto-scaling | [DOCKER_GCP_DEPLOYMENT.md](DOCKER_GCP_DEPLOYMENT.md#deploy-to-cloud-run) |
| **GKE** | Kubernetes, complex orchestration | [DOCKER_GCP_DEPLOYMENT.md](DOCKER_GCP_DEPLOYMENT.md#deploy-to-gke) |
| **Compute Engine** | Traditional VMs | [DEPLOYMENT.md](DEPLOYMENT.md) |

## Development

### Running Tests

```bash
# Run with hot reload
python server.py

# Or with Flask debug mode
FLASK_DEBUG=1 python server.py
```

### Building Docker Image

```bash
# Build
docker build -t quantnik-userstory-validator:latest .

# Test locally
docker run -p 8080:8080 quantnik-userstory-validator:latest

# Verify
curl http://localhost:8080/health
```

## Monitoring & Logging

The application uses Python's logging module with INFO level by default. Logs include:
- Request/response details
- Document processing status
- Vertex AI API calls
- Error tracking with stack traces

### View Logs (Cloud Run)

```bash
gcloud run services logs read quantnik-userstory-validator --region us-central1
```

## Security

- Non-root Docker user
- No secrets in container images
- Service account-based authentication
- Configurable authentication (Cloud Run IAM)

## License

[Your License Here]

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions, please open a GitHub issue.
