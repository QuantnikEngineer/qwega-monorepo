import os
import json
from dotenv import load_dotenv
load_dotenv()

from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
try:
    from autogen_ext.models.openai import OpenAIChatCompletionClient
except ImportError:
    OpenAIChatCompletionClient = None

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken
# from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools
from litellm_client import  LiteLLMRunner

from typing_extensions import Unpack

# Add imports for file parsing
import base64
import io

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

async def _get_model_client(llm_provider="azure_openai", llm_model=None, api_key=None):
   
   chat_model = "test"
   return chat_model



async def get_agent(azure_client, system_message=None) -> AssistantAgent:
    """Get the assistant agent with MCP Jira tools integration"""
    
    default_system_message = """
You are an expert in generating functional Test Scenarios, Test Cases and Test Scripts from user stories provided in detail.
You also have access to Jira tools to create and manage issues.

# TEST SCENARIOS

Generate all positive test scenarios for the given user story.
Don't create any negative test scenarios. Create granular scenarios for each acceptance criteria.

For each test scenario provide:
- **Test Scenario ID**: TS-XXX
- **Test Scenario Description**: Clear description of what to verify
- **Expected Results**: What should happen
- **Priority**: P1/P2/P3 (P1 = Critical, P2 = High, P3 = Medium) 
- **Pre-Condition**: Required setup/state before test

# TEST CASES

Given all test scenarios, create detailed test cases which cover step-by-step instructions by referring to application flow provided in the user story.
Strictly give only one test case for the given scenario. Ensure that the test case name is concise yet captures the essence of the description.
Present the expected results using future tense, employing phrases such as 'should be' or 'would be'.

For each test case provide:
- **Test Case ID**: TC-XXX
- **Test Case Name**: Brief descriptive name
- **Test Case Description**: Detailed description
- **Test Steps**: Numbered step-by-step instructions
- **Expected Results**: What should be observed

# TEST SCRIPTS

Generate combined end-to-end automation scripts for the given test cases as outlined above. Refer to the detailed test steps for creating scripts.

Task: Strengthen Test Stability
Objective: Identify potential areas of vulnerability in the code where errors may arise. Pinpoint locations requiring thread sleep and assertions to enhance script resilience.

Action: Implement Robust Techniques:
- Add separate Try-Catch Blocks after every commented step to gracefully handle unexpected exceptions
- Add appropriate wait strategy to enhance stability
- Add implicit wait of 10 seconds after opening the website
- Integrate Assertions: Specify critical checkpoints in the test scenario and embed assertions to validate expected outcomes

For each test script provide:
- **Test Case ID**: TC-XXX
- **Test Case Name**: Same as test case
- **Test Script**: Complete automation script

# JIRA INTEGRATION

You can create Jira issues for test cases using the available Jira tools.
        """

    # Get Jira tools from the model client (set up in _get_model_client)
    jira_tools = getattr(azure_client, 'jira_tools', [])

    # Create the assistant agent with Jira tools
    agent = AssistantAgent(
        name="test_case_generator",
        model_client=azure_client,
        system_message=system_message or default_system_message,
        tools=jira_tools
    )   

    return agent


async def get_test_scenarios_agent(azure_client) -> AssistantAgent:
    """Get the agent specifically for generating test scenarios"""
    system_message = """
You are an expert in generating functional Test Scenarios from user stories.

# TEST SCENARIOS

Generate all positive test scenarios for the given user story.
Don't create any negative test scenarios. Create granular scenarios for each acceptance criteria.

For each test scenario must provide:
- **Test Scenario ID**: TS-XXX
- **Test Scenario Description**: Clear description of what to verify
- **Expected Results**: What should happen
- **Priority**: P1/P2/P3 (P1 = Critical, P2 = High, P3 = Medium) 
- **Pre-Condition**: Required setup/state before test

Focus only on generating comprehensive test scenarios. Do not generate test cases or test scripts.
    """
    return await get_agent(azure_client, system_message)


