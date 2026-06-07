#!/usr/bin/env python3
"""
LiteLLM Script for Multiple LLM Providers with AutoGen
======================================================

This script demonstrates how to use different LLM providers (Azure OpenAI, AWS Bedrock, Google AI)
with LiteLLM and AutoGen. It accepts provider and model name as inputs.

Usage:
    python litellm_client.py --provider azure_openai --model gpt-4o
    python litellm_client.py --provider aws_bedrock --model anthropic.claude-3-5-sonnet-20240620-v1:0
    python litellm_client.py --provider google --model gemini-2.0-flash-001
    python litellm_client.py --provider vertex_ai --model gemini-2.0-flash-001
"""

import os
import sys
import argparse
import asyncio
import json
import litellm
import httpx
import ssl
from secrets_manager import get_secret

# Configure LiteLLM - disable verbose logging to reduce noise
litellm.set_verbose = False
# Drop unsupported parameters automatically for different providers
litellm.drop_params = True
# Disable callbacks to reduce log noise
os.environ["LITELLM_LOG"] = "ERROR"


class LiteLLMRunner:
    """Runner for multiple LLM providers using LiteLLM"""
    
    SUPPORTED_PROVIDERS = {
        "azure_openai": {
            "models": ["gpt-4o", "gpt-4"],
            "env_vars": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_VERSION"]
        },
        "aws_bedrock": {
            "models": ["anthropic.claude-3-sonnet-20240229-v1:0", "anthropic.claude-3-5-sonnet-20240620-v1:0", "arn:aws:bedrock:us-east-1:486699759954:inference-profile/global.anthropic.claude-sonnet-4-20250514-v1:0", "arn:aws:bedrock:us-east-1:486699759954:inference-profile/global.anthropic.claude-sonnet-4-5-20250929-v1:0", "arn:aws:bedrock:us-east-1:486699759954:inference-profile/us.anthropic.claude-opus-4-20250514-v1:0", "arn:aws:bedrock:us-east-1:486699759954:inference-profile/global.anthropic.claude-opus-4-5-20251101-v1:0"],
            "env_vars": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"]
        },
        "google": {
            "models": ["gemini-2.0-flash-001", "gemini-2.5-flash"],
            "env_vars": ["GOOGLE_API_KEY"]
        },
        "vertex_ai": {
            "models": ["gemini-2.0-flash-001", "gemini-2.5-flash"],
            "env_vars": []  # Will use service account JSON file
        },
       
    }
    
    def __init__(self, provider: str, model: str):
        # Ensure provider is not None
        if provider is None:
            provider = "azure_openai"
        
        # Map 'google' provider to 'vertex_ai' to use service account authentication
        if provider.lower() == "google":
            provider = "vertex_ai"
            print("🔄 Mapping 'google' provider to 'vertex_ai' for service account authentication")
        
        self.provider = provider.lower()
        self.model = model
        self.vertex_ai_credentials = None
        self.aws_region = None
        self.setup_environment()
        
    def setup_environment(self):
        """Setup environment variables for the selected provider"""
        print(f"Setting up environment for provider: {self.provider}")
        
        if self.provider == "azure_openai":
            # Ensure Azure OpenAI credentials are available as environment variables
            api_key = get_secret("AZURE_OPENAI_API_KEY")
            endpoint = get_secret("AZURE_OPENAI_ENDPOINT")
            api_version = get_secret("AZURE_OPENAI_API_VERSION")
            
            if api_key:
                os.environ["AZURE_OPENAI_API_KEY"] = api_key
            if endpoint:
                os.environ["AZURE_OPENAI_ENDPOINT"] = endpoint
            if api_version:
                os.environ["AZURE_OPENAI_API_VERSION"] = api_version
            
            print(f"✅ Azure OpenAI environment configured with endpoint: {endpoint}")

        elif self.provider == "aws_bedrock":
            # Ensure AWS Bedrock credentials are available as environment variables when provided
            access_key = get_secret("AWS_ACCESS_KEY_ID")
            secret_key = get_secret("AWS_SECRET_ACCESS_KEY")
            region = self._resolve_aws_region()
            
            if access_key:
                os.environ["AWS_ACCESS_KEY_ID"] = access_key
            if secret_key:
                os.environ["AWS_SECRET_ACCESS_KEY"] = secret_key
            if region:
                os.environ["AWS_DEFAULT_REGION"] = region
                os.environ["AWS_REGION"] = region
            print(f"✅ AWS Bedrock environment configured with region: {region}")
                
              
        elif self.provider == "vertex_ai":
            # Load Vertex AI credentials from JSON file
            self.setup_vertex_ai_credentials()
    
    def get_resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        import sys
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)
    
    def setup_vertex_ai_credentials(self):
        """Setup Vertex AI credentials from JSON file"""
        try:
            # Get the directory where this script is located
            credentials_path = self.get_resource_path("vertexai.json")
            
            if not os.path.exists(credentials_path):
                print(f"❌ Vertex AI credentials file not found: {credentials_path}")
                return False
                
            # Load the credentials JSON
            with open(credentials_path, 'r') as f:
                self.vertex_ai_credentials = json.load(f)
            
            # Set up environment variables for Vertex AI
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            os.environ["VERTEXAI_PROJECT"] = self.vertex_ai_credentials.get("project_id", "")
            os.environ["VERTEXAI_LOCATION"] = "us-central1"  # Default location
            
            print(f"✅ Loaded Vertex AI credentials for project: {self.vertex_ai_credentials.get('project_id')}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup Vertex AI credentials: {str(e)}")
            return False
    
   
    def get_model_string(self) -> str:
        """Get the properly formatted model string for LiteLLM"""
        if self.provider == "azure_openai":
            # For Azure, use the deployment name or model name
            deployment = self.model
            return f"azure/{deployment}"
        elif self.provider == "aws_bedrock":
            # For AWS Bedrock, use bedrock/ prefix
            if self.model.startswith("bedrock/"):
                return self.model
            else:
                return f"bedrock/{self.model}"
        elif self.provider == "google":
            # For Google AI Studio (not Vertex AI), use gemini/ prefix to force AI Studio API
            if self.model.startswith("gemini/"):
                return self.model
            elif self.model.startswith("gemini-"):
                return f"gemini/{self.model}"
            else:
                return f"gemini/gemini-{self.model}"
        elif self.provider == "vertex_ai":
            # For Vertex AI, use vertex_ai/ prefix
            if self.model.startswith("vertex_ai/"):
                return self.model
            elif self.model.startswith("gemini-"):
                return f"vertex_ai/{self.model}"
            else:
                return f"vertex_ai/gemini-{self.model}"
       
        else:
            return self.model
    
    def check_environment(self) -> bool:
        """Check if required environment variables are set"""
        provider_config = self.SUPPORTED_PROVIDERS.get(self.provider)
        if not provider_config:
            print(f"❌ Unsupported provider: {self.provider}")
            return False
        
        # Special handling for vertex_ai
        if self.provider == "vertex_ai":
            if self.vertex_ai_credentials is None:
                print("❌ Vertex AI credentials not loaded")
                return False
            if not get_secret("VERTEXAI_PROJECT"):
                print("❌ VERTEXAI_PROJECT not set")
                return False
            print(f"✅ Vertex AI environment ready for project: {get_secret('VERTEXAI_PROJECT')}")
            return True
        
        if self.provider == "aws_bedrock":
            return self._check_bedrock_environment()
            
        missing_vars = []
        for env_var in provider_config["env_vars"]:
            if not get_secret(env_var):
                missing_vars.append(env_var)
        
        if missing_vars:
            print(f"❌ Missing environment variables for {self.provider}: {', '.join(missing_vars)}")
            return False
        
        print(f"✅ Environment variables set for {self.provider}")
        return True

    def _resolve_aws_region(self) -> str:
        if self.aws_region:
            return self.aws_region
        candidates = [
            get_secret("AWS_DEFAULT_REGION"),
            os.environ.get("AWS_REGION"),
            os.environ.get("AWS_DEFAULT_REGION"),
            "us-east-1",
        ]
        for candidate in candidates:
            if candidate and str(candidate).strip():
                self.aws_region = str(candidate).strip()
                break
        return self.aws_region

    def _check_bedrock_environment(self) -> bool:
        region = self._resolve_aws_region()
        if not region:
            print("❌ AWS_DEFAULT_REGION not configured for AWS Bedrock")
            return False

        access_key = get_secret("AWS_ACCESS_KEY_ID")
        secret_key = get_secret("AWS_SECRET_ACCESS_KEY")
        if access_key and secret_key:
            print("✅ AWS Bedrock static credentials detected in secrets store")
            return True

        role_indicators = [
            os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE"),
            os.environ.get("AWS_CONTAINER_CREDENTIALS_FULL_URI"),
            os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"),
        ]
        if any(role_indicators):
            print("✅ AWS Bedrock will use IAM role credentials from the runtime environment")
            return True

        print("ℹ️ AWS Bedrock will rely on the default AWS credential chain (instance profile / IRSA / CLI)")
        return True
    
    async def completion(self, messages: list) -> dict:
        """LiteLLM completion with the configured provider"""
        model_string = self.get_model_string()
        print(f"###################### Completion with model: {model_string} ######################")
        
        try:
            # Prepare completion parameters
            completion_kwargs = {
                "model": model_string,
                "messages": messages,
                "max_tokens": 2000,
                "temperature": 0
            }
            
            # Add provider-specific parameters
            if self.provider == "azure_openai":
                api_key = get_secret("AZURE_OPENAI_API_KEY")
                endpoint = get_secret("AZURE_OPENAI_ENDPOINT")
                api_version = get_secret("AZURE_OPENAI_API_VERSION", default_value="2024-02-15-preview")
                
                if api_key:
                    completion_kwargs["api_key"] = api_key
                if endpoint:
                    completion_kwargs["api_base"] = endpoint.rstrip('/')
                completion_kwargs["api_version"] = api_version
                    
            elif self.provider == "aws_bedrock":
                access_key = get_secret("AWS_ACCESS_KEY_ID")
                secret_key = get_secret("AWS_SECRET_ACCESS_KEY")
                session_token = get_secret("AWS_SESSION_TOKEN")
                region = self._resolve_aws_region() or "us-east-1"
                
                completion_kwargs["aws_region_name"] = region
                if access_key and secret_key:
                    completion_kwargs["aws_access_key_id"] = access_key
                    completion_kwargs["aws_secret_access_key"] = secret_key
                if session_token and session_token.strip():
                    completion_kwargs["aws_session_token"] = session_token
            
                
            elif self.provider == "vertex_ai":
                completion_kwargs["vertex_project"] = get_secret("VERTEXAI_PROJECT")
                completion_kwargs["vertex_location"] = get_secret("VERTEXAI_LOCATION", default_value="us-east-1")
            
            # Make the API call
            # print(f"###################### LiteLLM API call ######################")
            # print("Arguments: ", completion_kwargs)
            response = await litellm.acompletion(**completion_kwargs)
            # print("Response: ", response)
            # print(f"###################### LiteLLM API call completed ######################")
            return {
                "success": True,
                "response": response.choices[0].message.content,
                "model": response.model,
                "usage": response.usage._asdict() if hasattr(response.usage, '_asdict') else str(response.usage)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model": model_string
            }

