from vertexai import init
from vertexai.generative_models import GenerativeModel, HarmBlockThreshold, HarmCategory, SafetySetting
import re
import os
import json
import logging
import threading
import requests
from requests.auth import HTTPBasicAuth
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from typing import Any, Dict, List, Optional
import urllib3
import ssl
import time

# ---------------------------------------------------------------------------
# SSL configuration for corporate proxy / SSL-inspection environments.
# Option 1 (recommended): set REQUESTS_CA_BUNDLE=/path/to/corporate-ca-bundle.crt in .env
# Option 2 (dev/testing only): set DISABLE_SSL_VERIFY=true in .env
# ---------------------------------------------------------------------------
_disable_ssl_verify = os.getenv("DISABLE_SSL_VERIFY", "false").lower() in ("true", "1", "yes")
if _disable_ssl_verify:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    _orig_merge_env = requests.Session.merge_environment_settings
    def _patched_merge_env(self, url, proxies, stream, verify, cert):
        settings = _orig_merge_env(self, url, proxies, stream, verify, cert)
        settings["verify"] = False
        return settings
    requests.Session.merge_environment_settings = _patched_merge_env

os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''
os.environ['GRPC_SSL_CIPHER_SUITES'] = 'HIGH:!DH:!aNULL'
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '1'
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_SSL_TARGET_NAME_OVERRIDE'] = 'aiplatform.googleapis.com'
os.environ['GRPC_DEFAULT_SSL_ROOTS_FILE_PATH'] = ''

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Provider selection ────────────────────────────────────────────────────────
_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "google").lower()  # "google" | "azure"
logger.info("LLM provider: %s", _LLM_PROVIDER)

# ── Azure OpenAI singleton ────────────────────────────────────────────────────
_azure: dict = {}


def _get_azure_client():
    """Return a cached (OpenAI client, deployment_name) tuple."""
    if _azure:
        return _azure["client"], _azure["deployment"]
    from openai import OpenAI  # imported lazily — not needed for Google path
    client = OpenAI(base_url=os.environ["AZURE_OPENAI_ENDPOINT"],api_key=os.environ["AZURE_OPENAI_API_KEY"])
    _azure["client"] = client
    _azure["deployment"] = os.environ["AZURE_OPENAI_DEPLOYMENT"]
    logger.info("Azure OpenAI client initialised: deployment=%s", _azure["deployment"])
    return client, _azure["deployment"]

PROJECT_ID = os.getenv("PROJECT_ID", "digital-rig-poc")
LOCATION = os.getenv("LOCATION", "global")
STAGING_BUCKET = os.getenv("STAGING_BUCKET","gs://test-agent-digital-engine-bucket")
MODEL_NAME = os.getenv("MODEL_NAME","gemini-3-flash-preview")

TEST_PLAN_KEY = os.getenv("TEST_PLAN_KEY", "WEGA-875")
XRAY_GRAPHQL_URL = os.getenv("XRAY_GRAPHQL_URL", "https://xray.cloud.getxray.app/api/v2/graphql")

jira_config = {
    "base_url":    os.getenv("JIRA_BASE_URL",    "https://wegabuildiq.atlassian.net/"),
    "username":    os.getenv("JIRA_USERNAME",    "harsh.65@wipro.com"),
    "api_token":   os.getenv("JIRA_API_TOKEN",   ""),
    "project_key": os.getenv("JIRA_PROJECT_KEY", "WEGAAIDEMO"),
}

xray_config = {
    "client_id":     os.getenv("XRAY_CLIENT_ID",     ""),
    "client_secret": os.getenv("XRAY_CLIENT_SECRET", ""),
}

qtest_config = {
    "base_url":   os.getenv("QTEST_BASE_URL",   "https://your-qtest-domain.qtestnet.com/api/v3"),
    "project_id": os.getenv("QTEST_PROJECT_ID", "12345"),
    "token":      os.getenv("QTEST_TOKEN",       "your_qtest_api_token"),
}

# ---------------------------------------------------------------------------
# SSL context patch
# ---------------------------------------------------------------------------
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

model = None
if _LLM_PROVIDER != "azure":
    try:
        init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)
        logger.info("Vertex AI initialized successfully (SSL verification disabled)")
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {str(e)}")
        raise

    try:
        model = GenerativeModel(MODEL_NAME)
        logger.info(f"GenerativeModel '{MODEL_NAME}' initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize GenerativeModel: {str(e)}")
        raise

GENERATION_CONFIG = {"temperature": 0.3, "top_p": 0.95, "top_k": 40}
SAFETY_SETTINGS = [
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,       threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,  threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
]

