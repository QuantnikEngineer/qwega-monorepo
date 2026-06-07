# BRD Summary Agent

An intelligent API service that generates comprehensive summaries of Business Requirements Documents (BRDs) from Confluence pages using Google's Vertex AI (Gemini).

## Overview

This Flask-based API reads Business Requirements Documents from Confluence pages and uses Google's Gemini AI model to generate comprehensive, structured summaries of 500-700 words. The summaries capture all critical business requirements, objectives, stakeholders, functional and non-functional requirements, and other important aspects of the BRD.

## Quick Start with Docker 🐳

The fastest way to get started:

```bash
# 1. Create .env file with your credentials
cp .env.example .env
# Edit .env with your actual credentials

# 2. Run with Docker Compose
docker-compose up -d

# 3. Test the service
curl http://localhost:8080/health
```

For GCP Cloud Run deployment:
```bash
chmod +x deploy-docker.sh
./deploy-docker.sh
```

📖 **Full Docker Guide**: See [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md) for comprehensive Docker and Cloud Run deployment instructions.

## Features

- **Confluence Integration**: Directly reads BRD content from Confluence pages
- **AI-Powered Summarization**: Uses Gemini 3 Pro to generate intelligent summaries
- **Comprehensive Coverage**: Captures all critical aspects of BRDs including:
  - Business objectives and goals
  - Key stakeholders
  - Functional and non-functional requirements
  - Technical constraints and dependencies
  - Business rules and validation requirements
  - Integration requirements
  - Success criteria and risks
- **RESTful API**: Easy-to-use REST endpoints
- **Swagger Documentation**: Interactive API documentation at `/docs`
- **GCP Ready**: Designed for deployment on Google Cloud Platform

## Prerequisites

- Python 3.10+
- Google Cloud Platform account with Vertex AI enabled
- Confluence account with API access
- Required environment variables (see below)

## Environment Variables

Set the following environment variables before running the application:

```bash
# Google Cloud Configuration
export GOOGLE_CLOUD_API_KEY="your-vertex-ai-api-key"

# Confluence Configuration
export CONFLUENCE_EMAIL="your-email@company.com"
export CONFLUENCE_API_TOKEN="your-confluence-api-token"

# Optional
export PORT=8080  # Default: 8080
```

### Getting Confluence API Token

1. Log in to Confluence
2. Go to Account Settings → Security → API tokens
3. Create a new API token
4. Copy the token and set it as `CONFLUENCE_API_TOKEN`

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Wega-brd-summary-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set environment variables (see above)

4. Run the application:
```bash
python brd_analyzer.py
```

Or using Gunicorn:
```bash
gunicorn brd_analyzer:app --bind 0.0.0.0:8080 --timeout 300
```

## API Usage

### Generate BRD Summary

**Endpoint:** `POST /v1/brdsummary`

**Request Body:**
```json
{
  "confluence_link": "https://your-confluence.atlassian.net/wiki/spaces/SPACE/pages/12345/BRD-Page",
  "query_text": "Focus on authentication and security requirements"
}
```

**Parameters:**
- `confluence_link` (required): URL of the Confluence page containing the BRD
- `query_text` (optional): Additional context or specific aspects to focus on in the summary

**Response:**
```json
{
  "status": "success",
  "message": "BRD summary generated successfully",
  "summary": "Comprehensive 500-700 word summary of the BRD...",
  "confluence_link": "https://your-confluence.atlassian.net/wiki/spaces/SPACE/pages/12345/BRD-Page"
}
```

### Health Check

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "service": "BRD Summary Agent"
}
```

### API Documentation

Access interactive Swagger documentation at: `http://localhost:8080/docs`

## Deployment Options

### Option 1: Docker + Cloud Run (Recommended) 🐳

**Benefits**: Containerized, scalable, fully managed, auto-scaling

```bash
# Quick deployment with environment variables
export GOOGLE_CLOUD_API_KEY="your-api-key"
export CONFLUENCE_EMAIL="your-email@company.com"
export CONFLUENCE_API_TOKEN="your-token"

chmod +x deploy-docker.sh
./deploy-docker.sh
```

See [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md) for complete Docker deployment guide.

### Option 2: Traditional VM Deployment

For Compute Engine or VM-based deployment, see:
- [DEPLOYMENT.md](DEPLOYMENT.md) - General deployment guide
- [DEPLOY_DIGITAL_RIG.md](DEPLOY_DIGITAL_RIG.md) - Digital Rig specific deployment

### Local Development

```bash
# Without Docker
python brd_analyzer.py

# With Docker
docker-compose up
```

## Example Usage with cURL

```bash
curl -X POST http://localhost:8080/v1/brdsummary \
  -H "Content-Type: application/json" \
  -d '{
    "confluence_link": "https://your-confluence.atlassian.net/wiki/spaces/SPACE/pages/12345/BRD",
    "query_text": "Focus on user authentication requirements"
  }'
```

## Architecture

```
┌─────────────────┐
│  Confluence     │
│  BRD Page       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Flask API      │
│  (brd_analyzer) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Vertex AI      │
│  (Gemini 3 Pro) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AI-Generated   │
│  Summary        │
└─────────────────┘
```

## Technology Stack

- **Framework**: Flask 3.0+
- **AI Model**: Google Vertex AI (Gemini 3 Pro Preview)
- **Documentation**: Flasgger (Swagger UI)
- **Production Server**: Gunicorn
- **Integration**: Confluence REST API

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure all dependencies are installed: `pip install -r requirements.txt`
2. **Authentication errors**: Verify environment variables are set correctly
3. **Confluence access errors**: Check API token permissions and URL format
4. **Vertex AI errors**: Ensure GCP project has Vertex AI enabled and proper IAM roles

### Logs

The application uses Python's logging module. Logs include:
- Request/response details
- Confluence fetching status
- Gemini API interactions
- Error stack traces

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Specify your license here]

## Support

For issues and questions, please contact the BRD Summary Team.