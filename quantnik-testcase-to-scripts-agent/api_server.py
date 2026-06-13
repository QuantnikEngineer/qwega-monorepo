
"""
FastAPI Server for Test Cases to Test Scripts Agent
Exposes REST API endpoints for Docker deployment
"""
import asyncio
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langfuse_instrumentation import instrument, LangfuseASGIMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List
from dotenv import load_dotenv
import uvicorn
from testcase_to_scripts_agent import process_single_test_case, TEST_SCRIPT_PROMPTS, SUPPORTED_FRAMEWORKS, SUPPORTED_LANGUAGES

load_dotenv()

app = FastAPI(title="Test Cases to Test Scripts Agent API",description="Convert test cases into automation test scripts using multiple frameworks and languages",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
instrument()
app.add_middleware(LangfuseASGIMiddleware)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================
class ConversionRequest(BaseModel):
    test_cases: str = Field(..., description="Test cases in JSON format to convert",example='[{"Test Case ID": "TC001", "Test Case Name": "Login Test", "Steps": [...]}]')
    framework_type: str = Field(default="Selenium TestNG",description="Testing framework to use",example="Selenium TestNG")
    language: str = Field(default="Java",description="Programming language for the scripts",example="Java")
    script_generation_type: str = Field(default="Greenfield",description="Generation approach: Greenfield or Brownfield",example="Greenfield")

class ConversionResponse(BaseModel):
    status: str
    push_results: Dict[str, List[str]]

class HealthResponse(BaseModel):
    status: str
    message: str
    supported_frameworks: List[str]
    supported_languages: List[str]

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with service information"""
    return HealthResponse(status="healthy",message="Test Cases to Test Scripts Agent API is running",supported_frameworks=SUPPORTED_FRAMEWORKS,supported_languages=SUPPORTED_LANGUAGES)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy",message="Service is operational",supported_frameworks=SUPPORTED_FRAMEWORKS,supported_languages=SUPPORTED_LANGUAGES)

@app.post("/convert", response_model=ConversionResponse)
async def generate_test_scripts(request: ConversionRequest):
    """
    Convert test cases to test automation scripts
    - **test_cases**: Test cases in JSON format
    - **framework_type**: Selenium TestNG, Selenium BDD, or Playwright
    - **language**: Java, Python, JavaScript, C#, or TypeScript
    - **script_generation_type**: Greenfield or Brownfield
    """
    try:
        test_cases_list = json.loads(request.test_cases)
        if isinstance(test_cases_list, dict):
            test_cases_list = [test_cases_list]
        tasks = [process_single_test_case(tc, request.framework_type, request.language, request.script_generation_type) for tc in test_cases_list]
        results = await asyncio.gather(*tasks) 
        folder_file_map: Dict[str, List[str]] = {}
        for tc, (code_blocks, file_urls, folder_name) in zip(test_cases_list, results):
            folder_file_map[folder_name] = file_urls
        return ConversionResponse(status="success",push_results=folder_file_map)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during conversion: {str(e)}")

@app.get("/supported-combinations")
async def get_supported_combinations():
    """Get all supported framework and language combinations"""
    combinations = []
    for framework, config in TEST_SCRIPT_PROMPTS.items():
        for language in config["languages"]:
            combinations.append({"framework": framework,"language": language,"generation_types": ["Greenfield", "Brownfield"]})
    return {"supported_combinations": combinations,"total_combinations": len(combinations)}

if __name__ == "__main__":
    print("🚀 Starting Test Cases to Test Scripts Agent API...")
    print(f"📋 Supported Frameworks: {SUPPORTED_FRAMEWORKS}")
    print(f"📋 Supported Languages: {SUPPORTED_LANGUAGES}")
    uvicorn.run("api_server:app", host="0.0.0.0", port=8080, reload=True)