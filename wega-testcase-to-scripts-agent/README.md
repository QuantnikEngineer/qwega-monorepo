# Test Cases to Test Scripts Agent

An intelligent AI-powered service that converts test cases into automation test scripts. Supports multiple frameworks (TestNG, BDD, Playwright, Selenium) and programming languages (Java, Python, JavaScript, TypeScript, C#) with both Greenfield and Brownfield generation approaches.

## 📋 Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Local Development](#local-development)
- [API Usage](#api-usage)
- [Docker Deployment](#docker-deployment)
- [GCP Cloud Run Deployment](#gcp-cloud-run-deployment)
- [API Endpoints](#api-endpoints)
- [Testing with Postman](#testing-with-postman)
- [Project Structure](#project-structure)

## ✨ Features

- **Multiple Frameworks Support**: Selenium TestNG, Selenium BDD/Cucumber, Playwright
- **Multi-Language**: Java, Python, JavaScript, TypeScript, C#
- **Generation Approaches**: Greenfield (new projects) and Brownfield (existing projects)
- **FastAPI-based REST API**: Easy integration with any application
- **Docker Support**: Containerized for easy deployment
- **GCP Cloud Run Ready**: Production-ready deployment to Google Cloud
- **Comprehensive Test Script Generation**: Includes Page Object Model, assertions, error handling

## 🔧 Prerequisites

### For Local Development
- Python 3.11 or higher
- pip (Python package manager)
- Google Cloud credentials (service account key JSON file)

### For Docker Deployment
- Docker Desktop or Docker Engine
- Google Cloud credentials

### For GCP Deployment
- Google Cloud SDK (gcloud CLI)
- Active GCP project with billing enabled
- Docker
- Appropriate GCP permissions (Cloud Run Admin, Storage Admin)

## 📦 Installation

### 1. Clone or Navigate to Project Directory

```bash
cd /Users/pr20347584/Desktop/A2A/Harness_Repo/wega-planning-design/testcase_to_script_agent
```

### 2. Install Dependencies

**Run these commands separately:**

```bash
pip install --upgrade google-cloud-aiplatform[agent_engines,langchain]
pip install cloudpickle==3.0.0
pip install "pydantic>=2.10"
pip install requests
pip install langgraph
pip install langchain-google-vertexai
pip install fastapi
pip install uvicorn[standard]
pip install python-multipart
```

**Or install from requirements.txt:**

```bash
pip install -r requirements.txt
```

### 3. Set Up Google Cloud Credentials

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
```

For permanent setup, add to your `.bashrc` or `.zshrc`:

```bash
echo 'export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"' >> ~/.zshrc
source ~/.zshrc
```

## 🚀 Local Development

### Start the FastAPI Server

```bash
uvicorn testcase_to_scripts_agent:app --host 0.0.0.0 --port 8080 --reload
```

The service will be available at:
- **API Base URL**: http://localhost:8080
- **Interactive API Docs**: http://localhost:8080/docs
- **Alternative Docs**: http://localhost:8080/redoc
- **Health Check**: http://localhost:8080/health

## 📡 API Usage

### Health Check

```bash
curl http://localhost:8080/health
```

### Convert Test Cases

```bash
curl -X POST http://localhost:8080/convert \
  -H "Content-Type: application/json" \
  -d '{
    "test_cases": "[{\"Test Case ID\": \"TC001\", \"Test Case Name\": \"User Login\", \"Steps\": [...]}]",
    "framework_type": "TestNG",
    "language": "Java",
    "script_generation_type": "Greenfield"
  }'
```

### Get Supported Combinations

```bash
curl http://localhost:8080/supported-combinations
```

## 🐳 Docker Deployment

### Build Docker Image

```bash
docker build -t testcase-to-scripts-agent .
```

### Run Docker Container

```bash
docker run -d \
  -p 8080:8080 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials.json \
  -v /path/to/your/service-account-key.json:/app/credentials.json \
  --name testcase-agent \
  testcase-to-scripts-agent
```

### Check Container Logs

```bash
docker logs -f testcase-agent
```

### Stop Container

```bash
docker stop testcase-agent
docker rm testcase-agent
```

## ☁️ GCP Cloud Run Deployment

### Prerequisites

1. Install and configure gcloud CLI:
```bash
gcloud init
gcloud auth login
```

2. Set your project:
```bash
gcloud config set project digital-rig-poc
```

### Automated Deployment

The project includes a deployment script for easy deployment to GCP Cloud Run:

```bash
# Make the script executable
chmod +x deploy_to_gcp.sh

# Run the deployment script
./deploy_to_gcp.sh
```

The script will:
1. ✅ Check prerequisites (gcloud, docker)
2. ✅ Enable required GCP APIs
3. ✅ Build Docker image
4. ✅ Push to Google Container Registry
5. ✅ Deploy to Cloud Run
6. ✅ Display the service URL

### Manual Deployment

If you prefer manual deployment:

```bash
# Build and tag the image
docker build -t gcr.io/digital-rig-poc/testcase-to-scripts-agent .

# Push to GCR
docker push gcr.io/digital-rig-poc/testcase-to-scripts-agent

# Deploy to Cloud Run
gcloud run deploy testcase-to-scripts-agent \
  --image gcr.io/digital-rig-poc/testcase-to-scripts-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --min-instances 0 \
  --max-instances 10
```

## 📚 API Endpoints

### `GET /`
Root endpoint with service information

**Response:**
```json
{
  "status": "healthy",
  "message": "Test Cases to Test Scripts Agent API is running",
  "supported_frameworks": ["TestNG", "BDD", "Playwright", "Selenium"],
  "supported_languages": ["Java", "Python", "JavaScript", "C#", "TypeScript"]
}
```

### `GET /health`
Health check endpoint

### `POST /convert`
Convert test cases to test scripts

**Request Body:**
```json
{
  "test_cases": "[{\"Test Case ID\": \"TC001\", ...}]",
  "framework_type": "TestNG",
  "language": "Java",
  "script_generation_type": "Greenfield"
}
```

**Parameters:**
- `test_cases` (required): Test cases in JSON format
- `framework_type` (optional, default: "TestNG"): TestNG, BDD, Playwright, or Selenium
- `language` (optional, default: "Java"): Java, Python, JavaScript, C#, or TypeScript
- `script_generation_type` (optional, default: "Greenfield"): Greenfield or Brownfield

**Response:**
```json
{
  "status": "success",
  "result": "# Test Cases to Test Scripts Conversion\n\n...",
  "framework": "TestNG",
  "language": "Java",
  "generation_type": "Greenfield"
}
```

### `GET /supported-combinations`
Get all supported framework and language combinations

## 📮 Testing with Postman

### 1. Import into Postman

Create a new request in Postman with these settings:

**Health Check:**
- Method: `GET`
- URL: `http://localhost:8080/health`
- Click Send

**Convert Test Cases:**
- Method: `POST`
- URL: `http://localhost:8080/convert`
- Headers: `Content-Type: application/json`
- Body (raw JSON):

```json
{
  "test_cases": "[{\"Test Case ID\": \"TC001\", \"Test Case Name\": \"User Login with Valid Credentials\", \"Test Case Description\": \"Verify that user can login with valid username and password\", \"Steps\": [{\"Step Number\": \"1\", \"Test Case Step\": \"Navigate to login page\", \"Expected Results\": \"Login page is displayed\", \"Java Page Name\": \"LoginPage\"}, {\"Step Number\": \"2\", \"Test Case Step\": \"Enter valid username\", \"Expected Results\": \"Username is entered in the field\", \"Java Page Name\": \"LoginPage\"}, {\"Step Number\": \"3\", \"Test Case Step\": \"Enter valid password\", \"Expected Results\": \"Password is entered in the field\", \"Java Page Name\": \"LoginPage\"}, {\"Step Number\": \"4\", \"Test Case Step\": \"Click login button\", \"Expected Results\": \"User is redirected to dashboard\", \"Java Page Name\": \"LoginPage\"}]}]",
  "framework_type": "TestNG",
  "language": "Java",
  "script_generation_type": "Greenfield"
}
```

### 2. Test Different Combinations

**BDD with Java:**
```json
{
  "test_cases": "[...]",
  "framework_type": "BDD",
  "language": "Java",
  "script_generation_type": "Greenfield"
}
```

**Playwright with TypeScript:**
```json
{
  "test_cases": "[...]",
  "framework_type": "Playwright",
  "language": "TypeScript",
  "script_generation_type": "Greenfield"
}
```

**Selenium with Python:**
```json
{
  "test_cases": "[...]",
  "framework_type": "Selenium",
  "language": "Python",
  "script_generation_type": "Brownfield"
}
```

## 📁 Project Structure

```
testcase_to_script_agent/
├── testcase_to_scripts_agent.py   # Main FastAPI application
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker configuration
├── deploy_to_gcp.sh               # GCP deployment script
├── README.md                       # This file
└── tc2scripts_agent.ipynb         # Original Jupyter notebook
```

## 🎯 Supported Frameworks and Languages

| Framework | Supported Languages |
|-----------|-------------------|
| TestNG | Java |
| BDD | Java, JavaScript, Python |
| Playwright | JavaScript, TypeScript, Python |
| Selenium | Java, Python, C#, JavaScript |

## 🔒 Security Notes

- Never commit your Google Cloud service account credentials to version control
- Use environment variables for sensitive configuration
- The Docker image runs as a non-root user for security
- Cloud Run deployment includes health checks and automatic scaling

## 🐛 Troubleshooting

### Issue: "GOOGLE_APPLICATION_CREDENTIALS not set"
**Solution:** Export the credentials path:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Issue: "Permission denied" when running deploy_to_gcp.sh
**Solution:** Make the script executable:
```bash
chmod +x deploy_to_gcp.sh
```

### Issue: Docker build fails
**Solution:** Ensure Docker daemon is running:
```bash
docker info
```

### Issue: gcloud command not found
**Solution:** Install Google Cloud SDK:
```bash
# macOS
brew install --cask google-cloud-sdk

# Or download from: https://cloud.google.com/sdk/docs/install
```

## 📝 License

This project is part of the Harness Repo/WEGA Planning Design suite.

## 🤝 Support

For issues or questions, please refer to the project documentation or contact the development team.

## 🔄 Version History

- **v1.0.0** - Initial release with FastAPI, Docker, and GCP Cloud Run support

---

**Generated by Test Cases to Test Scripts Agent** 🚀
