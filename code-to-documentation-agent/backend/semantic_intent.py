# semantic_intent.py
import os
from openai import AzureOpenAI, api_key
from litellm_client import LiteLLMRunner
from secrets_manager import get_secret
# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# azure_openai_endpoint = get_secret("AZURE_OPENAI_ENDPOINT")
# azure_openai_api_key = get_secret("AZURE_OPENAI_API_KEY")
# azure_openai_deployment_name = get_secret("AZURE_OPENAI_DEPLOYMENT_NAME")
# AZURE_OPENAI_API_VERSION = get_secret("AZURE_OPENAI_API_VERSION")

azure_openai_endpoint = get_secret("AZURE_OPENAI_ENDPOINT")
azure_openai_api_key = get_secret("AZURE_OPENAI_API_KEY")
azure_openai_deployment_name = get_secret("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = get_secret("AZURE_OPENAI_API_VERSION")

def get_client():
    """Get Azure OpenAI client with environment variables (legacy function)"""
    return AzureOpenAI(
        azure_endpoint=azure_openai_endpoint,
        api_key=azure_openai_api_key,
        api_version=AZURE_OPENAI_API_VERSION
    )

async def classify_intent_legacy(user_query):
    """Legacy function for backward compatibility - uses Azure OpenAI only"""
    
    client = get_client()
    messages = [
        {"role": "system", "content": (
            "You are an AI assistant to identify the primary semantic intent of user's query."
            "Respond with only the identified intent, concisely and without additional explanations or coversational texts."
            "Examples: 'help', 'informational', 'greeting', 'confirm'"
        )},
        {"role": "user", "content": f"{user_query}"}
    ]
    # Fix deployment name variable
    response = client.chat.completions.create(model=azure_openai_deployment_name, messages=messages, max_tokens=30, temperature=0)
    # For OpenAI Python SDK v1+, response is an object, not a dict
    intent = response.choices[0].message.content.strip().lower()
    return intent


async def classify_intent(user_query, llm_provider="azure_openai", llm_model=None, api_key=None):
    """Extracts the semantic intent from the user query using Azure OpenAI."""
    
    # Get the appropriate model for the provider if not specified
    if not llm_model:
        default_models = {
            "azure_openai": "gpt-4o",
            "aws_bedrock": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "google": "gemini-2.0-flash-001",
            "vertex_ai": "gemini-2.0-flash-001"
        }
        llm_model = default_models.get(llm_provider, "gpt-4o")
    
    # Map 'google' provider to 'vertex_ai' for better authentication
    if llm_provider == "google":
        llm_provider = "vertex_ai"
    
    
    
    # Create LiteLLM runner for the specified provider
    runner = LiteLLMRunner(provider=llm_provider, model=llm_model)

    messages = [
        {"role": "system", "content": (
            "You are an AI assistant to identify the primary semantic intent of user's query."
            "Respond with only the identified intent, concisely and without additional explanations or coversational texts."
            "Examples: 'help', 'informational', 'greeting', 'confirm'"
        )},
        {"role": "user", "content": f"{user_query}"}
    ]
    
    try:
        # Use LiteLLM to call any provider
        response = await runner.completion(messages=messages)
        
        # Extract intent from response (LiteLLMRunner returns a dictionary)
        if response["success"]:
            intent = response["response"].strip().lower()
        else:
            raise Exception(f"LiteLLM completion failed: {response['error']}")

        # Validate and normalize intent against example values
        example_intents = [
            'help', 'informational', 'greeting', 'confirm', 'case', 'scenario', 'cases', 'scenarios','scripts', 'epic', 'user story', 'script'
        ]
        
        # Check if intent starts with any of the example values
        for example in example_intents:
            if intent.startswith(example):
                intent = example
                break
        else:
            # If no match found, call legacy function as fallback
            try:
                intent = await classify_intent_legacy(user_query)
            except Exception as legacy_error:
                intent = "informational"

        return intent
        
    except Exception as e:
        # Fallback to default intent
        return "informational"