def _retry_api_call(func, max_retries=5, initial_delay=2):
    """
    Retry a function with exponential backoff for SSL and connection errors.
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"API call attempt {attempt + 1}/{max_retries}")
            return func()
        except Exception as e:
            error_str = str(e)
            is_retryable = any(keyword in error_str for keyword in 
                             ['SSL', 'Connection', 'timeout', 'Max retries', 'EOF', 'Timeout', 
                              'RemoteDisconnected', 'closed connection', 'aborted'])
            
            if is_retryable and attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {error_str}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed after {attempt + 1} attempts. Error: {error_str}")
                raise

def generate_test_cases(userstory, scenarioType):
    """
    Generate structured test cases from user story and scenario type.
    Returns test cases in Markdown format.
    """
    try:
        if not userstory or not userstory.strip():
            raise ValueError("User story cannot be empty")
        testScenarios = generate_test_scenarios_from_userstory(userstory, scenarioType)
        json_format = """
        {
            "Test Case ID": "<Test Case ID Number will come here>",
            "Test Case Name": "<Name>",
            "Test Case Description": "<Description>",
            "Steps": [
                {
                    "Step Number": "<Step number_1>",
                    "Test Case Step": "<Test Case Steps_1>",
                    "Expected Results": "<Expected Results_1>"
                }
            ]
        }"""   
        prompt_for_testcases = f"""
        User Story: {userstory} \n
        You are a QA assistant. Based on the following test scenarios, generate one detailed test case for each scenario.
        Instructions:
        - For each test scenario provided below, create a single, complete test case that covers detailed steps by referring to the application flow described in the user story.
        - Strictly analyze the entire application flow and use only the relevant parts/steps of the flow to create each test case end-to-end. Do not add redundant or irrelevant steps.
        - Present all test cases in a **JSON array**, where each element represents one test case.
        - Each test case must include the following keys:
        - "Test Case ID"
        - "Test Case Name"
        - "Test Case Description"
        - "Step Number"
        - "Test Case Step"
        - "Expected Results"
        - Ensure that:
        - Each "Test Case Name" is concise and captures the essence of the scenario.
        - "Expected Results" use future tense (e.g., "should be", "would be").
        - Return the response **only** in the following JSON format (no extra text, explanations, or markdown):
        {json_format} \n
        Here are the Test Scenarios: {testScenarios}"""  
        
        # Use retry logic for API call
        if _LLM_PROVIDER == "azure":
            def make_api_call():
                client, deployment = _get_azure_client()
                resp = client.chat.completions.create(model=deployment,messages=[{"role": "user", "content": prompt_for_testcases}],temperature=0.3,top_p=0.95)
                return resp
            api_response = _retry_api_call(make_api_call, max_retries=5)
            response_text = api_response.choices[0].message.content or ""
        else:
            def make_api_call():
                return model.generate_content(prompt_for_testcases, generation_config=GENERATION_CONFIG,safety_settings=SAFETY_SETTINGS)
            api_response = _retry_api_call(make_api_call, max_retries=5)
            if not api_response or not api_response.text:
                raise ValueError("Empty response from model")
            response_text = api_response.text
        
        if not response_text:
            raise ValueError("Empty response from model")

        pattern = r"```json(.*?)```"
        matches = re.findall(pattern, response_text, re.DOTALL)
        response_json = matches[0] if matches else response_text
        
        testScenarios = _normalize_multiline(testScenarios)
        response_json = _normalize_multiline(response_json)
        response = {"Test Scenarios": testScenarios, "Test Cases": response_json}
        return response
        
    except ValueError as e:
        logger.error(f"Validation error in generate_test_cases: {str(e)}")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in generate_test_cases: {str(e)}")
        return {"error": f"Failed to generate test cases: {str(e)}"}

def generate_test_scenarios_from_userstory(userstory, scenarioType):
    """
    Generate structured test scenarios from user story.
    Returns test scenarios in Markdown format.
    """
    try:
        if not userstory or not userstory.strip():
            raise ValueError("User story cannot be empty")
        
        TEST_SCENARIO_PROMPTS = {
        "Functional": "Generate only positive test scenarios (scenarios that validate/verify the positive requirement mentioned) for the below given user story. Don't create any negative test scenarios. Action: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality; Create granular scenarios for each acceptance criteria. Don't give any special characters in the answer.",
        "Boundary & Negative": "Act as an Highly experience Quality Assurance Specialist whose task is to generate negative and boundary test scenarios to thoroughly evaluate the above given userstory's/application's resilience and behavior under stress and edge conditions. The goal is to identify potential failures or unexpected behaviour by testing beyond the normal operational limits and in conditions that are likely to cause errors.; Goal: Focus exclusively on scenarios that challenge the application's robustness, including input, processing, and output boundaries, as well as error handling capabilities. Don't give scenarios that test the positive side of the user story. Generate only 'Test Scenario ID', 'Test Scenario Description','Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario without the quotes. Don't give any special characters in the answer. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality",
        "Buttons Enabled-Disabled": "Role: Highly experience Manual tester.; Task: Identify and create test scenarios focusing solely on button being enabled - disabled functionalities, transitions to new screens, or for completing previous steps wherever applicable and critical based on the description given in user story and/or business requirement (not necessarily at every step), If there are no such functionality mentioned or unrelated to these specific interactions, exclude test scenarios for those parts. Format: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality.",
        "Dropdown-Picklist": "Role: Quality Assurance Engineer; Task: Craft test scenarios exclusively for the identified scope, which involves the dropdown functionality, verification of default values is correctly passed if no selection is made, and pick-list implementation within the system, emphasising its purpose in data management and user interactions. Exclude test scenarios for functionalities not explicitly mentioned within the scope.; Format: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality.",
        "System Architecture": "Role: Experienced Application and system Architect and/or Senior Developer ; Task: Formulate test scenarios that uncover potential weakness in functionality flows . Draft specific scenarios that intricately examine the robustness and resilience of the underlying architectural design while users are navigating over the screens, pages . Take into consideration diverse spectrum of user roles, corresponding functionalities, their relevant application interactions while developing these scenarios. Add scenarios associated with browser backward actions, user session persistence, DB commit.; Generate only 'Test Scenario ID', 'Test Scenario Description','Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario without the quotes. Don't give any special characters in the answer. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality.",
        "Non Functional": "Role: Highly experienced Performance Test Architect; Action: Design comprehensive set of test cases to validate the non functional requirements of the above given user story. Include specific test scenarios for load testing, stress testing, endurance testing by calling out various levels of corresponding concurrent user activity and different workloads. Align the test scenarios to simulate real-world conditions, considering typical expected usage patterns given the context of user story and/or business requirement, associated peak load periods and potential fluctuations in user activities. Present these scenarios in the format given as - generate only 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality. Don't give any special characters in the answer. Strictly give in normal text format.",
        "Combinatorial": "Create all possible test scenarios with expected results for the above user story using combinations of different options available in the story.Action: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality Don't give any special characters in the answer.",
        "Gherkin Functional": "Role: Expert BDD test Automation Engineer Task: Create the positive BDD test scenarios by formulating steps that demonstrate the expected behavior when the user story functionalities are executed successfully Action:1.Understand the provided user story and identify key functionalities and establish acceptance criteria for each functionalities 2.Organize each BDD scenario using Given-When-Then Structure Goal: To craft BDD scenarios from user story. Strictly give 'Test Scenario Name', 'Test Scenario Description' in BDD format. Don't give any special characters in the answer.",
        "Gherkin Boundary & Negative": "Role: Expert BDD Test Automation Engineer Task: Create comprehensive BDD test scenarios that include both negative test cases and scenarios exploring boundary and edge conditions. These scenarios should cover potential failure points, error conditions, and ensure the system behaves robustly in extreme or limit situations, ensuring that all functionalities within the user story are executed successfully.Action: Understand the provided user story and identify key functionalities. Establish acceptance criteria for each functionality.Organize each BDD scenario using the Given-When-Then structure.Goal: To craft both negative and boundary BDD scenarios from the user story,ensuring thorough testing coverage.",
        "Bug Related": "Identity: I am a Quality Assurance Engineer tasked with verifying whether a reported bug still exists and ensuring comprehensive testing around the issue. Task: Please create a detailed test plan to determine if the bug is still present and to test related scenarios. Final Deliverable: please provide The test plan should include specific scenarios mentioned in the bug report as well as general and different scenarios that could be relevant.Format: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality",
        "Patch Related": "Analyze the provided documentation on Operating System (OS) updates during the patching cycle and create a detailed test plan for the below userstory. Action: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Ensure that each scenario is clearly described with specific expected results. In the 'Pre-Condition' column, also specify whether each test scenario is related to the OS Build, OS Patching Process, or other relevant categories. The categories should cover, but are not limited to, Functional Testing and Performance Testing. Also, add test scenarios that address key features, changes, and enhancements mentioned in the documentation."
    }

        prompt = TEST_SCENARIO_PROMPTS.get(scenarioType, "Generate test scenarios for the given user story. Focus on the specific scenario type provided. Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario.Make sure 'Test Scenario ID is in TS01, TS02, etc format.' Don't give any special characters in the answer.") + f"\n\nUser Story: {userstory}"
        # Use retry logic for API call
        if _LLM_PROVIDER == "azure":
            def make_api_call():
                client, deployment = _get_azure_client()
                resp = client.chat.completions.create(model=deployment,messages=[{"role": "user", "content": prompt}],temperature=0.3,top_p=0.95)
                return resp
            api_response = _retry_api_call(make_api_call, max_retries=5)
            response_text = api_response.choices[0].message.content or ""
        else:
            def make_api_call():
                return model.generate_content(prompt, generation_config=GENERATION_CONFIG, safety_settings=SAFETY_SETTINGS)
            api_response = _retry_api_call(make_api_call, max_retries=5)
            if not api_response or not api_response.text:
                raise ValueError("Empty response from model for test scenarios")
            response_text = api_response.text
        
        if not response_text:
            raise ValueError("Empty response from model for test scenarios")
        return response_text
        
    except ValueError as e:
        logger.error(f"Validation error in generate_test_scenarios_from_userstory: {str(e)}")
        return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in generate_test_scenarios_from_userstory: {str(e)}")
        return f"Error generating test scenarios: {str(e)}"

TEST_SCENARIO_PROMPTS = {
    "Functional": "Generate only positive test scenarios (scenarios that validate/verify the positive requirement mentioned) for the below given user story. Don't create any negative test scenarios. Action: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality; Create granular scenarios for each acceptance criteria. Don't give any special characters in the answer.",
    "Boundary & Negative": "Act as an Highly experience Quality Assurance Specialist whose task is to generate negative and boundary test scenarios to thoroughly evaluate the above given userstory's/application's resilience and behavior under stress and edge conditions. The goal is to identify potential failures or unexpected behaviour by testing beyond the normal operational limits and in conditions that are likely to cause errors.; Goal: Focus exclusively on scenarios that challenge the application's robustness, including input, processing, and output boundaries, as well as error handling capabilities. Don't give scenarios that test the positive side of the user story. Generate only 'Test Scenario ID', 'Test Scenario Description','Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario without the quotes. Don't give any special characters in the answer. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality",
    "Buttons Enabled-Disabled": "Role: Highly experience Manual tester.; Task: Identify and create test scenarios focusing solely on button being enabled - disabled functionalities, transitions to new screens, or for completing previous steps wherever applicable and critical based on the description given in user story and/or business requirement (not necessarily at every step), If there are no such functionality mentioned or unrelated to these specific interactions, exclude test scenarios for those parts. Format: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality.",
    "Dropdown-Picklist": "Role: Quality Assurance Engineer; Task: Craft test scenarios exclusively for the identified scope, which involves the dropdown functionality, verification of default values is correctly passed if no selection is made, and pick-list implementation within the system, emphasising its purpose in data management and user interactions. Exclude test scenarios for functionalities not explicitly mentioned within the scope.; Format: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality.",
    "System Architecture": "Role: Experienced Application and system Architect and/or Senior Developer ; Task: Formulate test scenarios that uncover potential weakness in functionality flows . Draft specific scenarios that intricately examine the robustness and resilience of the underlying architectural design while users are navigating over the screens, pages . Take into consideration diverse spectrum of user roles, corresponding functionalities, their relevant application interactions while developing these scenarios. Add scenarios associated with browser backward actions, user session persistence, DB commit.; Generate only 'Test Scenario ID', 'Test Scenario Description','Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario without the quotes. Don't give any special characters in the answer. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality.",
    "Non Functional": "Role: Highly experienced Performance Test Architect; Action: Design comprehensive set of test cases to validate the non functional requirements of the above given user story. Include specific test scenarios for load testing, stress testing, endurance testing by calling out various levels of corresponding concurrent user activity and different workloads. Align the test scenarios to simulate real-world conditions, considering typical expected usage patterns given the context of user story and/or business requirement, associated peak load periods and potential fluctuations in user activities. Present these scenarios in the format given as - generate only 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality. Don't give any special characters in the answer. Strictly give in normal text format.",
    "Combinatorial": "Create all possible test scenarios with expected results for the above user story using combinations of different options available in the story.Action: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality Don't give any special characters in the answer.",
    "Gherkin Functional": "Role: Expert BDD test Automation Engineer Task: Create the positive BDD test scenarios by formulating steps that demonstrate the expected behavior when the user story functionalities are executed successfully Action:1.Understand the provided user story and identify key functionalities and establish acceptance criteria for each functionalities 2.Organize each BDD scenario using Given-When-Then Structure Goal: To craft BDD scenarios from user story. Strictly give 'Test Scenario Name', 'Test Scenario Description' in BDD format. Don't give any special characters in the answer.",
    "Gherkin Boundary & Negative": "Role: Expert BDD Test Automation Engineer Task: Create comprehensive BDD test scenarios that include both negative test cases and scenarios exploring boundary and edge conditions. These scenarios should cover potential failure points, error conditions, and ensure the system behaves robustly in extreme or limit situations, ensuring that all functionalities within the user story are executed successfully.Action: Understand the provided user story and identify key functionalities. Establish acceptance criteria for each functionality.Organize each BDD scenario using the Given-When-Then structure.Goal: To craft both negative and boundary BDD scenarios from the user story,ensuring thorough testing coverage.",
    "Bug Related": "Identity: I am a Quality Assurance Engineer tasked with verifying whether a reported bug still exists and ensuring comprehensive testing around the issue. Task: Please create a detailed test plan to determine if the bug is still present and to test related scenarios. Final Deliverable: please provide The test plan should include specific scenarios mentioned in the bug report as well as general and different scenarios that could be relevant.Format: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Decide the Priority of the scenarios focusing on those that are most critical to the software's functionality and overall quality",
    "Patch Related": "Analyze the provided documentation on Operating System (OS) updates during the patching cycle and create a detailed test plan for the below userstory. Action: Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', 'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. Ensure that each scenario is clearly described with specific expected results. In the 'Pre-Condition' column, also specify whether each test scenario is related to the OS Build, OS Patching Process, or other relevant categories. The categories should cover, but are not limited to, Functional Testing and Performance Testing. Also, add test scenarios that address key features, changes, and enhancements mentioned in the documentation."
}

_DEFAULT_SCENARIO_PROMPT = (
    "Generate test scenarios for the given user story. Focus on the specific scenario type provided. "
    "Strictly give 'Test Scenario ID', 'Test Scenario Description', 'Expected Results', "
    "'Priority(P1,P2,P3..)' and 'Pre-Condition' for each test scenario. "
    "Make sure 'Test Scenario ID' is in TS01, TS02, etc format. "
    "Don't give any special characters in the answer.")

_TEST_CASE_JSON_FORMAT = """
{
    "Test Case ID": "<Test Case ID Number will come here>",
    "Test Case Name": "<Name>",
    "Test Case Description": "<Description>",
    "Steps": [
        {
            "Step Number": "<Step number_1>",
            "Test Case Step": "<Test Case Steps_1>",
            "Expected Results": "<Expected Results_1>"
        }
    ]
}"""

# ===========================================================================
# Utility helpers
# ===========================================================================

def get_scenario_type() -> List[str]:
    logger.debug("Retrieving available scenario types")
    scenario_types = ["Functional", "Non Functional", "Boundary & Negative","Gherkin Functional", "Gherkin Boundary & Negative","Buttons Enabled-Disabled", "Dropdown-Picklist", "System Architecture","Combinatorial", "Bug Related", "Patch Related"]
    logger.debug(f"Scenario types available: {len(scenario_types)} types")
    return scenario_types

def _normalize_multiline(text: str) -> str:
    logger.debug("Normalizing multiline text")
    try:
        if text is None:
            logger.debug("Text is None, returning as-is")
            return text
        t = text.strip()
        if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
            try:
                logger.debug("Attempting to parse quoted JSON")
                return json.loads(t)
            except json.JSONDecodeError:
                logger.warning("Failed to parse quoted JSON, returning normalized text")
        result = text.replace("\\n", "\n").replace("\\t", "\t")
        logger.debug("Text normalized successfully")
        return result
    except Exception as e:
        logger.error(f"Error in _normalize_multiline: {e}")
        return text

def _retry_api_call(func, max_retries: int = 5, initial_delay: int = 2):
    """Retry a callable with exponential backoff for transient SSL / connection errors."""
    logger.debug(f"Starting API call with max_retries={max_retries}, initial_delay={initial_delay}s")
    retryable_keywords = ['SSL', 'Connection', 'timeout', 'Max retries', 'EOF','Timeout', 'RemoteDisconnected', 'closed connection', 'aborted']
    for attempt in range(max_retries):
        try:
            logger.debug(f"API call attempt {attempt + 1}/{max_retries}")
            result = func()
            logger.debug(f"API call succeeded on attempt {attempt + 1}")
            return result
        except Exception as e:
            error_str = str(e)
            is_retryable = any(kw in error_str for kw in retryable_keywords)
            if is_retryable and attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed (retryable): {error_str}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Failed after {attempt + 1} attempts. Error: {error_str}")
                raise

def _llm_generate(prompt: str, temperature_override: Optional[float] = None) -> str:
    """
    Provider-agnostic text generation. Honors LLM_PROVIDER ("google" | "azure").
    Returns response text. Raises on empty response.
    """
    if _LLM_PROVIDER == "azure":
        client, deployment = _get_azure_client()
        gen_temp = temperature_override if temperature_override is not None else GENERATION_CONFIG.get("temperature", 0.3)
        def call_azure():
            return client.chat.completions.create(
                model=deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=gen_temp,
                top_p=GENERATION_CONFIG.get("top_p", 0.95),
            )
        api_response = _retry_api_call(call_azure, max_retries=5)
        text = (api_response.choices[0].message.content or "") if api_response and api_response.choices else ""
        if not text:
            raise ValueError("Empty response from model")
        return text
    else:
        gen_cfg = dict(GENERATION_CONFIG)
        if temperature_override is not None:
            gen_cfg["temperature"] = temperature_override
        def call_google():
            return model.generate_content(prompt, generation_config=gen_cfg, safety_settings=SAFETY_SETTINGS)
        response = _retry_api_call(call_google, max_retries=5)
        if not response or not response.text:
            raise ValueError("Empty response from model")
        return response.text


def _format_llm_error(exc: Exception) -> str:
    """Return a user-facing error string for model/generation failures."""
    msg = str(exc).strip() or exc.__class__.__name__
    lowered = msg.lower()
    timeout_keywords = ("timeout", "timed out", "deadline", "read timed out")
    connection_keywords = ("connection", "ssl", "remote disconnected", "max retries")
    if any(k in lowered for k in timeout_keywords):
        return f"LLM service timeout: {msg}"
    if any(k in lowered for k in connection_keywords):
        return f"LLM connection error: {msg}"
    return f"LLM generation failed: {msg}"

# ===========================================================================
# AI generation
# ===========================================================================

def generate_test_scenarios_from_userstory(userstory: str, scenarioType: str) -> str:
    """Generate test scenarios for a user story. Returns plain text."""
    logger.info(f"Generating test scenarios for scenario type: {scenarioType}")
    logger.debug(f"User story length: {len(userstory)} chars")
    if not userstory or not userstory.strip():
        logger.error("User story is empty or None")
        raise ValueError("User story cannot be empty")
    base_prompt = TEST_SCENARIO_PROMPTS.get(scenarioType, _DEFAULT_SCENARIO_PROMPT)
    logger.debug(f"Using prompt template for scenario type: {scenarioType}")
    prompt = f"{base_prompt}\n\nUser Story: {userstory}"
    try:
        response_text = _llm_generate(prompt)
        logger.info(f"Successfully generated test scenarios (length: {len(response_text)} chars)")
        return response_text
    except Exception as e:
        logger.error(f"Failed to generate test scenarios: {e}", exc_info=True)
        raise


def generate_test_cases(userstory: str, scenarioType: str) -> Dict[str, Any]:
    """
    Generate structured test scenarios + test cases from a user story.
    Returns {"Test Scenarios": <str>, "Test Cases": <str|list>}
    or {"error": <str>} on failure.
    """
    logger.info(f"Starting test case generation for scenario type: {scenarioType}")
    logger.debug(f"User story length: {len(userstory)} chars, scenario type: {scenarioType}")
    try:
        if not userstory or not userstory.strip():
            logger.error("User story is empty or None")
            raise ValueError("User story cannot be empty")
        logger.info("Generating test scenarios as first step...")
        test_scenarios = generate_test_scenarios_from_userstory(userstory, scenarioType)
        logger.debug(f"Test scenarios generated, length: {len(test_scenarios)} chars")
        prompt = (
            f"User Story: {userstory}\n\n"
            "You are a QA assistant. Based on the following test scenarios, generate one detailed test case "
            "for each scenario.\n"
            "Instructions:\n"
            "- For each test scenario provided below, create a single, complete test case that covers detailed "
            "steps by referring to the application flow described in the user story.\n"
            "- Strictly analyze the entire application flow and use only the relevant parts/steps of the flow "
            "to create each test case end-to-end. Do not add redundant or irrelevant steps.\n"
            "- Present all test cases in a **JSON array**, where each element represents one test case.\n"
            "- Each test case must include the following keys:\n"
            '  - "Test Case ID"\n'
            '  - "Test Case Name"\n'
            '  - "Test Case Description"\n'
            '  - "Step Number"\n'
            '  - "Test Case Step"\n'
            '  - "Expected Results"\n'
            "- Ensure that:\n"
            '  - Each "Test Case Name" is concise and captures the essence of the scenario.\n'
            '  - "Expected Results" use future tense (e.g., "should be", "would be").\n'
            "- Return the response **only** in the following JSON format (no extra text, explanations, "
            f"or markdown):\n{_TEST_CASE_JSON_FORMAT}\n\n"
            f"Here are the Test Scenarios: {test_scenarios}"
        )
        logger.debug(f"Prompt created for test case generation, length: {len(prompt)} chars")
        logger.info("Calling model to generate test cases...")
        response_text = _llm_generate(prompt)
        logger.debug(f"Response received from model, length: {len(response_text)} chars")
        matches = re.findall(r"```json(.*?)```", response_text, re.DOTALL)
        response_json = matches[0] if matches else response_text
        logger.info(f"Test cases generated successfully (scenario type: {scenarioType})")
        return {
            "Test Scenarios": _normalize_multiline(test_scenarios),
            "Test Cases": _normalize_multiline(response_json)}
    except ValueError as e:
        logger.error(f"Validation error in generate_test_cases: {e}")
        return {"error": str(e)}
    except Exception as e:
        error_msg = _format_llm_error(e)
        logger.error(f"Unexpected error in generate_test_cases: {error_msg}", exc_info=True)
        return {"error": error_msg}

# ===========================================================================
# Jira / Xray helpers
# ===========================================================================

def get_issue_id_from_key(issue_key: str, jira_cfg: dict):
    """Return the numeric Jira issue ID for a given issue key."""
    logger.debug(f"Fetching numeric ID for Jira issue: {issue_key}")
    url = f"{jira_cfg['base_url'].rstrip('/')}/rest/api/3/issue/{issue_key}"
    try:
        auth = HTTPBasicAuth(jira_cfg["username"], jira_cfg["api_token"])
        response = requests.get(url, headers={"Accept": "application/json"}, auth=auth, verify=False)
        if response.status_code == 200:
            issue_id = response.json().get("id")
            logger.debug(f"Successfully retrieved numeric ID for {issue_key}: {issue_id}")
            return issue_id
        logger.warning(f"Unable to fetch ID for {issue_key}: {response.status_code}")
    except Exception as e:
        logger.error(f"Error fetching issue ID for {issue_key}: {e}", exc_info=True)
    return None

def get_xray_token(client_id: str, client_secret: str) -> str:
    """Authenticate with Xray Cloud and return a bearer token."""
    logger.debug(f"Authenticating with Xray Cloud for client_id: {client_id}")
    try:
        response = requests.post("https://xray.cloud.getxray.app/api/v2/authenticate",headers={"Content-Type": "application/json"},json={"client_id": client_id, "client_secret": client_secret},verify=False)
        response.raise_for_status()
        token = response.json()
        logger.info("Successfully authenticated with Xray Cloud")
        return token.strip('"') if isinstance(token, str) else token
    except Exception as e:
        logger.error(f"Failed to authenticate with Xray Cloud: {e}", exc_info=True)
        raise

def create_tests_in_jira_cloud(jira_story_id: str, test_cases: list, jira_cfg: dict) -> List[str]:
    """Create Jira Test issues for each test case. Returns list of created issue keys (order-preserving)."""
    logger.info(f"Creating {len(test_cases)} Jira Test issues for story {jira_story_id}")
    logger.debug(f"Project key: {jira_cfg['project_key']}, Base URL: {jira_cfg['base_url']}")
    base_url    = jira_cfg["base_url"].rstrip('/')
    auth        = HTTPBasicAuth(jira_cfg["username"], jira_cfg["api_token"])
    project_key = jira_cfg["project_key"]
    headers     = {"Accept": "application/json", "Content-Type": "application/json"}
    def _create_single(idx_tc):
        idx, tc = idx_tc
        name        = tc.get("Test Case Name", "Unnamed Test Case")
        description = tc.get("Test Case Description", "")
        logger.debug(f"Creating Jira test case {idx + 1}/{len(test_cases)}: {name}")
        payload = {
            "fields": {
                "project":     {"key": project_key},
                "summary":     name,
                "description": {
                    "type": "doc", "version": 1,
                    "content": [{"type": "paragraph", "content": [
                        {"type": "text", "text": description or "No description provided."}
                    ]}],
                },
                "issuetype": {"name": "Test"},
                "labels":    [jira_story_id],
            }
        }
        try:
            resp = requests.post(f"{base_url}/rest/api/3/issue", headers=headers, auth=auth, json=payload, verify=False)
            if resp.status_code in (200, 201):
                key = resp.json().get("key")
                logger.info(f"Created Jira Test: {key} - {name}")
                return idx, key
            logger.error(f"Failed to create '{name}': {resp.status_code}")
        except Exception as e:
            logger.error(f"Exception while creating test case '{name}': {e}", exc_info=True)
        return idx, None

    results = [None] * len(test_cases)
    with ThreadPoolExecutor(max_workers=min(10, len(test_cases))) as executor:
        for idx, key in executor.map(_create_single, enumerate(test_cases)):
            if key:
                results[idx] = key
    created = [k for k in results if k is not None]
    logger.info(f"Successfully created {len(created)} out of {len(test_cases)} Jira Test issues")
    return created

def add_test_steps_graphql(issue_id: str, steps: list, token: str, batch_size: int = 10):
    """Add test steps to an Xray Cloud test via GraphQL mutations (batched)."""
    logger.info(f"Adding {len(steps)} test steps to Xray issue {issue_id} (batch_size={batch_size})")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for i in range(0, len(steps), batch_size):
        batch = steps[i:i + batch_size]
        logger.debug(f"Processing batch {i // batch_size + 1}/{(len(steps) + batch_size - 1) // batch_size}")
        mutations = [
            f"""step{idx}: addTestStep(
                issueId: "{issue_id}",
                step: {{
                    action: {json.dumps(step.get("Test Case Step", ""))},
                    data: "",
                    result: {json.dumps(step.get("Expected Results", ""))}
                }}
            ) {{ id action result }}"""
            for idx, step in enumerate(batch)
        ]
        query = "mutation { " + " ".join(mutations) + " }"
        try:
            resp = requests.post(XRAY_GRAPHQL_URL, headers=headers, json={"query": query}, verify=False)
            data = resp.json()
            if "errors" in data:
                logger.warning(f"Batch {i // batch_size + 1} had errors: {data['errors']}")
            else:
                logger.info(f"Successfully added {len(batch)} steps to issue {issue_id} (batch {i // batch_size + 1})")
        except Exception as e:
            logger.error(f"Error adding test steps batch to {issue_id}: {e}", exc_info=True)


def link_tests_to_plan_graphql(plan_issue_id: str, test_issue_ids: List[str], token: str):
    """Link a list of test issue IDs to a test plan via Xray GraphQL."""
    logger.info(f"Linking {len(test_issue_ids)} test cases to test plan {plan_issue_id}")
    logger.debug(f"Test issue IDs: {test_issue_ids}")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    mutation = """
    mutation addTestsToTestPlan($issueId: String!, $testIssueIds: [String!]!) {
        addTestsToTestPlan(issueId: $issueId, testIssueIds: $testIssueIds) {
            addedTests
            warning
        }
    }
    """
    variables = {"issueId": str(plan_issue_id), "testIssueIds": [str(tid) for tid in test_issue_ids]}
    try:
        resp = requests.post(XRAY_GRAPHQL_URL, headers=headers, json={"query": mutation, "variables": variables}, verify=False)
        data = resp.json()
        if "errors" in data:
            logger.error(f"Failed to link tests to plan: {data['errors']}")
        else:
            result = data.get("data", {}).get("addTestsToTestPlan", {})
            logger.info(f"Successfully linked tests to plan. Added: {result.get('addedTests')}, Warning: {result.get('warning')}")
    except Exception as e:
        logger.error(f"Error linking tests to plan: {e}", exc_info=True)

# ===========================================================================
# qTest helpers
# ===========================================================================

def create_test_case_in_qtest(project_id: str, test_case: dict, qtest_cfg: dict) -> Dict[str, Any]:
    """Create a test case in qTest and return a structured result."""
    logger.debug(f"Creating test case in qTest: {test_case.get('Test Case Name', 'Unnamed')}")
    url     = f"{qtest_cfg['base_url']}/projects/{project_id}/test-cases"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {qtest_cfg['token']}"}
    payload = {
        "name":        test_case.get("Test Case Name", "Unnamed Test Case"),
        "description": test_case.get("Test Case Description", ""),
        "properties":  [],
        "parent_id":   None,
        "order":       1,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, verify=False)
        if resp.status_code in (200, 201):
            test_case_id = resp.json().get("id")
            logger.info(f"Created qTest Test Case: {test_case_id} - {payload['name']}")
            return {"success": True, "test_case_id": test_case_id}
        error_text = (resp.text or "").strip()
        logger.error(f"Failed to create qTest test case: {resp.status_code} - {error_text[:300]}")
        return {
            "success": False,
            "error": f"qTest create failed (HTTP {resp.status_code}): {error_text[:300] or 'No response body'}",
        }
    except Exception as e:
        logger.error(f"Exception while creating qTest test case: {e}", exc_info=True)
        return {"success": False, "error": f"qTest create exception: {e}"}


def add_test_steps_in_qtest(project_id: str, test_case_id: str, steps: list, qtest_cfg: dict) -> Dict[str, Any]:
    """Add test steps to a qTest test case and return a structured result."""
    logger.info(f"Adding {len(steps)} test steps to qTest test case {test_case_id}")
    url     = f"{qtest_cfg['base_url']}/projects/{project_id}/test-cases/{test_case_id}/test-steps"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {qtest_cfg['token']}"}
    payload = [
        {"order": i, "description": step.get("Test Case Step", ""), "expected_result": step.get("Expected Results", "")}
        for i, step in enumerate(steps, start=1)
    ]
    try:
        resp = requests.post(url, headers=headers, json=payload, verify=False)
        if resp.status_code in (200, 201):
            logger.info(f"Successfully added {len(steps)} steps to qTest Test Case {test_case_id}")
            return {"success": True}
        else:
            error_text = (resp.text or "").strip()
            logger.error(f"Failed to add steps to qTest test case {test_case_id}: {resp.status_code} - {error_text[:300]}")
            return {
                "success": False,
                "error": f"qTest add steps failed for {test_case_id} (HTTP {resp.status_code}): {error_text[:300] or 'No response body'}",
            }
    except Exception as e:
        logger.error(f"Exception while adding qTest test steps: {e}", exc_info=True)
        return {"success": False, "error": f"qTest add steps exception for {test_case_id}: {e}"}

# ===========================================================================
# Core bulk-job processing logic
# (Shared by api_server.py — no FastAPI / HTTP imports here)
# ===========================================================================

def process_single_story_jira(jira_story_id: str, userstory: str, scenario_type: str) -> Dict[str, Any]:
    """
    Generate test cases for one story + scenario type, then push to Jira/Xray.
    Returns a result dict. Raises RuntimeError on any unrecoverable failure.
    """
    logger.info(f"Processing story {jira_story_id} for scenario type '{scenario_type}' (Jira/Xray)")
    logger.debug(f"User story length: {len(userstory)} chars")
    result = generate_test_cases(userstory=userstory, scenarioType=scenario_type)
    if result is None or "error" in result:
        error_msg = f"Test case generation failed: {result.get('error', 'Unknown error')}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    test_cases_raw = result.get("Test Cases")
    test_cases = json.loads(test_cases_raw) if isinstance(test_cases_raw, str) else test_cases_raw
    if not isinstance(test_cases, list) or not test_cases:
        raise RuntimeError("Test case generation failed: model returned empty or invalid test case list")
    total_generated = len(test_cases)
    logger.info(f"Generated {len(test_cases)} test cases. Pushing to Jira for story {jira_story_id}...")
    created_keys = create_tests_in_jira_cloud(jira_story_id, test_cases, jira_config)
    if not created_keys:
        error_msg = f"Jira push failed: 0/{total_generated} test cases created"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    push_errors: List[str] = []
    if len(created_keys) < total_generated:
        push_errors.append(f"Jira push partially failed: created {len(created_keys)}/{total_generated} test cases")
    logger.debug(f"Created {len(created_keys)} Jira test keys. Fetching Xray token and test plan ID...")
    # Fetch Xray token and test-plan numeric ID concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        token_future   = executor.submit(get_xray_token, xray_config["client_id"], xray_config["client_secret"])
        plan_id_future = executor.submit(get_issue_id_from_key, TEST_PLAN_KEY, jira_config)
        token          = token_future.result()
        plan_numeric_id = plan_id_future.result()
    if not token:
        error_msg = "Failed to obtain Xray authentication token"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    if not plan_numeric_id:
        error_msg = f"Failed to resolve numeric ID for test plan {TEST_PLAN_KEY}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    logger.debug(f"Xray token obtained, test plan ID: {plan_numeric_id}")
    def _enrich_test(args):
        i, key = args
        numeric_id = get_issue_id_from_key(key, jira_config)
        if not numeric_id:
            logger.warning(f"Skipping {key}: could not resolve numeric ID")
            push_errors.append(f"Failed to resolve Jira numeric issue id for {key}")
            return None
        steps = test_cases[i]["Steps"] if i < len(test_cases) else test_cases[0]["Steps"]
        add_test_steps_graphql(numeric_id, steps, token)
        return {
            "test_key":       key,
            "test_id":        numeric_id,
            "jira_link":      f"{jira_config['base_url'].rstrip('/')}/browse/{key}",
            "test_case_name": test_cases[i].get("Test Case Name", "Unnamed Test Case"),
        }

    test_details     = []
    numeric_test_ids = []
    with ThreadPoolExecutor(max_workers=min(10, len(created_keys))) as executor:
        for detail in executor.map(_enrich_test, enumerate(created_keys)):
            if detail:
                test_details.append(detail)
                numeric_test_ids.append(detail["test_id"])

    if not test_details:
        error_msg = "Failed to retrieve Jira issue IDs for created tests"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    logger.info(f"Adding test details to {len(numeric_test_ids)} tests and linking to test plan...")
    link_tests_to_plan_graphql(plan_numeric_id, numeric_test_ids, token)
    logger.info(f"Successfully completed processing for story {jira_story_id} - {len(test_details)} tests created")
    overall_status = "passed" if not push_errors else "partial_passed"
    return {
        "overall_status":          overall_status,
        "scenario_type":           scenario_type,
        "generated_test_scenarios": result.get("Test Scenarios"),
        "generated_test_cases":    test_cases,
        "jira_push_result": {
            "created_tests":      test_details,
            "linked_plan":        TEST_PLAN_KEY,
            "total_tests_created": len(test_details),
            "errors":             push_errors,
        },
    }


def process_single_story_qtest(userstory: str, scenario_type: str) -> Dict[str, Any]:
    """
    Generate test cases for one story + scenario type, then push to qTest.
    Returns a result dict. Raises RuntimeError on any unrecoverable failure.
    """
    logger.info(f"Processing story for scenario type '{scenario_type}' (qTest)")
    logger.debug(f"User story length: {len(userstory)} chars")
    result = generate_test_cases(userstory=userstory, scenarioType=scenario_type)
    if result is None or "error" in result:
        error_msg = f"Test case generation failed: {result.get('error', 'Unknown error')}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    test_cases_raw = result.get("Test Cases")
    test_cases = json.loads(test_cases_raw) if isinstance(test_cases_raw, str) else test_cases_raw
    if not isinstance(test_cases, list) or not test_cases:
        raise RuntimeError("Test case generation failed: model returned empty or invalid test case list")
    logger.info(f"Generated {len(test_cases)} test cases. Creating in qTest...")
    created_tests = []
    push_errors: List[str] = []
    for tc in test_cases:
        logger.debug(f"Creating test case in qTest: {tc.get('Test Case Name', 'Unnamed')}")
        create_result = create_test_case_in_qtest(qtest_config["project_id"], tc, qtest_config)
        if create_result.get("success"):
            test_case_id = create_result.get("test_case_id")
            steps_result = add_test_steps_in_qtest(qtest_config["project_id"], test_case_id, tc.get("Steps", []), qtest_config)
            if not steps_result.get("success"):
                push_errors.append(steps_result.get("error", f"Failed to add steps for qTest test case {test_case_id}"))
            created_tests.append({
                "test_case_id":   test_case_id,
                "test_case_name": tc.get("Test Case Name", ""),
                "qtest_link": (
                    f"{qtest_config['base_url'].replace('/api/v3', '')}"
                    f"/p/{qtest_config['project_id']}/testcase/{test_case_id}"
                ),
            })
        else:
            push_errors.append(create_result.get("error", f"Failed to create qTest test case '{tc.get('Test Case Name', 'Unnamed')}'"))

    total_generated = len(test_cases)
    if not created_tests:
        err_msg = f"qTest push failed: 0/{total_generated} test cases created. Errors: {' | '.join(push_errors[:3])}"
        logger.error(err_msg)
        raise RuntimeError(err_msg)

    if len(created_tests) < total_generated:
        push_errors.append(f"qTest push partially failed: created {len(created_tests)}/{total_generated} test cases")

    overall_status = "passed" if not push_errors else "partial_passed"

    logger.info(f"Successfully completed qTest processing - {len(created_tests)} tests created")
    return {
        "overall_status": overall_status,
        "scenario_type": scenario_type,
        "generated_test_scenarios": result.get("Test Scenarios"),
        "generated_test_cases": test_cases,
        "qtest_push_result": {
            "created_tests": created_tests,
            "total_tests_created": len(created_tests),
            "errors": push_errors,
        }}

def update_story_status(job_store: dict, jobs_lock: threading.Lock, job_id: str, index: int, scenario_types: List[str]):
    """
    Recompute and set the story-level status from its per-scenario results.
    Must be called while holding jobs_lock.
    Possible story statuses:
        pending         - no scenarios started yet
        processing      - at least one running, not all done
        passed          - all scenarios passed
        failed          - all scenarios failed
        partial_passed  - mix of passed/failed states
    """
    logger.debug(f"Updating story status for job {job_id}, story index {index}")
    story    = job_store[job_id]["stories"][index]
    results  = story["results_by_scenario"]
    statuses = [results[st]["status"] for st in scenario_types if st in results]
    done     = sum(1 for s in statuses if s in ("passed", "partial_passed", "failed"))
    if done == 0:
        new_status = "pending"
    elif done < len(scenario_types):
        new_status = "processing"
    elif all(s == "passed" for s in statuses):
        new_status = "passed"
    elif all(s == "failed" for s in statuses):
        new_status = "failed"
    else:
        new_status = "partial_passed"
    logger.debug(f"Story status updated to: {new_status} (done={done}/{len(scenario_types)})")
    story["status"] = new_status


# ── Azure DevOps integration ─────────────────────────────────────────────────

ado_config = {
    "org_url": os.getenv("AZURE_DEVOPS_ORG_URL", ""),
    "project": os.getenv("AZURE_DEVOPS_PROJECT", ""),
    "pat": os.getenv("AZURE_DEVOPS_PAT", ""),
}


def _ado_auth_header(pat: str) -> dict:
    """Build Basic auth header for Azure DevOps REST API."""
    import base64 as b64
    token = b64.b64encode(f":{pat}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json-patch+json",
    }


def _build_test_steps_xml(steps: list) -> str:
    """Convert test case steps to XML format expected by ADO TCM.Steps field."""
    xml_parts = ['<steps id="0" last="{}">'.format(len(steps))]
    for i, step in enumerate(steps, start=1):
        action = step.get("Test Case Step", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        expected = step.get("Expected Results", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        xml_parts.append(
            f'<step id="{i}" type="ValidateStep">'
            f'<parameterizedString isFormatted="true">{action}</parameterizedString>'
            f'<parameterizedString isFormatted="true">{expected}</parameterizedString>'
            f'</step>'
        )
    xml_parts.append('</steps>')
    return ''.join(xml_parts)


def _coerce_ado_id(value) -> int | None:
    """Best-effort conversion of an ADO id like '#2210', '2210', or 2210 to int."""
    if value is None:
        return None
    try:
        return int(str(value).strip().lstrip("#"))
    except (TypeError, ValueError):
        return None


def create_test_case_in_ado(
    test_case: dict,
    ado_cfg: dict,
    user_story_id: str | int | None = None,
) -> dict | None:
    """Create a Test Case work item in Azure DevOps with test steps.

    When ``user_story_id`` is provided, the test case is linked back to that
    user story via a ``Microsoft.VSTS.Common.TestedBy-Reverse`` relation, so
    the test case appears nested under the user story in the ADO UI.
    """
    org_url = ado_cfg["org_url"].rstrip("/")
    project = ado_cfg["project"]
    pat = ado_cfg["pat"]

    if not all([org_url, project, pat]):
        logger.error("Azure DevOps config incomplete (AZURE_DEVOPS_ORG_URL, AZURE_DEVOPS_PROJECT, AZURE_DEVOPS_PAT)")
        return None

    url = f"{org_url}/{project}/_apis/wit/workitems/$Test%20Case?api-version=7.1"
    headers = _ado_auth_header(pat)

    tc_name = test_case.get("Test Case Name", "Unnamed Test Case")
    tc_desc = test_case.get("Test Case Description", "")
    steps = test_case.get("Steps", [])
    steps_xml = _build_test_steps_xml(steps) if steps else ""

    payload = [
        {"op": "add", "path": "/fields/System.Title", "value": tc_name},
        {"op": "add", "path": "/fields/System.Description", "value": tc_desc},
    ]
    if steps_xml:
        payload.append({"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": steps_xml})

    parent_id = _coerce_ado_id(user_story_id)
    if parent_id is not None:
        payload.append({
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "Microsoft.VSTS.Common.TestedBy-Reverse",
                "url": f"{org_url}/{project}/_apis/wit/workItems/{parent_id}",
                "attributes": {"comment": "Auto-linked from user story to test case"},
            },
        })

    response = requests.post(url, headers=headers, json=payload, verify=False)
    if response.status_code in [200, 201]:
        data = response.json()
        work_item_id = data.get("id")
        if parent_id is not None:
            logger.info(
                f"Created ADO Test Case: {work_item_id} - {tc_name} (linked to user story {parent_id})"
            )
        else:
            logger.info(f"Created ADO Test Case: {work_item_id} - {tc_name} (no parent link)")
        return {
            "work_item_id": work_item_id,
            "test_case_name": tc_name,
            "ado_link": f"{org_url}/{project}/_workitems/edit/{work_item_id}",
        }
    else:
        logger.error(f"Failed to create ADO test case '{tc_name}': {response.status_code} - {response.text}")
        return None

def run_bulk_job_jira(job_id: str, stories: list, scenario_types: List[str], job_store: dict, jobs_lock: threading.Lock):
    """
    Process all (story x scenario_type) combinations concurrently and push to Jira/Xray.
    Updates job_store in place. Designed to be run in a background thread.
    """
    logger.info(f"Starting bulk Jira job {job_id} with {len(stories)} stories and {len(scenario_types)} scenario types")
    logger.debug(f"Total tasks to process: {len(stories) * len(scenario_types)}")
    def _process(index: int, story, scenario_type: str):
        logger.debug(f"[job={job_id}] Processing story {index + 1}/{len(stories)}: {story.userStoryJiraId}/{scenario_type}")
        with jobs_lock:
            job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {"status": "processing"}
            update_story_status(job_store, jobs_lock, job_id, index, scenario_types)
        try:
            logger.debug(f"Calling process_single_story_jira for {story.userStoryJiraId}/{scenario_type}")
            story_result = process_single_story_jira(jira_story_id=story.userStoryJiraId,userstory=story.userStory,scenario_type=scenario_type)
            scenario_status = story_result.get("overall_status", "passed")
            with jobs_lock:
                job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {
                    "status": scenario_status,
                    "result": story_result,
                }
                if scenario_status in ("passed", "partial_passed"):
                    job_store[job_id]["completed_count"] += 1
                update_story_status(job_store, jobs_lock, job_id, index, scenario_types)
            logger.info(f"[job={job_id}] Story {story.userStoryJiraId}/{scenario_type} completed successfully")
        except Exception as e:
            logger.error(f"[job={job_id}] story {story.userStoryJiraId} / {scenario_type} failed: {e}", exc_info=True)
            with jobs_lock:
                job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {
                    "status": "failed",
                    "error":  str(e),
                }
                job_store[job_id]["failed_count"] += 1
                update_story_status(job_store, jobs_lock, job_id, index, scenario_types)

    with jobs_lock:
        job_store[job_id]["status"] = "processing"
        logger.info(f"Job {job_id} status set to 'processing'")
    tasks = [(i, story, st) for i, story in enumerate(stories) for st in scenario_types]
    with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as executor:
        for future in as_completed([executor.submit(_process, i, s, t) for i, s, t in tasks]):
            future.result()

    _finalise_job(job_id, stories, scenario_types, job_store, jobs_lock)
    logger.info(f"[job={job_id}] Jira bulk job done. "
                f"completed={job_store[job_id]['completed_count']} "
                f"failed={job_store[job_id]['failed_count']}")

def run_bulk_job_qtest(job_id: str, stories: list, scenario_types: List[str], job_store: dict, jobs_lock: threading.Lock):
    """
    Process all (story x scenario_type) combinations concurrently and push to qTest.
    Updates job_store in place. Designed to be run in a background thread.
    """
    logger.info(f"Starting bulk qTest job {job_id} with {len(stories)} stories and {len(scenario_types)} scenario types")
    logger.debug(f"Total tasks to process: {len(stories) * len(scenario_types)}")
    def _process(index: int, story, scenario_type: str):
        logger.debug(f"[job={job_id}] Processing story {index + 1}/{len(stories)}: {scenario_type}")
        with jobs_lock:
            job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {"status": "processing"}
            update_story_status(job_store, jobs_lock, job_id, index, scenario_types)
        try:
            logger.debug(f"Calling process_single_story_qtest for {scenario_type}")
            story_result = process_single_story_qtest(userstory=story.userStory,scenario_type=scenario_type)
            scenario_status = story_result.get("overall_status", "passed")
            with jobs_lock:
                job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {
                    "status": scenario_status,
                    "result": story_result,
                }
                if scenario_status in ("passed", "partial_passed"):
                    job_store[job_id]["completed_count"] += 1
                update_story_status(job_store, jobs_lock, job_id, index, scenario_types)
            logger.info(f"[job={job_id}] Story {story.userStoryJiraId}/{scenario_type} completed successfully")
        except Exception as e:
            logger.error(f"[job={job_id}] story {story.userStoryJiraId} / {scenario_type} failed: {e}", exc_info=True)
            with jobs_lock:
                job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {
                    "status": "failed",
                    "error":  str(e),
                }
                job_store[job_id]["failed_count"] += 1
                update_story_status(job_store, jobs_lock, job_id, index, scenario_types)

    with jobs_lock:
        job_store[job_id]["status"] = "processing"
        logger.info(f"Job {job_id} status set to 'processing'")

    tasks = [(i, story, st) for i, story in enumerate(stories) for st in scenario_types]
    with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as executor:
        for future in as_completed([executor.submit(_process, i, s, t) for i, s, t in tasks]):
            future.result()
    _finalise_job(job_id, stories, scenario_types, job_store, jobs_lock)
    logger.info(f"[job={job_id}] qTest bulk job done. "
                f"completed={job_store[job_id]['completed_count']} "
                f"failed={job_store[job_id]['failed_count']}")

def run_bulk_job_ado(job_id: str, stories: list, scenario_types: List[str], job_store: dict, jobs_lock: threading.Lock):
    """
    Process all (story x scenario_type) combinations concurrently and push to Azure DevOps.
    Updates job_store in place. Designed to be run in a background thread.
    """
    logger.info(f"Starting bulk ADO job {job_id} with {len(stories)} stories and {len(scenario_types)} scenario types")
    logger.debug(f"Total tasks to process: {len(stories) * len(scenario_types)}")

    def _process(index: int, story, scenario_type: str):
        logger.debug(f"[job={job_id}] Processing story {index + 1}/{len(stories)}: {story.userStoryJiraId}/{scenario_type}")
        with jobs_lock:
            job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {"status": "processing"}

        try:
            result = generate_test_cases(userstory=story.userStory, scenarioType=scenario_type)
            if result is None or "error" in result:
                raise RuntimeError(f"Test case generation failed: {result.get('error', 'Unknown error')}")

            test_cases_raw = result.get("Test Cases")
            test_cases = json.loads(test_cases_raw) if isinstance(test_cases_raw, str) else test_cases_raw
            if not isinstance(test_cases, list) or not test_cases:
                raise RuntimeError("Test case generation failed: model returned empty or invalid test case list")

            created_tests = []
            push_errors: List[str] = []
            for tc in test_cases:
                ado_result = create_test_case_in_ado(tc, ado_config, user_story_id=story.userStoryJiraId)
                if ado_result:
                    created_tests.append(ado_result)
                else:
                    push_errors.append(f"Failed to create ADO test case '{tc.get('Test Case Name', 'Unnamed Test Case')}'")

            total_generated = len(test_cases)
            if not created_tests:
                raise RuntimeError(f"ADO push failed: 0/{total_generated} test cases created. Errors: {' | '.join(push_errors[:3])}")
            if len(created_tests) < total_generated:
                push_errors.append(f"ADO push partially failed: created {len(created_tests)}/{total_generated} test cases")
            overall_status = "passed" if not push_errors else "partial_passed"

            with jobs_lock:
                job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {
                    "status": overall_status,
                    "result": {
                        "overall_status": overall_status,
                        "scenario_type": scenario_type,
                        "generated_test_scenarios": result.get("Test Scenarios"),
                        "generated_test_cases": test_cases,
                        "ado_push_result": {
                            "created_tests": created_tests,
                            "total_tests_created": len(created_tests),
                            "errors": push_errors,
                        },
                    },
                }
                if overall_status in ("passed", "partial_passed"):
                    job_store[job_id]["completed_count"] += 1
                update_story_status(job_store, jobs_lock, job_id, index, scenario_types)
        except Exception as e:
            logger.error(f"[job={job_id}] story {story.userStoryJiraId} / {scenario_type} failed: {e}", exc_info=True)
            with jobs_lock:
                job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {
                    "status": "failed",
                    "error": str(e),
                }
                job_store[job_id]["failed_count"] += 1
                update_story_status(job_store, jobs_lock, job_id, index, scenario_types)

    with jobs_lock:
        job_store[job_id]["status"] = "processing"
        logger.info(f"Job {job_id} status set to 'processing'")

    tasks = [(i, story, st) for i, story in enumerate(stories) for st in scenario_types]
    with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as executor:
        for future in as_completed([executor.submit(_process, i, s, t) for i, s, t in tasks]):
            future.result()

    _finalise_job(job_id, stories, scenario_types, job_store, jobs_lock)
    logger.info(f"[job={job_id}] ADO bulk job done. "
                f"completed={job_store[job_id]['completed_count']} "
                f"failed={job_store[job_id]['failed_count']}")

def _finalise_job(job_id: str, stories: list, scenario_types: List[str], job_store: dict, jobs_lock: threading.Lock):
    """Set final job-level status and completion timestamp from story-level results."""
    logger.info(f"Finalizing job {job_id}...")
    from datetime import datetime
    with jobs_lock:
        job = job_store[job_id]
        total_stories = len(stories)
        passed_stories = failed_stories = partial_stories = processing_stories = 0

        for story in job["stories"]:
            story_status = story.get("status")
            if story_status == "passed":
                passed_stories += 1
            elif story_status == "failed":
                failed_stories += 1
            elif story_status == "partial_passed":
                partial_stories += 1
            else:
                processing_stories += 1

        job["completed_count"] = passed_stories
        job["failed_count"] = failed_stories

        if processing_stories > 0:
            job["status"] = "processing"
        elif passed_stories == total_stories:
            job["status"] = "passed"
        elif failed_stories == total_stories:
            job["status"] = "failed"
        else:
            job["status"] = "partial_passed"

        job["completed_at"] = datetime.utcnow().isoformat() + "Z"
        logger.info(
            f"Job {job_id} finalized. Final status: {job['status']} "
            f"(passed={passed_stories}, partial={partial_stories}, failed={failed_stories}, processing={processing_stories})"
        )


# ===========================================================================
# ──────────────────────────────────────────────────────────────────────────
# BROWNFIELD  –  Fetch → Analyse → Update / Create
# ──────────────────────────────────────────────────────────────────────────
# ===========================================================================

# ---------------------------------------------------------------------------
# Step 1 – Pull existing test cases from Jira by label (= userStoryJiraId)
# ---------------------------------------------------------------------------

def _parse_issues_from_jira_response(raw_issues: list) -> List[Dict[str, Any]]:
    """
    Shared parser for Jira search responses (both v2 and v3).
    Converts raw issue dicts into {key, id, summary, description}.
    """
    results: List[Dict[str, Any]] = []
    for issue in raw_issues:
        fields = issue.get("fields", {})
        # Extract plain text from Atlassian Document Format (ADF) description if present
        description = ""
        raw_desc = fields.get("description")
        if raw_desc and isinstance(raw_desc, dict):
            # ADF format (REST v3)
            try:
                description = " ".join(
                    node.get("text", "")
                    for block in raw_desc.get("content", [])
                    for node in block.get("content", [])
                    if node.get("type") == "text"
                )
            except Exception:
                description = str(raw_desc)
        elif isinstance(raw_desc, str):
            # Plain text / wiki markup (REST v2)
            description = raw_desc
        results.append({
            "key":         issue["key"],
            "id":          issue["id"],
            "summary":     fields.get("summary", ""),
            "description": description,
        })
    return results


def fetch_existing_test_cases_by_label(jira_story_id: str, jira_cfg: dict) -> List[Dict[str, Any]]:
    """
    Query Jira for all Test issues whose label matches jira_story_id.
    Returns a list of dicts: [{key, id, summary, description}, ...]

    Strategy (tried in order):
      1. POST /rest/api/3/search/jql  – new Atlassian Cloud endpoint (2024+)
      2. GET  /rest/api/2/search      – classic endpoint, still active on most instances
    """
    base_url = jira_cfg["base_url"].rstrip("/")
    auth     = HTTPBasicAuth(jira_cfg["username"], jira_cfg["api_token"])
    jql      = f'issuetype = Test AND labels = "{jira_story_id}" ORDER BY created ASC'

    # ── Attempt 1: POST /rest/api/3/search/jql ────────────────────────────
    # The new endpoint only accepts: jql, maxResults, nextPageToken, fields,
    # expand, properties, fieldsByKeys.  No "startAt".
    try:
        payload_v3 = {"jql":jql,"maxResults": 200,"fields":["summary", "description", "labels"]}
        resp = requests.post(f"{base_url}/rest/api/3/search/jql",headers={"Accept": "application/json", "Content-Type": "application/json"},auth=auth,json=payload_v3,verify=False)
        if resp.status_code == 200:
            issues = resp.json().get("issues", [])
            results = _parse_issues_from_jira_response(issues)
            logger.info(f"[v3/search/jql] Fetched {len(results)} test cases for label '{jira_story_id}'")
            return results
        logger.warning(f"POST /rest/api/3/search/jql returned {resp.status_code}: {resp.text[:300]}. Falling back to GET /rest/api/2/search.")
    except Exception as exc:
        logger.warning(f"POST /rest/api/3/search/jql raised {exc}. Falling back to GET /rest/api/2/search.")

    # ── Attempt 2: GET /rest/api/2/search (classic, still supported) ──────
    try:
        params_v2 = {"jql": jql,"fields": "summary,description,labels","maxResults": 200,"startAt":    0}
        resp = requests.get(f"{base_url}/rest/api/2/search",headers={"Accept": "application/json"},auth=auth,params=params_v2,verify=False)
        if resp.status_code == 200:
            issues = resp.json().get("issues", [])
            results = _parse_issues_from_jira_response(issues)
            logger.info(f"[v2/search] Fetched {len(results)} test cases for label '{jira_story_id}'")
            return results
        logger.error(f"GET /rest/api/2/search also failed ({resp.status_code}): {resp.text[:300]}")
    except Exception as exc:
        logger.error(f"GET /rest/api/2/search raised {exc}")
    return []

# ---------------------------------------------------------------------------
# Step 2 – Pull existing Xray steps for a single test issue (GraphQL)
# ---------------------------------------------------------------------------

# Ordered list of GraphQL query strategies for fetching test steps.
# Xray Cloud schema varies by tenant version; we try each until one succeeds.
# Cache the discovered step field name per token so introspection runs once.
_xray_step_field_cache: Dict[str, str] = {}   # token → "testSteps" | "steps"
_xray_remove_step_arg_cache: Dict[str, str] = {}  # token → "stepId" | "id"
_xray_remove_step_issue_arg_cache: Dict[str, Optional[str]] = {}  # token → "issueId" | None
_xray_remove_step_return_cache: Dict[str, Optional[str]] = {}  # token → return field name | None for scalar returns


def _introspect_xray_schema(token: str):
    """
    Run a single GraphQL introspection query that discovers:
      1. The step field name on the Test type  ('testSteps' or 'steps')
      2. The arg name for removeTestStep       ('stepId' or 'id')
    3. Whether removeTestStep accepts issueId
    4. The return field name of removeTestStep (used in mutation selection set)

    Results are cached by token so introspection only runs once per session.
    """
    if token in _xray_step_field_cache:
        return _xray_step_field_cache[token]

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    introspect_query = """
    {
        testType: __type(name: "Test") {
            fields { name }
        }
        mutationType: __type(name: "Mutation") {
            fields {
                name
                args { name }
                type {
                    name
                    kind
                    ofType { name kind }
                }
            }
        }
    }
    """
    try:
        resp = requests.post(
            XRAY_GRAPHQL_URL,
            headers=headers,
            json={"query": introspect_query},
            verify=False,
            timeout=10,
        )
        data = resp.json().get("data", {})

        # ── Step field on Test type ──────────────────────────────────────────
        test_fields = [
            f["name"]
            for f in (data.get("testType") or {}).get("fields", [])
        ]
        logger.info(f"Xray Test type fields: {test_fields}")
        if "testSteps" in test_fields:
            step_field = "testSteps"
        elif "steps" in test_fields:
            step_field = "steps"
        else:
            logger.warning(f"Step field not found, defaulting to 'steps'. Available: {test_fields}")
            step_field = "steps"

        # ── removeTestStep mutation args + return type ───────────────────────
        mutation_fields = (data.get("mutationType") or {}).get("fields", [])
        remove_mutation = next(
            (f for f in mutation_fields if f["name"] == "removeTestStep"), None
        )

        if remove_mutation:
            arg_names = [a["name"] for a in remove_mutation.get("args", [])]
            logger.info(f"removeTestStep args: {arg_names}")

            # Determine the step-id argument name
            if "stepId" in arg_names:
                remove_arg = "stepId"
            elif "id" in arg_names:
                remove_arg = "id"
            else:
                remove_arg = "stepId"   # safe default
                logger.warning(f"Unknown removeTestStep args {arg_names}, defaulting to stepId")

            # Some tenants require only the step identifier for deletion.
            remove_issue_arg = "issueId" if "issueId" in arg_names else None

            # Determine whether the mutation returns a scalar or an object.
            ret_type = remove_mutation.get("type", {})
            # unwrap NonNull / List wrappers
            while ret_type.get("kind") in ("NON_NULL", "LIST"):
                ret_type = ret_type.get("ofType") or {}
            ret_type_kind = ret_type.get("kind", "")
            ret_type_name = ret_type.get("name", "")
            if ret_type_kind == "SCALAR":
                ret_field = None
            else:
                # introspect the return type's fields to pick a safe scalar
                ret_field = _introspect_return_field(token, ret_type_name, headers)
        else:
            logger.warning("removeTestStep not found in Mutation type, using defaults")
            remove_arg = "stepId"
            remove_issue_arg = None
            ret_field = None

    except Exception as exc:
        logger.warning(f"Schema introspection failed: {exc}. Using defaults.")
        step_field = "steps"
        remove_arg = "stepId"
        remove_issue_arg = None
        ret_field = None

    _xray_step_field_cache[token]        = step_field
    _xray_remove_step_arg_cache[token]   = remove_arg
    _xray_remove_step_issue_arg_cache[token] = remove_issue_arg
    _xray_remove_step_return_cache[token] = ret_field

    logger.info(
        f"Xray schema resolved — step_field='{step_field}', "
        f"remove_arg='{remove_arg}', issue_arg='{remove_issue_arg}', return_field='{ret_field}'"
    )


def _introspect_return_field(token: str, type_name: str, headers: dict) -> Optional[str]:
    """
    Introspect a GraphQL type by name and return the name of the first
    scalar field suitable for use in a mutation selection set.
    Returns None for scalar/no-field types or if anything goes wrong.
    """
    if not type_name:
        return None
    query = """
    query($name: String!) {
        __type(name: $name) {
            fields { name type { kind } }
        }
    }
    """
    try:
        resp = requests.post(
            XRAY_GRAPHQL_URL,
            headers=headers,
            json={"query": query, "variables": {"name": type_name}},
            verify=False,
            timeout=10,
        )
        fields = (
            (resp.json().get("data", {}).get("__type") or {}).get("fields", [])
        )
        scalar_names = [
            f["name"] for f in fields
            if (f.get("type") or {}).get("kind") == "SCALAR"
        ]
        logger.info(f"Return type '{type_name}' scalar fields: {scalar_names}")
        # Prefer issueId > id > first scalar
        for preferred in ("issueId", "id"):
            if preferred in scalar_names:
                return preferred
        return scalar_names[0] if scalar_names else None
    except Exception as exc:
        logger.warning(f"Return type introspection failed: {exc}")
        return None


def _discover_step_field(token: str) -> str:
    """Return the step field name for this Xray tenant ('testSteps' or 'steps')."""
    _introspect_xray_schema(token)
    return _xray_step_field_cache.get(token, "steps")


def _discover_remove_args(token: str) -> tuple:
    """Return (step_id_arg_name, issue_id_arg_name, return_field_name) for removeTestStep mutation."""
    _introspect_xray_schema(token)
    return (
        _xray_remove_step_arg_cache.get(token, "stepId"),
        _xray_remove_step_issue_arg_cache.get(token),
        _xray_remove_step_return_cache.get(token),
    )


def fetch_test_steps_graphql(issue_id: str, token: str) -> List[Dict[str, Any]]:
    """
    Retrieve Xray test steps for a single test issue via GraphQL.
    Returns a list of dicts: {id, action, data, result}

    Discovers the correct field name ('testSteps' or 'steps') via schema
    introspection (cached) so it works across all Xray Cloud tenant versions.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    step_field = _discover_step_field(token)

    # Build query dynamically using the discovered field name
    query = f"""
    query($issueId: String!) {{
        getTest(issueId: $issueId) {{
            issueId
            {step_field} {{
            id
            action
            data
            result
            }}
        }}
    }}
    """
    resp = requests.post(XRAY_GRAPHQL_URL,headers=headers,json={"query": query, "variables": {"issueId": issue_id}},verify=False)
    data = resp.json()
    if "errors" in data:
        logger.warning(f"GraphQL errors fetching steps for {issue_id}: {data['errors']}")
        return []
    test_obj = (data.get("data") or {}).get("getTest") or {}
    steps = test_obj.get(step_field) or []

    # Handle paginated response shape: { results: [...] }
    if isinstance(steps, dict):
        steps = steps.get("results") or []

    logger.info(f"Fetched {len(steps)} steps for issue {issue_id}")
    return steps

