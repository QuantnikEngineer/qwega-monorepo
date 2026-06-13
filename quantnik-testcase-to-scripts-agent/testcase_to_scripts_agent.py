from datetime import datetime
import json
import os
import logging
import requests
import urllib3
import re
from vertexai import init
from vertexai.generative_models import GenerativeModel, HarmBlockThreshold, HarmCategory, SafetySetting
import time
from dotenv import load_dotenv
import asyncio
from concurrent.futures import ThreadPoolExecutor

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_disable_ssl_verify = os.getenv("DISABLE_SSL_VERIFY", "false").lower() in ("true", "1", "yes")
if _disable_ssl_verify:
    logger.warning("SSL verification is DISABLED via DISABLE_SSL_VERIFY — do not use this in production")
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    _orig_merge_env = requests.Session.merge_environment_settings
    def _patched_merge_env(self, url, proxies, stream, verify, cert):
        settings = _orig_merge_env(self, url, proxies, stream, verify, cert)
        settings["verify"] = False
        return settings
    requests.Session.merge_environment_settings = _patched_merge_env

executor = ThreadPoolExecutor(max_workers=10)

PROJECT_ID = os.getenv("PROJECT_ID", "digital-rig-poc")
LOCATION = os.getenv("LOCATION", "global")
STAGING_BUCKET = os.getenv("STAGING_BUCKET", "gs://test-agent-digital-engine-bucket")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3-flash-preview")

harness_url = os.getenv("HARNESS_URL", "https://app.harness.io")
account_id = os.getenv("ACCOUNT_ID", "2KolbecvR0aAcgQ5uXBObA")
org_id = os.getenv("ORG_ID", "WiproPOC")
project_id = os.getenv("PROJECT_ID_HARNESS", "Harness_POC")
repo_name = os.getenv("REPO_NAME", "test-automation-scripts-generator")
branch = os.getenv("BRANCH", "test")
token = os.getenv("TOKEN", "***REDACTED_HARNESS_PAT***")

try:
    logger.info("Initializing Vertex AI (project=%s, location=%s)", PROJECT_ID, LOCATION)
    init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)
    logger.info("Vertex AI initialized successfully")
except Exception as e:
    logger.error("Failed to initialize Vertex AI: %s", str(e))
    raise RuntimeError(f"Failed to initialize Vertex AI: {str(e)}")

try:
    logger.info("Loading GenerativeModel: %s", MODEL_NAME)
    model = GenerativeModel(MODEL_NAME)
    logger.info("GenerativeModel loaded successfully")
except Exception as e:
    logger.error("Failed to initialize GenerativeModel: %s", str(e))
    raise RuntimeError(f"Failed to initialize GenerativeModel: {str(e)}")

GENERATION_CONFIG = {"temperature": 0.3,"top_p": 0.95,"top_k": 40}
SAFETY_SETTINGS = [SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),SafetySetting(category=HarmCategory.HARM_CATEGORY_JAILBREAK,threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE)]

LANGUAGE_EXTENSIONS = {
    "java": ".java",
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "c#": ".cs",
    "xml": ".xml",
    "gradle": ".gradle",
    "feature": ".feature"
}