async def main():
    """Main function to run the LiteLLM"""
    parser = argparse.ArgumentParser(description="LiteLLM with multiple providers")
    parser.add_argument("--provider", required=True, choices=["azure_openai", "aws_bedrock", "google", "vertex_ai"],
                       help="LLM provider to use")
    parser.add_argument("--model", required=True, help="Model name to use")
    parser.add_argument("--message", default="Hello!",
                       help="Message to send to the model")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("LiteLLM Multi-Provider")
    print("=" * 60)
    print(f"Provider: {args.provider}")
    print(f"Model: {args.model}")
    print(f"Message: {args.message}")
    print("-" * 60)
    
    # Initialize Runner
    runner = LiteLLMRunner(args.provider, args.model)
    
    # Check environment variables
    if not runner.check_environment():
        print("❌ Environment check failed. Please set the required environment variables.")
        sys.exit(1)
    
    # Messages
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": args.message}
    ]
    
    print("\n1. LiteLLM Completion...")
    completion_result = await runner.completion(messages)
    
    if completion_result["success"]:
        print("✅ LiteLLM Completion successful!")
        print(f"Model: {completion_result['model']}")
        print(f"Response: {completion_result['response']}")
        print(f"Usage: {completion_result['usage']}")
    else:
        print("❌ LiteLLM Completion failed!")
        print(f"Error: {completion_result['error']}")
        return
    
    print("\n" + "=" * 60)
    print("LiteLLM completion Completed!")
    print("=" * 60)

def list_supported_models():
    """List all supported providers and models"""
    print("Supported Providers and Models:")
    print("=" * 40)
    
    runner = LiteLLMRunner("azure_openai", "gpt-4o")  # Dummy instance
    
    for provider, config in runner.SUPPORTED_PROVIDERS.items():
        print(f"\n{provider.upper()}:")
        print(f"  Models: {', '.join(config['models'])}")
        print(f"  Required Env Vars: {', '.join(config['env_vars'])}")

if __name__ == "__main__":
    if len(sys.argv) == 1 or "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        print("\nSupported configurations:")
        list_supported_models()
        print("\nExample usage:")
        print("  python litellm_client.py --provider azure_openai --model gpt-4o")
        print("  python litellm_client.py --provider aws_bedrock --model anthropic.claude-3-5-sonnet-20240620-v1:0")
        print("  python litellm_client.py --provider google --model gemini-2.0-flash-001")
        print("  python litellm_client.py --provider vertex_ai --model gemini-2.0-flash-001")
        sys.exit(0)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        sys.exit(1)