# ---------------------------------------------------------------------------
# Step 3 – Delete all Xray steps for an issue so we can write fresh ones
# ---------------------------------------------------------------------------

def delete_all_test_steps_graphql(issue_id: str, token: str):
    """
    Delete every existing Xray step for issue_id before writing updated ones.

    Uses _introspect_xray_schema() to discover:
      - the correct step-id argument name for removeTestStep (stepId or id)
      - the correct return field for the mutation selection set
    Both are cached after the first call so no repeated introspection occurs.
    """
    steps = fetch_test_steps_graphql(issue_id, token)
    valid_steps = [s for s in steps if s.get("id")]
    if not valid_steps:
        logger.info(f"No existing steps to delete for issue {issue_id}")
        return

    remove_arg, remove_issue_arg, ret_field = _discover_remove_args(token)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Build a single batched mutation using the introspected arg + return field
    issue_id_fragment = f'issueId: "{issue_id}", ' if remove_issue_arg else ""
    selection_set = f" {{ {ret_field} }}" if ret_field else ""
    mutations = [
	        f'del{idx}: removeTestStep({issue_id_fragment}{remove_arg}: "{step["id"]}"){selection_set}'
            for idx, step in enumerate(valid_steps)
        ]
    query = "mutation { " + " ".join(mutations) + " }"
    logger.debug(
        "Delete mutation — issueId=%s issueArg=%s arg=%s stepId=%s return=%s",
        issue_id,
        remove_issue_arg,
        remove_arg,
        valid_steps[0]["id"],
        ret_field,
    )

    resp  = requests.post(XRAY_GRAPHQL_URL, headers=headers, json={"query": query}, verify=False)
    data  = resp.json()

    if "errors" in data:
        msgs = [e.get("message", "") for e in data["errors"]]
        logger.error(
            f"removeTestStep failed for issue {issue_id} "
            f"(arg={remove_arg}, return={ret_field}): {msgs}\n"
            "Clearing schema cache so introspection retries on next call."
        )
        # Bust the cache so the next call re-introspects (schema may have changed)
        _xray_step_field_cache.pop(token, None)
        _xray_remove_step_arg_cache.pop(token, None)
        _xray_remove_step_issue_arg_cache.pop(token, None)
        _xray_remove_step_return_cache.pop(token, None)
        logger.warning(
            f"Could not delete existing steps for issue {issue_id}. "
            "Steps will be appended on top of existing ones."
        )
    else:
        logger.info(f"Deleted {len(valid_steps)} steps from issue {issue_id}")