TEST_SCRIPT_PROMPTS = {
    "Selenium TestNG": {
        "Greenfield": """Generate an individual, complete, end-to-end {selected_language} Selenium script for the given test case as outlined above, using the latest versions of Selenium, TestNG, and WebDriverManager. Refer to the detailed test steps for creating the script. Task: Strengthen Test Stability; Objective: Identify potential areas of vulnerability in the code where errors may arise. Implement the test steps directly within the @Test method without separating them into reusable methods. Create a base test class that contains the setUp method and any other common setup or teardown logic, compatible with the latest Selenium and TestNG APIs, and use WebDriverManager for driver setup. Pinpoint locations requiring thread sleep and assertions to enhance script resilience; Action: Implement Robust Techniques, Add separate Try-Catch Blocks after every commented step to gracefully handle unexpected exceptions. Add appropriate wait strategies using Selenium 4+ features to enhance stability, and set an implicit wait of 10 seconds after opening the website. Integrate Assertions: Specify critical checkpoints in the test scenario and embed assertions to validate expected outcomes, ensuring thorough verification. Goal: Establish a Reliable Automation Script using the latest Selenium, TestNG, and WebDriverManager best practices. Give only the script, don't give anything else.""",
        "Brownfield": """You are enhancing an existing Selenium TestNG project in {selected_language}. Integrate the given test case into the existing framework by adding a new test method or updating an existing one. Reuse existing setup, teardown, and utility methods. Ensure stability improvements, add assertions at critical checkpoints, and follow existing project conventions. Return only the updated code.""",
        "languages": ["Java", "Python", "C#", "JavaScript"]
    },
    "Playwright": {
        "Greenfield": """IDENTITY You are a software test automation engineer with expertise in creating robust and reliable test scripts using Playwright {selected_language}. You specialize in writing maintainable, accessibility-focused scripts that use semantic selectors and ARIA roles for stability. Your skills include identifying potential vulnerabilities, implementing error handling, and integrating assertions to ensure test stability and accuracy. You enhance test scripts to handle unexpected scenarios gracefully and verify expected outcomes thoroughly. TASK Generate a Playwright script that identifies potential areas of vulnerability and implements robust techniques to enhance test stability. The script should include appropriate delays to ensure stability, and assertions to validate only the most critical checkpoints within the test scenario. FINAL DELIVERABLES A reliable Playwright automation script that includes: Integrated assertions to validate expected outcomes only at critical checkpoints (such as after navigation, before/after major actions, or at the end to confirm success). The script should have test(test case name or scenario name, async () => {{ ... }}); Use standard import statements for Playwright libraries. For element interaction: Use getByRole for buttons, links, headings, and form fields wherever possible, following ARIA roles and accessible names. Use locator only for elements that cannot be selected by role, and prefer semantic selectors. For user input fields, first use click and then fill methods. Add waitForTimeout() function wherever necessary for stability. The test data should be fetched from excel. Add detailed comments and logging to clarify each step and checkpoint. Prioritize accessibility and maintainability in selector strategy. Do not add visibility assertions (toBeVisible) for every step.""",
        "Brownfield": """You are updating an existing Playwright {selected_language} project. Integrate the new test case into the existing test suite, following the same structure and conventions. Reuse existing fixtures, page objects, and utilities. Add assertions only at critical checkpoints and ensure accessibility-focused selectors. Return only the new or updated test code.""",
        "languages": ["JavaScript", "TypeScript"]
    },
    "Selenium BDD": {
        "Greenfield": {
            "feature": """As an expert automation tester generate a feature file for the below given test case, focusing on its core functionality and requirements. Consider only the test steps and not the expected results of each step while generating the feature file.""",
            "step_definition": """IDENTITY You are an expert BDD automation engineer skilled in writing robust and maintainable step definition files across multiple frameworks and languages. TASK Generate a complete Step Definition file in {selected_language} for the given below feature file. FRAMEWORK CONTEXT The selected automation framework is Selenium BDD. Implement the step definitions according to the conventions of this framework and language. IMPLEMENTATION REQUIREMENTS - Map each Gherkin step (Given/When/Then) from the feature file to a corresponding method in {selected_language}. - Use the appropriate automation library for the selected framework: - Selenium BDD → Selenium WebDriver + Cucumber. - Playwright BDD → Playwright + Cucumber or equivalent. - Include necessary imports and annotations for step definitions (e.g., @Given, @When, @Then). - Implement robust error handling using try/catch (or equivalent) blocks for each step. - Add meaningful logging and comments for clarity. - Use explicit waits or framework-specific synchronization techniques to ensure stability. - Integrate assertions at critical checkpoints to validate expected outcomes. - For data-driven steps, read test data from external sources (e.g., Excel, JSON, or configuration files). - Keep the code modular, readable, and aligned with best practices for the chosen language. OUTPUT FORMAT Return only the complete and runnable step definition code for {selected_language}, enclosed in proper code syntax blocks. Do not include any explanations or narrative outside the code.""",
            "page_object": """Develop a Page Object Model (POM) file in {selected_language} selenium BDD framework to complement the previously generated Step Definition File. Ensure that the POM file effectively encapsulates the web elements and related actions for the application pages referenced in the below step definition code. Add code everywhere, don't just give blank classes."""
        },
        "Brownfield": {
            "feature": """Update or extend an existing Gherkin Feature file with new scenarios for the given test case.""",
            "page_object": """Update existing Page Object class in {selected_language} to include new elements or methods.""",
            "step_definition": """Add or update Step Definitions in {selected_language} corresponding to the new steps."""
        },
        "languages": ["Java", "C#"]
    }
}
SUPPORTED_FRAMEWORKS = list(TEST_SCRIPT_PROMPTS.keys())
SUPPORTED_LANGUAGES = ["Java", "Python", "JavaScript", "C#", "TypeScript"]
logger.info("Test script generation prompts configured")
logger.info("Supported Frameworks: %s", SUPPORTED_FRAMEWORKS)
logger.info("Supported Languages: %s", SUPPORTED_LANGUAGES)

