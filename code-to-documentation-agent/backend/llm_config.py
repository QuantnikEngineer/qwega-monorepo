import re
import json
from typing import Dict, Any, List, Tuple, Optional

import httpx
import logging
import requests
from secrets_manager import get_secret


logger = logging.getLogger(__name__)


def _escape_string(value: str) -> str:
    """Escape double quotes so normalized JSON strings remain valid."""
    return value.replace('"', '\\"')


def normalize_to_json(raw: str) -> str:
    """Normalize Python-like dict/list string to valid JSON.
    
    Handles:
    - Single quotes → double quotes
    - Unquoted keys
    - true/false/null (case-insensitive)
    """
    normalized = raw.strip().replace("'", '"')
    result = []
    stack = ["obj"]
    expect_key = True
    i = 0
    length = len(normalized)

    while i < length:
        char = normalized[i]
        if char.isspace():
            result.append(char)
            i += 1
            continue
        if char == "{":
            result.append("{")
            stack.append("obj")
            expect_key = True
            i += 1
            continue
        if char == "[":
            result.append("[")
            stack.append("array")
            expect_key = False
            i += 1
            continue
        if char == "}" or char == "]":
            result.append(char)
            if len(stack) > 1:
                stack.pop()
            expect_key = False
            i += 1
            continue
        if char == ",":
            result.append(",")
            expect_key = stack and stack[-1] == "obj"
            i += 1
            continue
        if char == ":":
            result.append(":")
            expect_key = False
            i += 1
            continue

        context = stack[-1]
        if context == "obj" and expect_key:
            start = i
            while i < length and normalized[i] != ":":
                i += 1
            key = normalized[start:i].strip().strip('"')
            result.append(f'"{key}"')
            expect_key = False
            continue

        start = i
        if context == "obj":
            delimiters = {",", "}", "]"}
        else:
            delimiters = {",", "]"}
        while i < length and normalized[i] not in delimiters:
            i += 1
        token = normalized[start:i].strip()
        if not token:
            continue

        lower = token.lower()
        first_char = token[0]
        if first_char in "\"'":
            quote_char = first_char
            stripped = token
            if token[-1] == quote_char and len(token) > 1:
                stripped = token[1:-1]
            result.append(f'"{_escape_string(stripped)}"')
        elif first_char in "[{":
            result.append(token)
        elif lower in {"true", "false", "null"}:
            result.append(lower)
        elif re.fullmatch(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", token):
            result.append(token)
        else:
            result.append(f'"{_escape_string(token)}"')

    return "".join(result)


def _normalize_result(obj: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Normalize JSON content to providers/models lists of dicts.

    Accepts either:
    - {"providers": [...], "models": [...]} already in desired format
    - providers/models as list of strings; convert to dicts with minimal fields
    - uppercase keys (PROVIDERS/LLM_MODELS)
    """
    providers: List[Dict[str, Any]] = []
    models: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        raw_providers = obj.get("providers") or obj.get("PROVIDERS")
        raw_models = obj.get("models") or obj.get("LLM_MODELS")
        if isinstance(raw_providers, list):
            if raw_providers and isinstance(raw_providers[0], dict):
                providers = raw_providers
            else:
                providers = [{"key": str(p), "label": str(p)} for p in raw_providers]
        if isinstance(raw_models, list):
            if raw_models and isinstance(raw_models[0], dict):
                models = raw_models
            else:
                models = [{"key": str(m), "label": str(m), "provider": (str(m).split("/")[0] if "/" in str(m) else "")} for m in raw_models]
    return providers, models


def _resolve_config_url(base_url: Optional[str], config_path: Optional[str]) -> Optional[str]:
    logger.info(f"[DEBUG] Resolving LLM config URL from base: {base_url}")
    if not base_url:
        return None
    # # Default target path fallback
    # target_path = config_path if config_path else "Frontend/src/config/llmConfig.ts"
    # If direct file given (ts or json), use as-is
    if base_url.lower().endswith(".ts") or base_url.lower().endswith(".json"):
        return base_url
    try:
        from urllib.parse import urlparse
        u = urlparse(base_url)
        if u.hostname == "api.github.com":
            path = u.path.rstrip("/")
            if not path.endswith("/contents"):
                path = f"{path}/contents"
            return f"{u.scheme}://{u.hostname}{path}/{config_path}"
        if u.hostname == "github.com":
            parts = [p for p in u.path.split("/") if p]
            owner = parts[0] if len(parts) > 0 else ""
            repo = parts[1] if len(parts) > 1 else ""
            branch = parts[3] if len(parts) > 3 else "main"
            if owner and repo:
                return f"https://api.github.com/repos/{owner}/{repo}/contents/{config_path}?ref={branch}"
        if u.hostname == "raw.githubusercontent.com":
            segs = [p for p in u.path.split("/") if p]
            if len(segs) >= 3:
                owner, repo, branch = segs[0], segs[1], segs[2]
                return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{config_path}"
        return f"{base_url.rstrip('/')}/{config_path}"
    except Exception:
        return f"{base_url.rstrip('/')}/{config_path}"


def _parse_typescript_config(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse TypeScript config file containing array exports for PROVIDERS and LLM_MODELS.

    Expects patterns like:
      export const PROVIDERS = [ ... ];
      export const LLM_MODELS = [ ... ];
    """
    try:
        logger.info("🔍 Parsing TypeScript config...")

        def extract_array(name: str) -> Optional[str]:
            m = re.search(rf'export\s+const\s+{name}\s*[:=]\s*(\[[\s\S]*?\])', content, re.MULTILINE)
            return m.group(1) if m else None

        providers_arr = extract_array('PROVIDERS')
        models_arr = extract_array('LLM_MODELS')

        if not providers_arr and not models_arr:
            logger.error("Could not find PROVIDERS or LLM_MODELS exports in TypeScript config")
            return None

        def ts_array_to_json(arr_str: str) -> Optional[list]:
            if not arr_str:
                return None
            s = arr_str
            # Remove comments
            s = re.sub(r'//.*?$', '', s, flags=re.MULTILINE)
            s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)
            # Remove trailing commas
            s = re.sub(r',\s*(\]|\})', r'\1', s)
            # Convert single quotes to double quotes
            s = s.replace("'", '"')
            # Quote object keys
            s = re.sub(r'(\{|,)(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1\2"\3":', s)
            try:
                return json.loads(s)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error for {arr_str[:30]}...: {e}")
                return None

        providers_list = ts_array_to_json(providers_arr) or []
        models_list = ts_array_to_json(models_arr) or []

        result = {
            "providers": providers_list,
            "models": models_list,
        }
        logger.info(f"✅ Parsed providers={len(providers_list)}, models={len(models_list)} from GitHub config")
        return result

    except Exception as e:
        logger.error(f"Error parsing TypeScript config: {e}")
        return None
        
async def fetch_llm_config() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fetch PROVIDERS and LLM_MODELS from GitHub using secrets."""
    gh_llm_config = get_secret("GITHUB_LLM_CONFIG")
    logger.info(f"[DEBUG] Raw GITHUB_LLM_CONFIG secret: {gh_llm_config}")

    if not gh_llm_config:
        logger.warning("[WARNING] GITHUB_LLM_CONFIG secret missing - using fallback configuration")
        # Return fallback configuration with AWS Bedrock as default
        return (
            [
                {"key": "aws_bedrock", "label": "AWS Bedrock", "default": True}
            ],
            [
                # AWS Bedrock models
                {"key": "anthropic.claude-3-7-sonnet-20250219-v1:0", "label": "Claude 3.7 Sonnet", "provider": "aws_bedrock", "default": True},
                {"key": "amazon.nova-pro-v1:0", "label": "Amazon Nova Pro", "provider": "aws_bedrock", "default": False}
            ]
        )

    # If secret is a JSON string, parse it; otherwise if dict use directly; else attempt key=value extraction.
    if isinstance(gh_llm_config, str):
        parsed_secret: Optional[Dict[str, Any]] = None
        try:
            parsed_secret = json.loads(gh_llm_config)
            logger.info("[DEBUG] Parsed GITHUB_LLM_CONFIG as JSON string")
        except json.JSONDecodeError:
            # Try normalizing Python-like syntax to JSON
            try:
                normalized = normalize_to_json(gh_llm_config)
                parsed_secret = json.loads(normalized)
                logger.info("[DEBUG] Parsed GITHUB_LLM_CONFIG after normalization")
            except (json.JSONDecodeError, Exception) as norm_err:
                logger.debug(f"[DEBUG] Normalization failed: {norm_err}")
                # Fallback: parse key=value pairs (url=..., token=..., config_path=...)
                kv_matches = re.findall(r'(url|token|config_path)\s*[:=]\s*([^\n,;]+)', gh_llm_config)
                if kv_matches:
                    parsed_secret = {}
                    for k, v in kv_matches:
                        v_clean = v.strip().strip('"\'')
                        parsed_secret[k] = v_clean
                    logger.info("[DEBUG] Extracted key=value pairs from raw secret string")
        if not parsed_secret:
            logger.error("[ERROR] Unable to parse GITHUB_LLM_CONFIG secret string")
            return [], []
        gh_llm_config = parsed_secret

    if not isinstance(gh_llm_config, dict):
        logger.error("[ERROR] GITHUB_LLM_CONFIG not a dict after parsing")
        return [], []

    # Check if config already has providers/models (direct format)
    if "providers" in gh_llm_config and "models" in gh_llm_config:
        providers_list = gh_llm_config.get("providers", [])
        models_list = gh_llm_config.get("models", [])
        logger.info(f"✅ Using direct providers/models from secret: providers={len(providers_list)}, models={len(models_list)}")
        return _normalize_result(gh_llm_config)

    # Otherwise, expect url/token/config_path format to fetch from GitHub
    gh_url = gh_llm_config.get("url")
    gh_token = gh_llm_config.get("token")
    gh_llm_config_path = gh_llm_config.get("config_path")

    # Sanitize config_path (remove trailing braces/whitespace artifacts)
    if isinstance(gh_llm_config_path, str):
        cleaned_path = re.sub(r'[}\s]+$', '', gh_llm_config_path).strip()
        cleaned_path = re.sub(r'[}]+$', '', cleaned_path)
        if cleaned_path != gh_llm_config_path:
            logger.info(f"[DEBUG] Cleaned config_path from '{gh_llm_config_path}' to '{cleaned_path}'")
            gh_llm_config_path = cleaned_path

    logger.info(f"[DEBUG] GitHub URL: {gh_url}")
    logger.info("[DEBUG] GitHub Token present: %s" % ("YES" if gh_token else "NO"))
    logger.info(f"[DEBUG] GitHub config_path: {gh_llm_config_path}")

    resolved_url = _resolve_config_url(gh_url, gh_llm_config_path)
    logger.info(f"[DEBUG] Resolved LLM config URL: {resolved_url}")
    if not resolved_url:
        return [], []
        
    try:
        # Prepare headers
        token_headers = {}
        if gh_token:
            token_headers["Authorization"] = f"token {gh_token}"

        text: Optional[str] = None

        # Case 1: GitHub API contents endpoint
        if resolved_url.startswith("https://api.github.com/"):
            logger.info(f"📥 Fetching via GitHub API contents: {resolved_url}")
            api_headers = {"Accept": "application/vnd.github.v3+json", **token_headers}
            resp = requests.get(resolved_url, headers=api_headers, timeout=15, verify=False)
            if resp.status_code != 200:
                logger.info(f"❌ GitHub API request failed: {resp.status_code} {resp.text}")
                return [], []
            data = resp.json()
            # Prefer 'download_url' if available
            download_url = data.get("download_url")
            if download_url:
                logger.info(f"🔁 Following download_url to fetch raw file")
                raw_resp = requests.get(download_url, headers=token_headers, timeout=15, verify=False)
                if raw_resp.status_code != 200:
                    logger.info(f"❌ download_url fetch failed: {raw_resp.status_code} {raw_resp.text}")
                    return [], []
                text = raw_resp.text
            else:
                # Fall back to 'content' field (base64) when present
                content_b64 = data.get("content")
                if content_b64 and isinstance(content_b64, str):
                    import base64
                    try:
                        text = base64.b64decode(content_b64.encode("utf-8")).decode("utf-8")
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to decode base64 content: {e}")
                        return [], []
                else:
                    logger.info("❌ Neither download_url nor content present in API response")
                    return [], []

        # Case 2: GitHub web blob URL → convert to raw
        elif "github.com" in resolved_url:
            logger.info(f"📥 Fetching via GitHub web URL: {resolved_url}")
            # Convert web URL to raw URL to avoid HTML content
            if "/blob/" in resolved_url:
                resolved_url = resolved_url.replace("/blob/", "/raw/")
            resolved_url = resolved_url.replace("github.com", "raw.githubusercontent.com")
            logger.info(f"➡️  Converted to raw URL: {resolved_url}")
            raw_headers = {"Accept": "application/octet-stream", **token_headers}
            resp = requests.get(resolved_url, headers=raw_headers, timeout=15, verify=False)
            if resp.status_code != 200:
                logger.info(f"❌ Raw GitHub fetch failed: {resp.status_code} {resp.text}")
                return [], []
            text = resp.text

        # Case 3: Already raw.githubusercontent.com
        else:
            logger.info(f"📥 Fetching via raw URL: {resolved_url}")
            raw_headers = {"Accept": "application/octet-stream", **token_headers}
            resp = requests.get(resolved_url, headers=raw_headers, timeout=15, verify=False)
            if resp.status_code != 200:
                logger.info(f"❌ Raw fetch failed: {resp.status_code} {resp.text}")
                return [], []
            text = resp.text

        if text is None:
            logger.info("❌ No text content fetched from GitHub")
            return [], []
        logger.info(f"✅ Successfully fetched LLM config ({len(text)} bytes)")
    except Exception as e:
        logger.error(f"[ERROR] Error fetching LLM config: {e}")
        return [], []
    logger.info(f"[DEBUG] Fetched LLM config content, length: {len(text)}")
    
    # Parse TypeScript arrays and normalize to providers/models
    parsed_config = _parse_typescript_config(text)
    if not parsed_config:
        return [], []
    providers, models = _normalize_result(parsed_config)
    logger.info(f"[DEBUG] Parsed providers: {len(providers)}, models: {len(models)}")
    return providers, models