# ---------------------------------------------------------------------------
# Step 4 – Update Jira issue summary + description in place
# ---------------------------------------------------------------------------

def update_jira_test_issue(issue_key: str, new_name: str, new_description: str, jira_cfg: dict):
    """Update the summary and description of an existing Jira Test issue."""
    base_url = jira_cfg["base_url"].rstrip("/")
    auth     = HTTPBasicAuth(jira_cfg["username"], jira_cfg["api_token"])
    headers  = {"Accept": "application/json", "Content-Type": "application/json"}
    payload  = {
        "fields": {
            "summary": new_name,
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": new_description or "No description provided."}
                ]}],
            },
        }
    }
    resp = requests.put(f"{base_url}/rest/api/3/issue/{issue_key}",headers=headers, auth=auth, json=payload, verify=False)
    if resp.status_code == 204:
        logger.info(f"Updated Jira issue {issue_key}")
    else:
        logger.error(f"Failed to update {issue_key}: {resp.status_code} - {resp.text}")


# ---------------------------------------------------------------------------
# Step 5 – Diff prompt: given fresh test cases + existing ones, decide
#           which to update (matched by name similarity) and which are new
# ---------------------------------------------------------------------------

_BROWNFIELD_DIFF_FORMAT = """
You MUST return ONLY a raw JSON object. No markdown. No code fences. No explanation. No prose.
Start your response with { and end with }.

Required structure:
{
  "updated_test_cases": [
    {
      "existing_key": "<Jira key e.g. WEGA-123 — use null for brand-new cases>",
      "Test Case Name": "<name>",
      "Test Case Description": "<description>",
      "Steps": [
        {
          "Step Number": "1",
          "Test Case Step": "<action>",
          "Expected Results": "<expected result>"
        }
      ],
      "change_reason": "<one sentence: what changed or why this is new>"
    }
  ],
  "summary": "<one sentence overall summary>"
}
"""