def clean_response(response: str) -> str:
    """
    Strip fenced code blocks from the model response and return the code content.
    Rules:
    - Skip blocks tagged as bash/shell/sh/cmd (these are install instructions, not scripts).
    - Return the first non-bash fenced block if one exists.
    - If no fenced blocks exist at all, return the raw response (model gave bare code).
    - Never return an empty string when the original response had content.
    """
    SKIP_TAGS = {"bash", "shell", "sh", "cmd", "powershell", "zsh"}
    try:
        fence_pattern = re.compile(r"```(?P<tag>[a-zA-Z0-9#\+\-_]*)\s*\n(?P<code>[\s\S]*?)```",re.MULTILINE)
        matches = fence_pattern.findall(response)  # list of (tag, code) tuples
        for tag, code in matches:
            tag_lower = tag.strip().lower()
            code = code.strip()
            if tag_lower in SKIP_TAGS or not code:
                continue
            return code
        return response.strip()
    except Exception as e:
        logger.error("Error in clean_response: %s", str(e))
        return response

def extract_class_name_from_code(code: str, language: str, default_name: str) -> str:
    """
    Extract the actual class name from code, ignoring comments.
    Works for Java and C#.
    """
    lang_key = language.strip().lower()
    if lang_key in ("java", "c#"):
        code_no_comments = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code_no_comments = re.sub(r'/\*[\s\S]*?\*/', '', code_no_comments)
        type_match = re.search(r'^\s*(?:public\s+)?class\s+(\w+)', code_no_comments, re.MULTILINE)
        if type_match:
            return type_match.group(1)
    return default_name    