async def get_test_cases_agent(azure_client) -> AssistantAgent:
    """Get the agent specifically for generating test cases"""
    system_message = """
You are an expert in generating detailed Test Cases from user stories.

# TEST CASES

Create detailed test cases which cover step-by-step instructions by referring to application flow provided in the user story.
Strictly give only one test case for the given scenario. Ensure that the test case name is concise yet captures the essence of the description.
Present the expected results using future tense, employing phrases such as 'should be' or 'would be'.

For each test case must provide:
- **Test Case ID**: TC-XXX
- **Test Case Name**: Brief descriptive name
- **Test Case Description**: Detailed description
- **Test Steps**: Numbered step-by-step instructions
- **Expected Results**: What should be observed

Focus only on generating comprehensive test cases. Do not generate test scenarios or test scripts.
    """
    return await get_agent(azure_client, system_message)


async def get_test_scripts_agent(azure_client) -> AssistantAgent:
    """Get the agent specifically for generating test scripts"""
    system_message = """
You are an expert in generating automation Test Scripts from user stories and test cases.

# TEST SCRIPTS

Generate combined end-to-end automation scripts for the given test cases. Refer to the detailed test steps for creating scripts.

Task: Strengthen Test Stability
Objective: Identify potential areas of vulnerability in the code where errors may arise. Pinpoint locations requiring thread sleep and assertions to enhance script resilience.

Action: Implement Robust Techniques:
- Add separate Try-Catch Blocks after every commented step to gracefully handle unexpected exceptions
- Add appropriate wait strategy to enhance stability
- Add implicit wait of 10 seconds after opening the website
- Integrate Assertions: Specify critical checkpoints in the test scenario and embed assertions to validate expected outcomes

For each test script must provide:
- **Test Case ID**: TC-XXX
- **Test Case Name**: Same as test case
- **Test Script**: Complete automation script

Focus only on generating comprehensive test automation scripts. Do not generate test scenarios or test cases.
    """
    return await get_agent(azure_client, system_message)

# Do not change the method and module name
async def execute_workflow(**kwargs: Unpack[dict]):
    """
    Method for executing the Agent workflow
    """
    query = kwargs.get("query")
    file_names = kwargs.get("file_names")
    file_contents = kwargs.get("file_contents")
    # Extract text content parameters from frontend
    user_story_text = kwargs.get("user_story_text")  # New field for user story content
    # Extract LLM parameters from kwargs
    llm_provider = kwargs.get("llm_provider")
    llm_model = kwargs.get("llm_model")
    api_key = kwargs.get("api_key")
    
    
    return await execute_complete_workflow(**kwargs)

async def execute_complete_workflow(**kwargs: Unpack[dict]):
    """
    Execute the complete workflow that generates scenarios, cases, and scripts
    """
    query = kwargs.get("query")
    file_names = kwargs.get("file_names")
    file_contents = kwargs.get("file_contents")
    # Extract text content parameters from frontend
    user_story_text = kwargs.get("user_story_text")  # New field for user story content
    # Extract LLM parameters from kwargs
    llm_provider = kwargs.get("llm_provider")
    llm_model = kwargs.get("llm_model")
    api_key = kwargs.get("api_key")

   
   
        

    # Build the agent input message
    agent_input = ""
    agent_input +=" As an agent you are capable of analysing epics and user stories. so you should able to answer to the user queries in general way and also you should able to generate test scenarios, test cases and test scripts from the given user stories."
    agent_input +=" clarify the user queries with proper response"
    agent_input +="For any general queries provide the response in concise way."
    # Start with the user query if provided
    if query and query.strip():
        agent_input += f"User Query: {query.strip()}\n\n"
    
    # Build KB_CONTEXT from file contents and text inputs
    kb_context_parts = []
    
    
    if user_story_text and user_story_text.strip():
        kb_context_parts.append(f"User Story:\n{user_story_text.strip()}")
    
    # Build the structured input for the system prompt
    if kb_context_parts:
        agent_input += "KB_CONTEXT:\n" + "\n\n---\n\n".join(kb_context_parts) + "\n\n"
    
    
    # If no structured context provided, fall back to simple query
    if not agent_input.strip():
        agent_input = query.strip() if query else ""
    
    # Add instruction to generate table of contents response
    if kb_context_parts:
        agent_input += "\nPlease generate a Test Scenarios from the given User Stories."
        agent_input += "\n\nPlease generate a Test Cases from the given User Stories."
        agent_input += "\n\nPlease generate a Test Scripts from the given User Stories."

    runner = LiteLLMRunner(llm_provider, llm_model)
    response = await runner.completion(messages=[{"role": "user", "content": agent_input}])
    return response