def _match_existing_key(fresh_name: str, existing_issues: List[Dict[str, Any]]) -> Optional[str]:
    """
    Simple name-based matcher: returns the Jira key of the existing test case
    whose summary most closely matches fresh_name (case-insensitive substring),
    or None if no reasonable match is found.
    Used as a fast pre-match before the LLM diff step.
    """
    fresh_lower = fresh_name.lower().strip()
    best_key   = None
    best_score = 0
    for issue in existing_issues:
        existing_lower = issue["summary"].lower().strip()
        # Count shared words as a simple similarity score
        fresh_words    = set(fresh_lower.split())
        existing_words = set(existing_lower.split())
        common         = len(fresh_words & existing_words)
        total          = len(fresh_words | existing_words) or 1
        score          = common / total
        if score > best_score and score >= 0.5:   # 50% word overlap threshold
            best_score = score
            best_key   = issue["key"]
    return best_key


def diff_and_merge_test_cases(fresh_test_cases: List[Dict[str, Any]],existing_issues:  List[Dict[str, Any]],scenario_type:    str) -> Dict[str, Any]:
    """
    Given:
      - fresh_test_cases : output of generate_test_cases() — properly structured list
      - existing_issues  : Jira issues with steps already fetched
      - scenario_type    : for context in the prompt

    Asks the LLM only to decide which fresh test cases map to existing Jira issues
    (so they should be updated in-place) vs which are genuinely new (should be created).

    Returns {updated_test_cases: [...], summary: "..."}
    Raises RuntimeError on parse failure.
    """
    existing_block = json.dumps([{"Jira Key": iss["key"], "Name": iss["summary"]} for iss in existing_issues],indent=2)
    fresh_block = json.dumps(fresh_test_cases, indent=2)

    prompt = f"""You are a QA engineer reconciling newly generated test cases against existing Jira test issues.

    Scenario Type: {scenario_type}

    Existing Jira test cases (key + name only):
    {existing_block}

    Newly generated test cases (full detail):
    {fresh_block}

    Your task:
    1. For each newly generated test case, check if it matches an existing Jira test case by name/intent.
    2. If it matches an existing one, set "existing_key" to that Jira key so it will be updated in-place.
    3. If it is a genuinely new scenario not covered by any existing case, set "existing_key" to null.
    4. Copy the full test case content (Name, Description, Steps) exactly from the fresh test cases — do not rewrite them.
    5. Every existing Jira key must appear at most once in your output.
    6. Do not drop any newly generated test case from your output.
    7. Keep Expected Results in future tense. No special characters.

    {_BROWNFIELD_DIFF_FORMAT}
    """
    raw = _llm_generate(prompt, temperature_override=0.1).strip()
    # Strip markdown fences if present
    matches = re.findall(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    json_str = matches[0].strip() if matches else raw

    # If still wrapped in fences without language tag
    if json_str.startswith("```"):
        json_str = re.sub(r"^```[^\n]*\n?", "", json_str)
        json_str = re.sub(r"\n?```$", "", json_str).strip()

    # Find the outermost JSON object if there is surrounding text
    if not json_str.startswith("{"):
        brace_start = json_str.find("{")
        if brace_start != -1:
            json_str = json_str[brace_start:]

    if not json_str:
        raise RuntimeError("LLM returned empty content for brownfield diff")

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse LLM brownfield diff JSON: {exc}\nRaw:\n{json_str[:600]}")
        # Last-resort fallback: build the result ourselves using name-based matching
        logger.warning("Falling back to name-based matching without LLM diff.")
        merged = []
        used_keys: set = set()
        for tc in fresh_test_cases:
            key = _match_existing_key(tc.get("Test Case Name", ""), existing_issues)
            if key and key not in used_keys:
                used_keys.add(key)
                existing_key = key
                change_reason = "Updated via name-match fallback"
            else:
                existing_key = None
                change_reason = "New test case — no matching existing issue found"
            merged.append({
                "existing_key":         existing_key,
                "Test Case Name":       tc.get("Test Case Name", ""),
                "Test Case Description": tc.get("Test Case Description", ""),
                "Steps":                tc.get("Steps", []),
                "change_reason":        change_reason,
            })
        return {"updated_test_cases": merged, "summary": "Merged via name-based fallback."}


# ---------------------------------------------------------------------------
# Step 6 – Orchestrate the full brownfield update for one story + scenario
# ---------------------------------------------------------------------------

def process_brownfield_story_jira(jira_story_id: str,userstory: str,scenario_type: str) -> Dict[str, Any]:
    """
    Full brownfield pipeline — mirrors greenfield two-step generation then diffs:
      1. Fetch existing Jira test cases (by label = jira_story_id)
      2. Fetch their Xray steps
      3. Generate fresh test scenarios + test cases from the (updated) user story
         using the same generate_test_cases() call as greenfield
      4. Diff fresh vs existing: LLM decides which map to existing keys (update)
         and which are net-new (create)
      5. Update existing Jira issues + replace their Xray steps
      6. Create brand-new Jira issues for gap-fill test cases
      7. Link new issues to the test plan

    Falls back to greenfield if no existing test cases are found.
    """
    # ── 1. Fetch existing Jira test cases ──────────────────────────────────
    existing_issues = fetch_existing_test_cases_by_label(jira_story_id, jira_config)
    if not existing_issues:
        logger.info(f"No existing test cases found for '{jira_story_id}' / '{scenario_type}'.Falling back to greenfield creation.")
        return process_single_story_jira(jira_story_id, userstory, scenario_type)
    # ── 2. Fetch Xray steps for each existing issue (needs token first) ────
    token = get_xray_token(xray_config["client_id"], xray_config["client_secret"])
    if not token:
        raise RuntimeError("Failed to obtain Xray authentication token")

    def _enrich_with_steps(issue: Dict[str, Any]) -> Dict[str, Any]:
        issue["steps"] = fetch_test_steps_graphql(issue["id"], token)
        return issue

    with ThreadPoolExecutor(max_workers=min(10, len(existing_issues))) as executor:
        enriched_issues = list(executor.map(_enrich_with_steps, existing_issues))

    # ── 3. Generate fresh test cases via the same greenfield pipeline ───────
    logger.info(f"Generating fresh test cases for '{jira_story_id}' / '{scenario_type}'...")
    generation_result = generate_test_cases(userstory=userstory, scenarioType=scenario_type)
    if generation_result is None or "error" in generation_result:
        raise RuntimeError(f"Test case generation failed: {generation_result.get('error', 'Unknown error')}")
    fresh_raw = generation_result.get("Test Cases")
    fresh_test_cases: List[Dict] = (json.loads(fresh_raw) if isinstance(fresh_raw, str) else fresh_raw)
    if not fresh_test_cases:
        raise RuntimeError("generate_test_cases returned an empty test case list")
    logger.info(f"Generated {len(fresh_test_cases)} fresh test cases; {len(enriched_issues)} existing in Jira. Running diff...")

    # ── 4. Diff: decide which fresh cases update existing vs are new ─────────
    diff_result = diff_and_merge_test_cases(fresh_test_cases, enriched_issues, scenario_type)
    merged_cases: List[Dict] = diff_result.get("updated_test_cases", [])
    if not merged_cases:
        raise RuntimeError("Diff step returned no test cases")

    existing_by_key = {iss["key"]: iss for iss in enriched_issues}
    to_update = [tc for tc in merged_cases if tc.get("existing_key")]
    to_create  = [tc for tc in merged_cases if not tc.get("existing_key")]

    updated_details: List[Dict] = []
    created_details: List[Dict] = []
    new_numeric_ids: List[str]  = []

    # ── 5. Update existing Jira issues + replace Xray steps ─────────────────
    def _apply_update(tc: Dict) -> Optional[Dict]:
        key        = tc["existing_key"]
        issue_info = existing_by_key.get(key)
        if not issue_info:
            logger.warning(f"Diff referenced unknown key {key} – skipping")
            return None
        update_jira_test_issue(
            issue_key      = key,
            new_name       = tc.get("Test Case Name", issue_info["summary"]),
            new_description= tc.get("Test Case Description", issue_info["description"]),
            jira_cfg       = jira_config,
        )
        delete_all_test_steps_graphql(issue_info["id"], token)
        steps = tc.get("Steps", [])
        if steps:
            add_test_steps_graphql(issue_info["id"], steps, token)
        return {
            "test_key":        key,
            "test_id":         issue_info["id"],
            "jira_link":       f"{jira_config['base_url'].rstrip('/')}/browse/{key}",
            "test_case_name":  tc.get("Test Case Name", issue_info["summary"]),
            "action":          "updated",
            "change_reason":   tc.get("change_reason", ""),
        }

    with ThreadPoolExecutor(max_workers=min(10, max(len(to_update), 1))) as executor:
        for detail in executor.map(_apply_update, to_update):
            if detail:
                updated_details.append(detail)

    # ── 6. Create net-new Jira issues for gap-fill test cases ───────────────
    if to_create:
        plan_numeric_id = get_issue_id_from_key(TEST_PLAN_KEY, jira_config)
        new_keys = create_tests_in_jira_cloud(jira_story_id, to_create, jira_config)

        def _enrich_new(args) -> Optional[Dict]:
            i, key = args
            numeric_id = get_issue_id_from_key(key, jira_config)
            if not numeric_id:
                return None
            steps = to_create[i].get("Steps", [])
            if steps:
                add_test_steps_graphql(numeric_id, steps, token)
            new_numeric_ids.append(numeric_id)
            return {
                "test_key":       key,
                "test_id":        numeric_id,
                "jira_link":      f"{jira_config['base_url'].rstrip('/')}/browse/{key}",
                "test_case_name": to_create[i].get("Test Case Name", "Unnamed Test Case"),
                "action":         "created",
                "change_reason":  to_create[i].get("change_reason", "New scenario identified"),
            }

        with ThreadPoolExecutor(max_workers=min(10, len(new_keys))) as executor:
            for detail in executor.map(_enrich_new, enumerate(new_keys)):
                if detail:
                    created_details.append(detail)

        # ── 6. Link new tests to plan ──────────────────────────────────────
        if new_numeric_ids and plan_numeric_id:
            link_tests_to_plan_graphql(plan_numeric_id, new_numeric_ids, token)

    return {
        "scenario_type":             scenario_type,
        "llm_summary":            diff_result.get("summary", ""),
        "generated_test_scenarios": generation_result.get("Test Scenarios"),
        "total_existing_fetched": len(enriched_issues),
        "total_fresh_generated":  len(fresh_test_cases),
        "total_updated":          len(updated_details),
        "total_created":          len(created_details),
        "updated_test_cases":        updated_details,
        "created_test_cases":        created_details,
        "jira_push_result": {
            "updated_tests":         updated_details,
            "created_tests":         created_details,
            "linked_plan":           TEST_PLAN_KEY,
        },
    }

# ---------------------------------------------------------------------------
# Bulk-job runner for brownfield (mirrors run_bulk_job_jira structure)
# ---------------------------------------------------------------------------
def run_bulk_brownfield_job_jira(job_id: str,stories: list,scenario_types: List[str],job_store: dict,jobs_lock: threading.Lock):
    """
    Process all (story × scenario_type) brownfield updates concurrently.
    Updates job_store in place. Designed to run in a FastAPI BackgroundTask.
    """
    def _process(index: int, story, scenario_type: str):
        with jobs_lock:
            job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {"status": "processing"}
            update_story_status(job_store, jobs_lock, job_id, index, scenario_types)
        try:
            result = process_brownfield_story_jira(jira_story_id=story.userStoryJiraId,userstory=story.userStory,scenario_type=scenario_type)
            with jobs_lock:
                job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {"status": "passed","result": result}
                job_store[job_id]["completed_count"] += 1
                update_story_status(job_store, jobs_lock, job_id, index, scenario_types)
        except Exception as exc:
            logger.error(f"[brownfield job={job_id}] story {story.userStoryJiraId} / {scenario_type} failed: {exc}",exc_info=True)
            with jobs_lock:
                job_store[job_id]["stories"][index]["results_by_scenario"][scenario_type] = {
                    "status": "failed",
                    "error":  str(exc),
                }
                job_store[job_id]["failed_count"] += 1
                update_story_status(job_store, jobs_lock, job_id, index, scenario_types)

    with jobs_lock:
        job_store[job_id]["status"] = "processing"

    tasks = [(i, story, st) for i, story in enumerate(stories) for st in scenario_types]
    with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as executor:
        for future in as_completed([executor.submit(_process, i, s, t) for i, s, t in tasks]):
            future.result()

    _finalise_job(job_id, stories, scenario_types, job_store, jobs_lock)
    logger.info(
        f"[brownfield job={job_id}] done. "
        f"completed={job_store[job_id]['completed_count']} "
        f"failed={job_store[job_id]['failed_count']}")