def extract_code_blocks(response_text: str, language: str):
    start_time = time.time()
    blocks = {}
    lang_key = language.strip().lower()
    file_ext = LANGUAGE_EXTENSIONS.get(lang_key, ".txt")
    fence_pattern = re.compile(r"```(?P<tag>[a-zA-Z0-9#\+\-_]*)\s*\n(?P<code>[\s\S]*?)```",re.MULTILINE)
    fence_matches = list(fence_pattern.finditer(response_text))
    candidates = []
    if fence_matches:
        for m in fence_matches:
            tag = (m.group("tag") or "").strip().lower()
            code = (m.group("code") or "").strip()
            if code:
                candidates.append((tag, code))
    else:
        if response_text.strip():
            candidates.append(("", response_text.strip()))

    def unique_name(name: str) -> str:
        if name not in blocks:
            return name
        base, ext = name.rsplit(".", 1)
        i = 2
        while f"{base}_{i}.{ext}" in blocks:
            i += 1
        return f"{base}_{i}.{ext}"
    SKIP_TAGS = {"bash", "shell", "sh", "cmd", "powershell", "zsh"}
    for idx, (tag, code) in enumerate(candidates, start=1):
        if time.time() - start_time > 10:
            logger.warning("extract_code_blocks timeout reached after 10s, stopping early")
            break
        if tag.strip().lower() in SKIP_TAGS:
            logger.info("Skipping bash/shell block (idx=%d): %r", idx, code[:60])
            continue
        if lang_key == "java":
            if tag in ("feature", "gherkin") or re.search(r"^\s*Feature:", code, re.MULTILINE):
                feature_name_match = re.search(r"Feature:\s*(.+)", code)
                feature_name = (re.sub(r"[^\w\-]", "_", feature_name_match.group(1).strip()) if feature_name_match else f"feature_{idx}")
                fname = unique_name(f"{feature_name}.feature")
                blocks[fname] = code
                continue
            is_java_like = (tag in ("java", "") and re.search(r"\b(class|interface|enum)\s+\w+", code) is not None)
            if not is_java_like:
                continue
            type_match = re.search(r"\b(?:public\s+)?(?:class|interface|enum)\s+(\w+)", code)
            class_name = type_match.group(1) if type_match else f"Generated{idx}"
            fname = unique_name(f"{class_name}{file_ext}")
            blocks[fname] = code.strip()
            continue
        elif lang_key == "python":
            classes = re.findall(r"class\s+(\w+)", code)
            if classes:
                for class_name in classes:
                    fname = unique_name(f"{class_name}{file_ext}")
                    blocks[fname] = code.strip()
            else:
                fname = unique_name(f"test_script{file_ext}")
                blocks[fname] = code.strip()
        elif lang_key in ("javascript", "typescript"):
            test_name_match = re.search(r"""(?:test|describe)\s*\(\s*['"`]([^'"`]+)['"`]""", code)
            if test_name_match:
                raw_name = test_name_match.group(1).strip()
                file_stem = re.sub(r"[^\w\-]", "_", raw_name)
                file_stem = re.sub(r"_+", "_", file_stem).strip("_")
            else:
                file_stem = f"test_script_{idx}"
            fname = unique_name(f"{file_stem}{file_ext}")
            blocks[fname] = code.strip()
        elif lang_key == "xml":
            if "<dependencies>" in code:
                blocks[unique_name("pom.xml")] = code
            elif "<suite" in code:
                blocks[unique_name("testng.xml")] = code
            else:
                blocks[unique_name(f"config_{idx}.xml")] = code
        elif lang_key == "gradle":
            blocks[unique_name(f"build_{idx}.gradle")] = code
        else:
            blocks[unique_name(f"code_block_{idx}{file_ext}")] = code
    return blocks

def extract_bdd_code_blocks(feature_text: str, step_text: str, page_text: str, language: str) -> dict:
    """
    Extract code blocks for Selenium BDD output which has separate
    feature, step definition, and page object content.
    """
    blocks = {}
    lang_key = language.strip().lower()
    file_ext = LANGUAGE_EXTENSIONS.get(lang_key, ".txt")
    def unique_name(name: str) -> str:
        if name not in blocks:
            return name
        base, ext = name.rsplit(".", 1)
        i = 2
        while f"{base}_{i}.{ext}" in blocks:
            i += 1
        return f"{base}_{i}.{ext}"
    if feature_text and feature_text.strip():
        feature_name_match = re.search(r"Feature:\s*(.+)", feature_text)
        feature_name = (re.sub(r"[^\w\-]", "_", feature_name_match.group(1).strip()) if feature_name_match else "feature")
        fname = unique_name(f"{feature_name}.feature")
        blocks[fname] = feature_text.strip()
    if step_text and step_text.strip():
        class_name = extract_class_name_from_code(step_text, language, "StepDefinitions")
        fname = unique_name(f"{class_name}{file_ext}")
        blocks[fname] = step_text.strip()
    if page_text and page_text.strip():
        class_name = extract_class_name_from_code(page_text, language, "PageObject")
        fname = unique_name(f"{class_name}{file_ext}")
        blocks[fname] = page_text.strip()  
    return blocks
 
