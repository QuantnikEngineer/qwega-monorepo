import logging
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger, swag_from
from google import genai
from google.genai import types
import os
import ssl
import requests as http_requests
from html.parser import HTMLParser
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ssl._create_default_https_context = ssl._create_unverified_context

import httpx
_original_httpx_client_init = httpx.Client.__init__
def _patched_httpx_client_init(self, *args, **kwargs):
    kwargs.setdefault("verify", False)
    _original_httpx_client_init(self, *args, **kwargs)
httpx.Client.__init__ = _patched_httpx_client_init

_original_httpx_async_client_init = httpx.AsyncClient.__init__
def _patched_httpx_async_client_init(self, *args, **kwargs):
    kwargs.setdefault("verify", False)
    _original_httpx_async_client_init(self, *args, **kwargs)
httpx.AsyncClient.__init__ = _patched_httpx_async_client_init

app = Flask(__name__)

# Enable CORS for all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# Swagger configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs"
}

swagger_template = {
    "info": {
        "title": "BRD Summary Agent API",
        "description": "API for generating intelligent summaries of Business Requirements Documents (BRD) from Confluence pages using Vertex AI (Gemini)",
        "version": "1.0.0",
        "contact": {
            "name": "BRD Summary Team"
        }
    },
    "basePath": "/",
    "schemes": ["https", "http"]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("Starting BRD Summary Agent server")

# Document URI - default BRD document, authenticated url and not public one of the document of gcp bucket
# For Vertex AI, use gs:// format (Cloud Storage URI)
#DEFAULT_DOCUMENT_URI = "gs://digital-rig-poc-gemini-document/YOU_BANK_BRD_Generic 1.pdf"
#logger.info(f"Default document URI set to: {DEFAULT_DOCUMENT_URI}")
# Note: HTTPS URLs don't work with Vertex AI - must use gs:// format
#gs://digital-rig-poc-gemini-document/HowToExportAzureCoPilotAgent_V1.2.pdf

def extract_page_id(confluence_link):
  """Extract page ID from a Confluence URL."""
  match = re.search(r'/pages/(\d+)', confluence_link)
  if match:
    return match.group(1)
  raise ValueError(f"Could not extract page ID from Confluence link: {confluence_link}")

def extract_base_url(confluence_link):
  """Extract base URL (scheme + host) from a Confluence URL."""
  match = re.match(r'(https?://[^/]+)', confluence_link)
  if match:
    return match.group(1)
  raise ValueError(f"Could not extract base URL from Confluence link: {confluence_link}")

class HTMLTextExtractor(HTMLParser):
  """Simple HTML parser to extract text content."""
  def __init__(self):
    super().__init__()
    self.text_parts = []
    
  def handle_data(self, data):
    stripped = data.strip()
    if stripped:
      self.text_parts.append(stripped)
      
  def get_text(self):
    return '\n'.join(self.text_parts)

def extract_html_text(html_content):
  """Extract plain text from HTML content."""
  parser = HTMLTextExtractor()
  parser.feed(html_content)
  return parser.get_text()

def fetch_confluence_docx(confluence_link):
  """Fetch the Confluence page content and extract text for analysis.
  
  Reads the content of the specified Confluence page and extracts plain text
  for Gemini analysis, without creating any intermediate files.
  
  Args:
    confluence_link: URL of the Confluence page
    
  Returns:
    dict: Dictionary containing:
      - 'text_content': Extracted plain text from the page
      - 'page_title': Title of the Confluence page
  """
  confluence_email = os.environ.get("CONFLUENCE_EMAIL")
  confluence_api_token = os.environ.get("CONFLUENCE_API_TOKEN")
  
  if not confluence_email or not confluence_api_token:
    raise ValueError("CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN environment variables are required")

  # Extract page ID and base URL from the Confluence link
  page_id = extract_page_id(confluence_link)
  base_url = extract_base_url(confluence_link)
  
  auth = (confluence_email, confluence_api_token)
  
  # Fetch the page content using Confluence REST API
  content_url = f"{base_url}/wiki/rest/api/content/{page_id}?expand=body.storage"
  logger.info(f"Fetching page content from: {content_url}")
  
  resp = http_requests.get(content_url, auth=auth, verify=False)
  resp.raise_for_status()
  
  page_data = resp.json()
  page_title = page_data.get('title', 'Confluence Page')
  page_body_html = page_data.get('body', {}).get('storage', {}).get('value', '')
  
  if not page_body_html:
    raise ValueError("No content found on the Confluence page")
  
  logger.info(f"Retrieved page content for: {page_title}")
  
  # Extract plain text from HTML for analysis
  text_content = extract_html_text(page_body_html)
  logger.info(f"Extracted text length: {len(text_content)} characters")
  
  return {
    'text_content': text_content,
    'page_title': page_title
  }

@app.route('/health', methods=['GET'])
def health_check():
  """Health check endpoint
  ---
  tags:
    - Health
  responses:
    200:
      description: Service is healthy
      schema:
        type: object
        properties:
          status:
            type: string
            example: healthy
          service:
            type: string
            example: BRD Analyzer Agent
  """
  logger.info("Health check endpoint called")
  return jsonify({"status": "healthy", "service": "BRD Summary Agent"}), 200

@app.route('/v1/brdsummary', methods=['POST'])
def analyze_brd():
  """Generate a comprehensive summary of a Business Requirements Document
  ---
  tags:
    - Analysis
  parameters:
    - in: body
      name: body
      required: true
      schema:
        type: object
        required:
          - confluence_link
        properties:
          confluence_link:
            type: string
            description: Confluence page URL containing the BRD content
            example: "https://wegabuildiq.atlassian.net/wiki/spaces/WAAD/pages/36962305/BRD+Page"
          query_text:
            type: string
            description: (Optional) Additional context or specific aspects to focus on
            example: "Focus on authentication and security requirements"
  responses:
    200:
      description: Summary generated successfully
      schema:
        type: object
        properties:
          status:
            type: string
            example: success
          message:
            type: string
            example: BRD summary generated successfully
          summary:
            type: string
            description: Comprehensive 500-700 word summary of the BRD capturing all important points
          confluence_link:
            type: string
            description: The analyzed Confluence page URL
    400:
      description: Missing required fields
      schema:
        type: object
        properties:
          status:
            type: string
            example: error
          message:
            type: string
            example: confluence_link is required
    500:
      description: Internal server error
      schema:
        type: object
        properties:
          status:
            type: string
            example: error
          message:
            type: string
  """
  logger.info("BRD Summary endpoint called")
  try:
    data = request.get_json(force=True, silent=True)
    logger.info(f"Received request data: {data}")
    
    if not data or not isinstance(data, dict):
      return jsonify({
        "status": "error",
        "message": "Invalid or missing JSON body. Expected JSON object with 'confluence_link' field. Example: {\"confluence_link\": \"https://your-confluence.atlassian.net/wiki/spaces/SPACE/pages/12345/BRD\"}"
      }), 400
    
    # Extract fields from request
    confluence_link = data.get('confluence_link')
    query_text = data.get('query_text', '')
    
    # Validate required fields
    if not confluence_link:
      return jsonify({
        "status": "error",
        "message": "confluence_link is required. Provide it as: {\"confluence_link\": \"https://...\"}"
      }), 400
    
    logger.info(f"Confluence Link: {confluence_link}")
    if query_text:
      logger.info(f"Additional context provided: {query_text}")
    
    # Fetch BRD document from Confluence
    logger.info("Fetching BRD document from Confluence...")
    confluence_data = fetch_confluence_docx(confluence_link)
    brd_text = confluence_data['text_content']
    logger.info(f"Extracted BRD text length: {len(brd_text)} characters")
    logger.debug(f"BRD text preview: {brd_text[:500]}...")
    
    # Generate summary using Gemini
    logger.info("Generating BRD summary using Gemini...")
    summary = generate_summary(brd_text, query_text)
    logger.info("Summary generation completed successfully")
    
    return jsonify({
      "status": "success",
      "message": "BRD summary generated successfully",
      "summary": summary,
      "confluence_link": confluence_link
    }), 200
    
  except Exception as e:
    logger.error(f"Error in analyze endpoint: {str(e)}", exc_info=True)
    return jsonify({
      "status": "error",
      "message": str(e)
    }), 500

@app.route('/', methods=['GET'])
def home():
  """Home endpoint with service information
  ---
  tags:
    - Info
  responses:
    200:
      description: Service information
      schema:
        type: object
        properties:
          service:
            type: string
            example: BRD Analyzer Agent
          version:
            type: string
            example: "1.0"
          endpoints:
            type: object
  """
  logger.info("Home endpoint called")
  return jsonify({
    "service": "BRD Summary Agent",
    "version": "1.0",
    "description": "Generate intelligent summaries of Business Requirements Documents from Confluence pages",
    "endpoints": {
      "/": "Home - this page",
      "/health": "Health check",
      "/v1/brdsummary": "POST - Generate BRD summary from Confluence page",
      "/docs": "API Documentation (Swagger UI)"
    },
    "usage": {
      "endpoint": "/v1/brdsummary",
      "method": "POST",
      "required_fields": ["confluence_link"],
      "optional_fields": ["query_text"],
      "example_request": {
        "confluence_link": "https://your-confluence.atlassian.net/wiki/spaces/SPACE/pages/12345/BRD",
        "query_text": "Focus on authentication requirements"
      }
    }
  }), 200


def generate_summary(brd_text, additional_context=""):
  """Generate a comprehensive summary of the BRD using Gemini model
  
  Args:
    brd_text: The full text content of the Business Requirements Document
    additional_context: Optional additional context or focus areas
  
  Returns:
    A comprehensive 500-700 word summary of the BRD
  """
  logger.info("Starting generate_summary() function")
  result_text = ""
  try:
    api_key = os.environ.get("GOOGLE_CLOUD_API_KEY")
    if not api_key:
      logger.warning("GOOGLE_CLOUD_API_KEY environment variable not set")
    else:
      logger.info("API key found, initializing Vertex AI client")
    
    client = genai.Client(
        vertexai=True,
        api_key=api_key,
    )
    logger.info("Vertex AI client initialized successfully")

    # Construct comprehensive summary prompt
    additional_instruction = f"\n\nAdditional focus: {additional_context}" if additional_context else ""
    
    summary_prompt = f"""You are an expert Business Analyst specialized in analyzing Business Requirements Documents (BRDs).

BUSINESS REQUIREMENTS DOCUMENT CONTENT:
{brd_text}

TASK:
Analyze the above Business Requirements Document and provide a comprehensive summary that:

1. Length: 500-700 words
2. Structure: Organize the summary into clear sections
3. Coverage: Capture ALL important points including:
   - Business objectives and goals
   - Key stakeholders and their roles
   - Functional requirements (core features and capabilities)
   - Non-functional requirements (performance, security, scalability, etc.)
   - Technical constraints and dependencies
   - Business rules and validation requirements
   - Integration requirements
   - Timeline and milestones (if mentioned)
   - Success criteria and acceptance criteria
   - Risks and assumptions
   - Any other critical business requirements

4. Style: Professional, clear, and concise
5. Focus: Prioritize the most critical business requirements and their implications{additional_instruction}

Provide a well-structured summary that a business stakeholder or technical team can use to quickly understand the complete scope and requirements of this project."""
    
    logger.info(f"Summary prompt constructed (length: {len(summary_prompt)} chars)")
    text_part = types.Part.from_text(text=summary_prompt)

    model = "gemini-3.1-flash-lite-preview"
    logger.info(f"Using model: {model}")
    
    contents = [
      types.Content(
        role="user",
        parts=[text_part]
      )
    ]
    logger.info("Content prepared for summary generation")

    logger.info("Configuring generation parameters")
    generate_content_config = types.GenerateContentConfig(
      temperature = 0.7,
      top_p = 0.95,
      max_output_tokens = 8192,
      safety_settings = [
        types.SafetySetting(
          category="HARM_CATEGORY_HATE_SPEECH",
          threshold="BLOCK_MEDIUM_AND_ABOVE"
        ),
        types.SafetySetting(
          category="HARM_CATEGORY_DANGEROUS_CONTENT",
          threshold="BLOCK_MEDIUM_AND_ABOVE"
        ),
        types.SafetySetting(
          category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
          threshold="BLOCK_MEDIUM_AND_ABOVE"
        ),
        types.SafetySetting(
          category="HARM_CATEGORY_HARASSMENT",
          threshold="BLOCK_MEDIUM_AND_ABOVE"
        )
      ],
      thinking_config=types.ThinkingConfig(
        thinking_level="HIGH",
      ),
    )
    logger.info("Generation config: temperature=0.7, top_p=0.95, max_tokens=8192, thinking_level=HIGH")

    logger.info("Starting content generation stream")
    chunk_count = 0
    for chunk in client.models.generate_content_stream(
      model = model,
      contents = contents,
      config = generate_content_config,
      ):
      chunk_count += 1
      result_text += chunk.text
      if chunk_count % 10 == 0:
        logger.debug(f"Processed {chunk_count} chunks")
    
    logger.info(f"Summary generation completed. Total chunks: {chunk_count}")
    logger.info(f"Summary length: {len(result_text)} characters")
    return result_text
    
  except Exception as e:
    logger.error(f"Error in generate_summary() function: {str(e)}", exc_info=True)
    raise

if __name__ == "__main__":
  logger.info("Starting Flask web server")
  port = int(os.environ.get("PORT", 8080))
  logger.info(f"Server will run on port {port}")
  # Run without SSL for local development (use reverse proxy like nginx for production SSL)
  app.run(host='0.0.0.0', port=port, debug=True)