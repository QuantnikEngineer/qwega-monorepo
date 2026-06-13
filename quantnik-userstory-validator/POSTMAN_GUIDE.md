# Using Postman with BRD-Agent-GCP

This guide shows you how to test the BRD-Agent-GCP API using Postman.

## Prerequisites

1. Flask server running (locally or on GCP)
2. Postman installed or use [Postman Web](https://web.postman.co/)

## Starting the Server Locally

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the Flask server
python server.py
```

The server will start on `http://localhost:8080`

## API Endpoints

### 1. Health Check

**GET** `http://localhost:8080/health`

**Response:**
```json
{
  "status": "healthy",
  "service": "Quantnik-Userstory-Validator"
}
```

### 2. Root Endpoint (API Info)

**GET** `http://localhost:8080/`

**Response:**
```json
{
  "service": "Quantnik-Userstory-Validator",
  "version": "1.0.0",
  "endpoints": {
    "health": "/health",
    "query": "/query (POST)"
  },
  "usage": {
    "endpoint": "/query",
    "method": "POST",
    "body": {
      "question": "Your question here",
      "document_uri": "optional-document-uri"
    }
  }
}
```

### 3. Query Endpoint (Main Functionality)

**POST** `http://localhost:8080/query`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "question": "What are the Internet Banking features?"
}
```

**Optional - With Custom Document:**
```json
{
  "question": "What are the key features?",
  "document_uri": "gs://your-bucket/your-document.pdf"
}
```

**Response:**
```json
{
  "question": "What are the Internet Banking features?",
  "answer": "Based on the BRD document, the Internet Banking features include...",
  "document_uri": "https://storage.googleapis.com/digital-rig-poc-gemini-document/YOU_BANK_BRD_Generic%201.pdf"
}
```

## Postman Collection Setup

### Step 1: Create a New Collection

1. Open Postman
2. Click **Collections** → **New Collection**
3. Name it "BRD-Agent-GCP"

### Step 2: Add Environment Variables

1. Click **Environments** → **Create Environment**
2. Name it "BRD-Agent Local"
3. Add variables:
   - `base_url`: `http://localhost:8080`
   - `gcp_url`: `http://YOUR-GCP-IP:8080` (for production)

### Step 3: Create Requests

#### Request 1: Health Check

- **Method:** GET
- **URL:** `{{base_url}}/health`
- **Headers:** None needed

#### Request 2: Query BRD

- **Method:** POST
- **URL:** `{{base_url}}/query`
- **Headers:**
  - `Content-Type`: `application/json`
- **Body (raw JSON):**
```json
{
  "question": "What are the Internet Banking features?"
}
```

#### Request 3: Custom Query

- **Method:** POST
- **URL:** `{{base_url}}/query`
- **Headers:**
  - `Content-Type`: `application/json`
- **Body (raw JSON):**
```json
{
  "question": "What are the mobile banking features?",
  "document_uri": "https://storage.googleapis.com/digital-rig-poc-gemini-document/YOU_BANK_BRD_Generic%201.pdf"
}
```

## Sample Questions to Test

```json
{"question": "What are the Internet Banking features?"}
{"question": "What are the security requirements?"}
{"question": "What are the user authentication methods?"}
{"question": "What are the mobile banking capabilities?"}
{"question": "What are the payment processing features?"}
{"question": "Summarize the main objectives of this BRD"}
```

## Testing on GCP Compute Engine

Once deployed to GCP, replace the base URL:

1. Get your instance's external IP:
```bash
gcloud compute instances describe brd-agent-instance --zone=us-central1-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

2. Update Postman environment:
   - `base_url`: `http://EXTERNAL_IP:8080`

3. Ensure firewall allows port 8080:
```bash
gcloud compute firewall-rules create allow-brd-agent \
    --allow tcp:8080 \
    --target-tags http-server \
    --description="Allow BRD Agent API traffic"
```

## Error Handling

### 400 Bad Request
**Cause:** Missing or invalid JSON body

**Example Error:**
```json
{
  "error": "Missing 'question' field in request body"
}
```

**Fix:** Ensure your request includes a `question` field

### 500 Internal Server Error
**Cause:** Server-side error (authentication, API issues)

**Example Error:**
```json
{
  "error": "Your default credentials were not found..."
}
```

**Fix:** 
- Check server logs
- Verify GCP credentials are configured
- Ensure Vertex AI API is enabled

## Postman Tests (Automated)

Add these to the **Tests** tab in Postman to automate validation:

```javascript
// Test 1: Status code is 200
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

// Test 2: Response has answer field
pm.test("Response contains answer", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData).to.have.property('answer');
});

// Test 3: Answer is not empty
pm.test("Answer is not empty", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.answer).to.not.be.empty;
});

// Test 4: Response time is acceptable
pm.test("Response time is less than 30s", function () {
    pm.expect(pm.response.responseTime).to.be.below(30000);
});
```

## cURL Examples

If you prefer command line:

```bash
# Health check
curl http://localhost:8080/health

# Query
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the Internet Banking features?"}'

# Query with custom document
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the key features?",
    "document_uri": "gs://your-bucket/document.pdf"
  }'
```

## Troubleshooting

### Connection Refused
- Ensure server is running
- Check port 8080 is not in use
- Verify firewall rules (for GCP)

### Authentication Errors
- Run: `gcloud auth application-default login` (local)
- Verify service account permissions (GCP)

### Slow Responses
- Gemini API can take 10-30 seconds for complex queries
- Increase Postman timeout in Settings

## Next Steps

1. Create a Postman Collection and share it with your team
2. Set up Postman monitors for automated testing
3. Add authentication (API keys, OAuth) for production
4. Implement rate limiting and caching