# ---------------------------------------------------------------------------
# FIX: get_folder_name now accepts a single test-case dict directly.
# Folder name = "{TC ID}_{TC Name}" sanitised for filesystem/URL safety.
# ---------------------------------------------------------------------------
def get_folder_name(tc: dict) -> str:
    """
    Build a clean folder name from a single test-case dict.
    Pattern: {Test Case ID}_{Test Case Name}  (special chars → underscore)
    """
    try:
        tc_id = tc.get("Test Case ID", tc.get("id", "TC"))
        tc_name = tc.get("Test Case Name", tc.get("name", "Script"))
        folder = re.sub(r"[^\w\-]", "_", f"{tc_id}_{tc_name}")
        folder = re.sub(r"_+", "_", folder).strip("_")
        logger.info("Resolved folder name: '%s'", folder)
        return folder
    except Exception as e:
        logger.warning("Could not build folder name from test case dict, using default. Error: %s", str(e))
        return "generated_scripts"

# ---------------------------------------------------------------------------
# FIX: push_to_harness_devops no longer adds a timestamp to file names.
# Files are named after their class/feature name (set by extract_*_code_blocks).
# A timestamp is kept only on the commit message so pushes remain traceable.
# If a file already exists in the repo the action "CREATE" will overwrite it;
# switch to "UPDATE" here if your Harness API requires a separate verb.
# ---------------------------------------------------------------------------
def push_to_harness_devops(code_blocks: dict, folder_name: str) -> list:
    """
    Push all generated code files to Harness DevOps in a single commit.

    Strategy for 409 conflicts (file already exists):
      - First attempt uses "CREATE" for all files.
      - If Harness returns 409, we identify the conflicting path from the error
        message and rebuild the actions list replacing "CREATE" → "UPDATE" for
        that file, then retry the entire commit once.
      - This handles repos that already have scripts from a previous run without
        requiring a delete step.
    """
    headers = {"x-api-key": token,"Content-Type": "application/json"}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    commit_url = (
        f"{harness_url}/code/api/v1/repos/{repo_name}/commits"
        f"?accountIdentifier={account_id}"
        f"&orgIdentifier={org_id}"
        f"&projectIdentifier={project_id}"
    )
    file_actions = {}
    for filename, content in code_blocks.items():
        file_path = f"{folder_name}/{filename}"
        file_actions[file_path] = {"action": "CREATE","path": file_path,"payload": content.strip(),"encoding": "utf-8"}
    pushed_paths = list(file_actions.keys())
    logger.info("Pushing %d file(s) to Harness folder '%s' on branch '%s'", len(pushed_paths), folder_name, branch)
    logger.info("Commit URL: %s", commit_url)
    def _do_commit(actions: list) -> requests.Response:
        payload = {"branch": branch,"message": f"Automated commit for {folder_name} at {timestamp}","actions": actions}
        return requests.post(commit_url, headers=headers, json=payload, verify=False)
    # Iterative retry: handle 409 (file exists → UPDATE) and 404 (file missing → CREATE).
    # A mixed-state folder (some files pre-existing, some new) can trigger both codes
    # across retries. We adjust per-file actions based on the specific path in each
    # error response and retry up to (2 × number of files) times.
    max_attempts = len(file_actions) * 2 + 1
    response = None
    for attempt in range(1, max_attempts + 1):
        response = _do_commit(list(file_actions.values()))
        if response.status_code in (200, 201):
            break
        try:
            error_message = response.json().get("message", "")
        except Exception:
            error_message = response.text
        if response.status_code == 409:
            match = re.search(r"path (.+?) already exists", error_message)
            if match:
                conflicting_path = match.group(1).strip()
                if conflicting_path in file_actions:
                    logger.warning("Attempt %d — 409: switching '%s' CREATE → UPDATE", attempt, conflicting_path)
                    file_actions[conflicting_path]["action"] = "UPDATE"
                else:
                    logger.warning("Attempt %d — 409: conflicting path '%s' not in action map, switching all to UPDATE", attempt, conflicting_path)
                    for path in file_actions:
                        file_actions[path]["action"] = "UPDATE"
            else:
                logger.warning("Attempt %d — 409: no specific path in error, switching all to UPDATE", attempt)
                for path in file_actions:
                    file_actions[path]["action"] = "UPDATE"
        elif response.status_code == 404:
            match = re.search(r"path (.+?) not found", error_message)
            if match:
                missing_path = match.group(1).strip()
                if missing_path in file_actions:
                    logger.warning("Attempt %d — 404: switching '%s' UPDATE → CREATE", attempt, missing_path)
                    file_actions[missing_path]["action"] = "CREATE"
                else:
                    logger.error("Attempt %d — 404: missing path '%s' not in action map, aborting", attempt, missing_path)
                    break
            else:
                logger.error("Attempt %d — 404: could not parse missing path from response, aborting", attempt)
                break
        else:
            logger.error("Attempt %d — unrecoverable HTTP %d, aborting", attempt, response.status_code)
            break
    if response is not None and response.status_code in (200, 201):
        logger.info("Successfully pushed %d file(s) to folder '%s'", len(pushed_paths), folder_name)
        for p in pushed_paths:
            logger.info("  Pushed: %s", p)
        file_urls = [
            f"{harness_url}/ng/account/{account_id}/module/code/orgs/{org_id}"
            f"/projects/{project_id}/repos/{repo_name}/files/{branch}/~/{path}"
            for path in pushed_paths]
        return file_urls
    else:
        status = response.status_code if response is not None else "N/A"
        body = response.text if response is not None else "no response"
        logger.error("Push failed for folder '%s' after %d attempt(s) — HTTP %s", folder_name, attempt, status)
        logger.error("Harness response: %s", body)
        return []
    
def convert_test_cases_to_scripts(test_cases: str, framework_type: str, language: str, script_generation_type: str) -> dict:
    """
    Convert test cases to test automation scripts using the specified framework and language.
    Returns a dict with either 'script' key (for non-BDD) or 'feature', 'step_definition', 'page_object' keys (for BDD).
    """
    logger.info("Converting test cases — framework: '%s', language: '%s', type: '%s'", framework_type, language, script_generation_type)
    if framework_type not in TEST_SCRIPT_PROMPTS:
        logger.error("Unsupported framework type: '%s'. Supported: %s", framework_type, SUPPORTED_FRAMEWORKS)
        raise ValueError(f"Unsupported framework type: {framework_type}. Supported frameworks: {SUPPORTED_FRAMEWORKS}")
    framework_config = TEST_SCRIPT_PROMPTS[framework_type]
    allowed_languages = framework_config["languages"]
    if language not in allowed_languages:
        logger.error("Unsupported language '%s' for framework '%s'. Allowed: %s", language, framework_type, allowed_languages)
        raise ValueError(f"Unsupported language '{language}' for framework '{framework_type}'. "f"Supported languages for this framework are: {allowed_languages}")
    generation_type = script_generation_type.capitalize()
    if generation_type not in ["Greenfield", "Brownfield"]:
        logger.error("Invalid script_generation_type: '%s'. Must be 'Greenfield' or 'Brownfield'", script_generation_type)
        raise ValueError("script_generation_type must be either 'Greenfield' or 'Brownfield'")
    if framework_type == "Selenium BDD":
        prompts = framework_config[generation_type]
        feature_prompt = f"{prompts['feature']}\n\nLanguage: {language}\nTest Cases:\n{test_cases}"
        logger.info("Generating Feature File (language=%s, type=%s)...", language, generation_type)
        try:
            feature_response = model.generate_content(feature_prompt,generation_config=GENERATION_CONFIG,safety_settings=SAFETY_SETTINGS)
            feature_text = feature_response.text.strip()
            feature_text = clean_response(feature_text)
            logger.info("Feature File generated successfully (%d chars)", len(feature_text))
        except Exception as e:
            logger.error("Error generating Feature File: %s", str(e))
            raise RuntimeError(f"Error generating Feature File: {str(e)}")
        step_prompt = prompts["step_definition"].format(selected_language=language)
        step_prompt = f"{step_prompt}\n\nFeature File:\n{feature_text}\n\nLanguage: {language}"
        logger.info("Generating Step Definition File (language=%s)...", language)
        try:
            step_response = model.generate_content(step_prompt,generation_config=GENERATION_CONFIG,safety_settings=SAFETY_SETTINGS)
            step_text = step_response.text.strip()
            step_text = clean_response(step_text)
            logger.info("Step Definition File generated successfully (%d chars)", len(step_text))
        except Exception as e:
            logger.error("Error generating Step Definition File: %s", str(e))
            raise RuntimeError(f"Error generating Step Definition File: {str(e)}")
        page_prompt = prompts["page_object"].format(selected_language=language)
        page_prompt = f"{page_prompt}\n\nStep Definition Code:\n{step_text}\n\nLanguage: {language}"
        logger.info("Generating Page Object File (language=%s)...", language)
        try:
            page_response = model.generate_content(page_prompt,generation_config=GENERATION_CONFIG,safety_settings=SAFETY_SETTINGS)
            page_text = page_response.text.strip()
            page_text = clean_response(page_text)
            logger.info("Page Object File generated successfully (%d chars)", len(page_text))
        except Exception as e:
            logger.error("Error generating Page Object File: %s", str(e))
            raise RuntimeError(f"Error generating Page Object File: {str(e)}")
        return {"is_bdd": True, "feature": feature_text,"step_definition": step_text,"page_object": page_text}
    else:
        prompts = TEST_SCRIPT_PROMPTS[framework_type]
        base_prompt = prompts[generation_type].format(selected_language=language)
        generation_prompt = f"{base_prompt}\n\nTest Cases:\n{test_cases}\n\nLanguage: {language}\nGeneration Type: {script_generation_type}"
        logger.info("Generating script (framework=%s, language=%s, type=%s)...", framework_type, language, generation_type)
        try:
            response = model.generate_content(generation_prompt, generation_config=GENERATION_CONFIG, safety_settings=SAFETY_SETTINGS)
            script_text = clean_response(response.text.strip())
            logger.info("Script generated successfully (%d chars)", len(script_text))
            return {"is_bdd": False,"script": script_text}
        except Exception as e:
            logger.error("Error during script generation (framework=%s, language=%s): %s", framework_type, language, str(e))
            raise RuntimeError(f"Error during script generation: {str(e)}")

async def process_single_test_case(tc: dict, framework_type: str, language: str, script_generation_type: str):
    tc_id = tc.get("Test Case ID", tc.get("id", "unknown"))
    tc_name = tc.get("Test Case Name", tc.get("name", "unknown"))
    logger.info("Processing test case: ID='%s', Name='%s', framework='%s', language='%s', type='%s'",
                tc_id, tc_name, framework_type, language, script_generation_type)
    tc_str = json.dumps(tc)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor,lambda: convert_test_cases_to_scripts(tc_str, framework_type, language, script_generation_type))
    if result.get("is_bdd"):
        logger.info("Extracting BDD code blocks for test case '%s'", tc_id)
        code_blocks = extract_bdd_code_blocks(result.get("feature", ""),result.get("step_definition", ""),result.get("page_object", ""),language)
    else:
        logger.info("Extracting code blocks for test case '%s'", tc_id)
        code_blocks = extract_code_blocks(result.get("script", ""), language)
    logger.info("Extracted %d code block(s) for test case '%s': %s", len(code_blocks), tc_id, list(code_blocks.keys()))
    folder_name = get_folder_name(tc)
    file_urls = await loop.run_in_executor(executor,lambda: push_to_harness_devops(code_blocks, folder_name))
    logger.info("Completed processing for test case '%s' — %d file URL(s) returned", tc_id, len(file_urls))
    return code_blocks, file_urls, folder_name
