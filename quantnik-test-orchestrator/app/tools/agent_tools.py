"""
Agent Tools Registry
====================
MCP-ready tool interfaces for calling test agents.
Supports both regular HTTP and SSE streaming calls.
"""

from typing import Dict, Any, AsyncGenerator, Optional
import httpx
import certifi
import json
import asyncio

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


def parse_sse_event(data: str) -> Optional[Dict[str, Any]]:
    """Parse a single SSE event data line into a dictionary."""
    logger.info("[agent_tools.py] parse_sse_event: ENTRY")
    if not data or not data.startswith("data:"):
        logger.info("[agent_tools.py] parse_sse_event: EXIT - no data")
        return None
    try:
        json_str = data[5:].strip()  # Remove "data:" prefix
        if json_str:
            result = json.loads(json_str)
            logger.info("[agent_tools.py] parse_sse_event: EXIT - success")
            return result
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse SSE event", data=data[:100], error=str(e))
    logger.info("[agent_tools.py] parse_sse_event: EXIT - failed")
    return None


def format_child_sse_event(event_data: Dict[str, Any], agent_name: str) -> str:
    """Format a child agent event for forwarding to client."""
    logger.info("[agent_tools.py] format_child_sse_event: ENTRY", agent_name=agent_name)
    event_data["source_agent"] = agent_name
    logger.info("[agent_tools.py] format_child_sse_event: EXIT", agent_name=agent_name)
    return f"data: {json.dumps(event_data)}\n\n"


class AgentToolRegistry:
    """Registry of test agent tools with SSE streaming support."""
    
    def __init__(self, timeout: int = None):
        logger.info("[agent_tools.py] AgentToolRegistry.__init__: ENTRY")
        self._timeout = timeout if timeout is not None else settings.agent_call_timeout
        
        # Get fresh SSL verify setting
        self._ssl_verify = False if not settings.ssl_verify else certifi.where()
        logger.info("SSL verify setting from config", settings_ssl_verify=settings.ssl_verify, resolved_ssl_verify=self._ssl_verify)
        
        if not settings.ssl_verify:
            logger.warning("SSL verification disabled - not recommended for production")
        
        # Configure httpx limits to prevent connection pool exhaustion
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=50,
            keepalive_expiry=30.0
        )
        
        # Configure transport with retry logic
        # IMPORTANT: Pass verify to transport so SSL context is properly configured
        transport = httpx.AsyncHTTPTransport(
            retries=3,  # Retry failed connections up to 3 times
            http2=False,  # Force HTTP/1.1 for better compatibility
            verify=self._ssl_verify  # Must pass verify here when using custom transport
        )
        
        # Force HTTP/1.1 for better compatibility with Cloud Run and various network configurations
        # HTTP/2 can cause "All connection attempts failed" errors in some environments
        self._client = httpx.AsyncClient(
            timeout=self._timeout, 
            verify=self._ssl_verify,
            limits=limits,
            follow_redirects=True,
            transport=transport
        )
        logger.info(
            "[agent_tools.py] AgentToolRegistry.__init__: EXIT",
            timeout_seconds=self._timeout,
            timeout_minutes=self._timeout / 60,
            ssl_verify=bool(self._ssl_verify),
            http2_enabled=False
        )

    def _resolve_test_cases_endpoint_url(self, state: Dict[str, Any]) -> str:
        """Resolve the test-cases endpoint based on Greenfield or Brownfield context."""
        context = state.get("context", {})
        entities = state.get("entities", {})

        project_type = (
            context.get("project_type")
            or entities.get("project_type")
            or context.get("script_generation_type")
            or entities.get("script_generation_type")
            or ""
        )
        project_type = str(project_type).strip().lower()

        endpoint_path = "/v1/generate-test-cases/bulk"
        if project_type == "brownfield":
            endpoint_path = "/v1/generate-test-cases/bulk/brownfield"

        endpoint_url = f"{settings.get_test_scenario_agent_url()}{endpoint_path}"
        logger.info(
            "Resolved test scenario endpoint",
            project_type=project_type or "greenfield",
            endpoint=endpoint_url
        )
        return endpoint_url
    
    async def close(self):
        """Close the HTTP client."""
        logger.info("[agent_tools.py] AgentToolRegistry.close: ENTRY")
        await self._client.aclose()
        logger.info("[agent_tools.py] AgentToolRegistry.close: EXIT")
    
    async def _stream_sse_request(
        self,
        url: str,
        payload: Dict[str, Any],
        agent_name: str
    ) -> AsyncGenerator[str, None]:
        """
        Make a streaming SSE request to a child agent and yield events.
        
        Args:
            url: The SSE endpoint URL
            payload: Request payload
            agent_name: Name of the agent for logging and event tagging
            
        Yields:
            SSE formatted strings to forward to client
        """
        logger.info(f"[agent_tools.py] AgentToolRegistry._stream_sse_request: ENTRY", agent_name=agent_name, endpoint=url)
        logger.debug(f"{agent_name} streaming request payload", endpoint=url, payload=payload)
        
        try:
            # Configure limits for streaming connections
            limits = httpx.Limits(
                max_keepalive_connections=20,
                max_connections=50,
                keepalive_expiry=30.0
            )
            
            # Use fresh ssl_verify setting
            ssl_verify = False if not settings.ssl_verify else certifi.where()
            logger.info(f"SSE stream SSL verify setting", ssl_verify=ssl_verify, settings_ssl_verify=settings.ssl_verify)
            
            # Configure transport with retry logic for streaming
            # IMPORTANT: Pass verify to transport, not just client, so SSL context is properly configured
            transport = httpx.AsyncHTTPTransport(
                retries=3,
                http2=False,
                verify=ssl_verify  # This is crucial - transport needs to know about SSL verification
            )
            
            async with httpx.AsyncClient(
                timeout=self._timeout, 
                verify=ssl_verify,
                limits=limits,
                follow_redirects=True,
                transport=transport
            ) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    logger.debug(
                        f"{agent_name} SSE connection established",
                        endpoint=url,
                        status_code=response.status_code
                    )
                    
                    if not response.is_success:
                        error_bytes = await response.aread()
                        error_text = error_bytes.decode() if error_bytes else ""
                        
                        # Try to parse error as JSON for better error details
                        error_detail = error_text[:1000]
                        try:
                            error_json = json.loads(error_text)
                            error_detail = error_json.get("detail", error_json)
                        except (json.JSONDecodeError, TypeError):
                            pass
                        
                        logger.error(
                            f"{agent_name} SSE request failed",
                            endpoint=url,
                            status_code=response.status_code,
                            error_detail=error_detail,
                            request_payload=payload
                        )
                        
                        raise RuntimeError(
                            f"{agent_name} request failed (HTTP {response.status_code}): {error_detail}"
                        )
                    
                    event_count = 0
                    buffer = ""
                    
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            
                            for line in event_str.split("\n"):
                                if line.startswith("data:"):
                                    event_data = parse_sse_event(line)
                                    if event_data:
                                        event_count += 1
                                        logger.debug(
                                            f"{agent_name} SSE event received",
                                            event_number=event_count,
                                            event_type=event_data.get("type"),
                                            event_stage=event_data.get("stage")
                                        )
                                        yield format_child_sse_event(event_data, agent_name)
                    
                    logger.info(
                        f"[agent_tools.py] AgentToolRegistry._stream_sse_request: EXIT",
                        agent_name=agent_name,
                        endpoint=url,
                        total_events=event_count
                    )
                    
        except httpx.HTTPStatusError as e:
            logger.error(
                f"{agent_name} SSE HTTP error",
                endpoint=url,
                status_code=e.response.status_code,
                error=str(e)
            )
            raise
        except httpx.HTTPError as e:
            logger.error(
                f"{agent_name} SSE connection error",
                endpoint=url,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    async def call_test_cases_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the Test Scenario Generator Agent.
        
        Generates test scenarios from user stories.
        """
        endpoint_url = self._resolve_test_cases_endpoint_url(state)
        logger.info("[agent_tools.py] AgentToolRegistry.call_test_cases_agent: ENTRY", endpoint=endpoint_url)
        
        context = state.get("context", {})
        entities = state.get("entities", {})
        
        logger.info("Test Scenario agent - raw state context", context=context)
        logger.info("Test Scenario agent - raw state entities", entities=entities)
        
        user_stories_raw = context.get("user_stories") or entities.get("user_stories") or ""
        scenario_types = context.get("scenario_types", [])
        
        # Use first scenario type if multiple provided, or default to "All"
        
        # Convert user_stories to string if it's a list/dict structure
        if isinstance(user_stories_raw, (list, dict)):
            user_stories = json.dumps(user_stories_raw)
        else:
            user_stories = str(user_stories_raw) if user_stories_raw else ""
        
        payload = {
            "userStories": [
                {
                    "userStoryJiraId": context.get("jira_id", "STORY-001"),
                    "userStory": user_stories
                }
            ],
            "ScenarioTypes": scenario_types
        }
        
        logger.info("Test Scenario agent - FINAL PAYLOAD", endpoint=endpoint_url, payload=payload)
        #logger.debug("Test Scenario agent request payload", endpoint=endpoint_url, payload=payload)
        
        # Get fresh SSL verify setting for this call
        ssl_verify = False if not settings.ssl_verify else certifi.where()
        logger.info("Test Scenario agent SSL verify", ssl_verify=ssl_verify, settings_ssl_verify=settings.ssl_verify)
        
        try:
            # Create fresh client with current SSL settings
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=ssl_verify,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload
                )
                
                logger.debug(
                    "Test Scenario agent HTTP response",
                    endpoint=endpoint_url,
                    status_code=response.status_code,
                    response_headers=dict(response.headers)
                )
                
                # Handle non-success status codes with detailed error logging
                if response.status_code >= 400:
                    error_body = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("detail", error_json)
                    except Exception:
                        error_detail = error_body[:1000] if error_body else "No error details"
                    
                    logger.error(
                        "Test Scenario agent returned error",
                        endpoint=endpoint_url,
                        status_code=response.status_code,
                        error_detail=error_detail,
                        request_payload=payload
                    )
                    raise RuntimeError(
                        f"Test Scenario agent error (HTTP {response.status_code}): {error_detail}"
                    )
                
                response.raise_for_status()
                
                result = response.json()
                print(f"[DEBUG] Test Scenario agent response payload: {str(result)[:2000]}")
                logger.info("Test Scenario agent response payload", endpoint=endpoint_url, result_payload=str(result)[:2000])
                
                # Extract test cases from response
                test_cases = result.get("test_cases", result.get("result", {}).get("test_cases", []))
                
                # Extract job_id, poll_url from async response (200/202)
                job_id = result.get("job_id")
                poll_url = result.get("poll_url")
                total = result.get("total")
                message = result.get("message")
                print(f"[DEBUG] Extracted values - job_id: {job_id}, poll_url: {poll_url}, total: {total}, message: {message}")
                logger.info("Test Scenario agent extracted values", job_id=job_id, poll_url=poll_url, total=total, message=message)
                agent_result = {
                    "success": True,
                    "result": {
                        "test_cases": test_cases,
                        "test_scenarios": result
                    },
                    "scenario_types_options": [],
                    "job_id": job_id,
                    "poll_url": poll_url,
                    "total": total,
                    "message": message,
                }
                
                logger.info(
                    "[agent_tools.py] AgentToolRegistry.call_test_cases_agent: EXIT",
                    endpoint=endpoint_url,
                    test_case_count=len(test_cases) if isinstance(test_cases, list) else 0,
                    job_id=job_id
                )
                
                return agent_result
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Test Scenario agent HTTP error",
                endpoint=endpoint_url,
                status_code=e.response.status_code,
                error=str(e),
                response_text=e.response.text[:500] if e.response.text else None
            )
            raise RuntimeError(f"Test Scenario agent error: {str(e)}")
        except httpx.HTTPError as e:
            logger.error(
                "Test Scenario agent call failed",
                endpoint=endpoint_url,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Test Scenario agent error: {str(e)}")
    
    async def call_test_cases_agent_streaming(
        self,
        state: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Call the Test Scenario Generator Agent with SSE streaming.
        
        First makes a non-streaming POST to get job_id and poll_url,
        then yields SSE events with the response data.
        """
        endpoint_url = self._resolve_test_cases_endpoint_url(state)
        logger.info("[agent_tools.py] AgentToolRegistry.call_test_cases_agent_streaming: ENTRY", endpoint=endpoint_url)
        
        context = state.get("context", {})
        entities = state.get("entities", {})
        
        logger.info("Test Scenario agent (streaming) - raw state context", context=context)
        logger.info("Test Scenario agent (streaming) - raw state entities", entities=entities)
        
        storyDetails = context.get("create_user_story_text") or entities.get("create_user_story_text") or ""
        scenario_types = context.get("scenario_types", [])
         
        # Populate all elements of storyDetails into userStories array
        userStories = []
        for story_detail in storyDetails:
            for user_story in story_detail.get("user_stories", []):
                userStories.append({
                    "userStoryJiraId": user_story.get("key", ""),
                    "userStory": user_story.get("summary", "")
                })

        scenario_payload = {
            "userStories": userStories,
            "ScenarioTypes": scenario_types 
        }

        logger.info(f"Calling generate-scenarios endpoint: {endpoint_url}")
        logger.info(f"Scenario payload: {scenario_payload}")
        
        # First make a non-streaming POST to get job_id, poll_url, etc.
        ssl_verify = False if not settings.ssl_verify else certifi.where()
        
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=ssl_verify,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    endpoint_url,
                    json=scenario_payload
                )
                
                print(f"[DEBUG] Test Scenario agent (streaming) - Response status: {response.status_code}")
                logger.info("Test Scenario agent (streaming) HTTP response", 
                           endpoint=endpoint_url, 
                           status_code=response.status_code)
                
                if response.status_code >= 400:
                    error_body = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("detail", error_json)
                    except Exception:
                        error_detail = error_body[:1000] if error_body else "No error details"
                    
                    logger.error("Test Scenario agent (streaming) returned error",
                                endpoint=endpoint_url,
                                status_code=response.status_code,
                                error_detail=error_detail)
                    raise RuntimeError(f"Test Scenario agent error (HTTP {response.status_code}): {error_detail}")
                
                result = response.json()
                print(f"[DEBUG] Test Scenario agent (streaming) - Response payload: {str(result)[:2000]}")
                logger.info("Test Scenario agent (streaming) response payload", 
                           endpoint=endpoint_url, 
                           result_payload=str(result)[:2000])
                
                # Extract job_id, poll_url from async response (200/202)
                job_id = result.get("job_id")
                poll_url = result.get("poll_url")
                total = result.get("total")
                message = result.get("message")
                if message and 'Poll /v1/jobs/' in message:
                    message = message.split('Poll /v1/jobs/')[0]
                test_cases = result.get("test_cases", result.get("result", {}).get("test_cases", []))
                
                print(f"[DEBUG] Test Scenario agent (streaming) - Extracted: job_id={job_id}, poll_url={poll_url}, total={total}, message={message}")
                logger.info("Test Scenario agent (streaming) extracted values", 
                           job_id=job_id, poll_url=poll_url, total=total, message=message)
                
                # Store job_id and poll_url in state for later use
                state["job_id"] = job_id
                state["poll_url"] = poll_url
                state["total"] = total
                state["message"] = message
                
                # Yield the response as an SSE event with job_id info
                response_event = {
                    "type": "response",
                    "stage": "test_scenario_agent",
                    "data": {
                        "success": True,
                        "job_id": job_id,
                        "poll_url": poll_url,
                        "total": total,
                        "message": message,
                        "test_cases": test_cases,
                        "test_scenarios": result
                    }
                }
                yield format_child_sse_event(response_event, "test_scenario_agent")
                
                logger.info("[agent_tools.py] AgentToolRegistry.call_test_cases_agent_streaming: EXIT",
                           endpoint=endpoint_url,
                           job_id=job_id)
                
        except httpx.HTTPStatusError as e:
            logger.error("Test Scenario agent (streaming) HTTP error",
                        endpoint=endpoint_url,
                        status_code=e.response.status_code,
                        error=str(e))
            raise RuntimeError(f"Test Scenario agent error: {str(e)}")
        except httpx.HTTPError as e:
            logger.error("Test Scenario agent (streaming) call failed",
                        endpoint=endpoint_url,
                        error=str(e),
                        error_type=type(e).__name__)
            raise RuntimeError(f"Test Scenario agent error: {str(e)}")
    
    async def call_test_script_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the Test Script Generator Agent.
        
        Generates automated test scripts from test cases.
        """
        endpoint_url = f"{settings.get_test_script_agent_url()}/convert"
        logger.info("[agent_tools.py] AgentToolRegistry.call_test_script_agent: ENTRY", endpoint=endpoint_url)
        
        context = state.get("context", {})
        
        # Get test cases - can be string or object
        test_cases = context.get("test_cases", "")
        if isinstance(test_cases, dict) or isinstance(test_cases, list):
            import json
            test_cases = json.dumps(test_cases)
        
        payload = {
            "test_cases": test_cases,
            "framework_type": context.get("framework_type", "Selenium TestNG"),
            "language": context.get("language", "Java"),
            "script_generation_type": context.get("script_generation_type", "Greenfield"),
        }
        
        logger.debug("Test Script agent request payload", endpoint=endpoint_url, payload=payload)
        
        # Get fresh SSL verify setting for this call
        ssl_verify = False if not settings.ssl_verify else certifi.where()
        logger.info("Test Script agent SSL verify", ssl_verify=ssl_verify, settings_ssl_verify=settings.ssl_verify)
        
        try:
            # Create fresh client with current SSL settings
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=ssl_verify,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload
                )
                
                logger.debug(
                    "Test Script agent HTTP response",
                    endpoint=endpoint_url,
                    status_code=response.status_code,
                    response_headers=dict(response.headers)
                )
                
                response.raise_for_status()
                
                result = response.json()
                logger.debug("Test Script agent response payload", endpoint=endpoint_url, response=result)
                
                # Extract test scripts and push_results from response
                test_scripts = result.get("test_scripts", result.get("scripts", result.get("result", {})))
                push_results = result.get("push_results")
                
                agent_result = {
                    "success": True,
                    "result": result,
                    "test_scripts": test_scripts,
                    "push_results": push_results,
                }
                
                logger.info(
                    "[agent_tools.py] AgentToolRegistry.call_test_script_agent: EXIT",
                    endpoint=endpoint_url,
                    has_scripts=bool(test_scripts)
                )
                
                return agent_result
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Test Script agent HTTP error",
                endpoint=endpoint_url,
                status_code=e.response.status_code,
                error=str(e),
                response_text=e.response.text[:500] if e.response.text else None
            )
            raise RuntimeError(f"Test Script agent error: {str(e)}")
        except httpx.HTTPError as e:
            logger.error(
                "Test Script agent call failed",
                endpoint=endpoint_url,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Test Script agent error: {str(e)}")
    
    async def call_test_script_agent_streaming(
        self,
        state: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Call the Test Script Generator Agent with SSE streaming.
        
        Makes a POST request and yields SSE events with push_results extracted.
        """
        endpoint_url = f"{settings.get_test_script_agent_url()}/convert"
        logger.info("[agent_tools.py] AgentToolRegistry.call_test_script_agent_streaming: ENTRY", endpoint=endpoint_url)
        
        context = state.get("context", {})
        
        # Get test cases - can be string or object
        test_cases = context.get("test_cases", "")
        if isinstance(test_cases, dict) or isinstance(test_cases, list):
            test_cases = json.dumps(test_cases)
        
        payload = {
            "test_cases": test_cases,
            "framework_type": context.get("framework_type", "Selenium TestNG"),
            "language": context.get("language", "Java"),
            "script_generation_type": context.get("script_generation_type", "Greenfield"),
        }
        
        logger.debug("Test Script agent (streaming) request payload", endpoint=endpoint_url, payload=payload)
        
        # Get fresh SSL verify setting for this call
        ssl_verify = False if not settings.ssl_verify else certifi.where()
        logger.info("Test Script agent (streaming) SSL verify", ssl_verify=ssl_verify, settings_ssl_verify=settings.ssl_verify)
        
        try:
            # Create fresh client with current SSL settings
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=ssl_verify,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload
                )
                
                logger.debug(
                    "Test Script agent (streaming) HTTP response",
                    endpoint=endpoint_url,
                    status_code=response.status_code,
                    response_headers=dict(response.headers)
                )
                
                if response.status_code >= 400:
                    error_body = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("detail", error_json)
                    except Exception:
                        error_detail = error_body[:1000] if error_body else "No error details"
                    
                    logger.error(
                        "Test Script agent (streaming) returned error",
                        endpoint=endpoint_url,
                        status_code=response.status_code,
                        error_detail=error_detail,
                        request_payload=payload
                    )
                    raise RuntimeError(
                        f"Test Script agent error (HTTP {response.status_code}): {error_detail}"
                    )
                
                response.raise_for_status()
                
                result = response.json()
                logger.debug("Test Script agent (streaming) response payload", endpoint=endpoint_url, response=result)
                
                # Extract test scripts and push_results from response
                test_scripts = result.get("test_scripts", result.get("scripts", result.get("result", {})))
                
                # Extract push_results from the response
                push_results = result.get("push_results", {})
                push_results_dict = {}
                for key, value in push_results.items():
                    push_results_dict[key] = value
                
                logger.info(
                    "[agent_tools.py] AgentToolRegistry.call_test_script_agent_streaming: EXIT",
                    endpoint=endpoint_url,
                    has_scripts=bool(test_scripts),
                    has_push_results=bool(push_results_dict)
                )
                
                # Store push_results in state for later use
                state["push_results"] = push_results_dict
                state["test_scripts"] = test_scripts
                
                # Yield the response as an SSE event with push_results
                response_event = {
                    "type": "response",
                    "stage": "test_script_agent",
                    "data": {
                        "success": True,
                        "test_scripts": test_scripts,
                        "push_results": push_results_dict,
                        "result": result
                    },
                   # "push_results": push_results_dict
                }
                yield format_child_sse_event(response_event, "test_script_agent")
                
        except httpx.HTTPStatusError as e:
            logger.error(
                "Test Script agent (streaming) HTTP error",
                endpoint=endpoint_url,
                status_code=e.response.status_code,
                error=str(e),
                response_text=e.response.text[:500] if e.response.text else None
            )
            raise RuntimeError(f"Test Script agent error: {str(e)}")
        except httpx.HTTPError as e:
            logger.error(
                "Test Script agent (streaming) call failed",
                endpoint=endpoint_url,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Test Script agent error: {str(e)}")

    async def call_test_data_agent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the Test Data Generator Agent.
        
        Generates structured test data from test cases.
        """
        endpoint_url = f"{settings.get_test_data_agent_url()}/generate-test-data"
        logger.info("Calling Test Data agent", endpoint=endpoint_url)
        
        context = state.get("context", {})
        
        test_cases = context.get("test_cases", [])
        if isinstance(test_cases, str):
            try:
                test_cases = json.loads(test_cases)
            except json.JSONDecodeError:
                test_cases = [{"description": test_cases}]
        
        output_format = context.get("output_format", "json")
        
        payload = {
            "test_cases": test_cases,
            "output_format": output_format,
        }
        
        logger.info("Test Data agent - FINAL PAYLOAD", endpoint=endpoint_url, payload=payload)
        
        ssl_verify = False if not settings.ssl_verify else certifi.where()
        
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=ssl_verify,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload
                )
                
                logger.debug(
                    "Test Data agent HTTP response",
                    endpoint=endpoint_url,
                    status_code=response.status_code,
                )
                
                if response.status_code >= 400:
                    error_body = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("detail", error_json)
                    except Exception:
                        error_detail = error_body[:1000] if error_body else "No error details"
                    
                    logger.error(
                        "Test Data agent returned error",
                        endpoint=endpoint_url,
                        status_code=response.status_code,
                        error_detail=error_detail,
                    )
                    raise RuntimeError(
                        f"Test Data agent error (HTTP {response.status_code}): {error_detail}"
                    )
                
                result = response.json()
                logger.info("Test Data agent response payload", endpoint=endpoint_url, result_payload=str(result)[:2000])
                
                agent_result = {
                    "success": True,
                    "result": result,
                    "test_data": result,
                    "output_format": output_format,
                }
                
                logger.info("Test Data agent call successful", endpoint=endpoint_url)
                return agent_result
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Test Data agent HTTP error",
                endpoint=endpoint_url,
                status_code=e.response.status_code,
                error=str(e),
            )
            raise RuntimeError(f"Test Data agent error: {str(e)}")
        except httpx.HTTPError as e:
            logger.error(
                "Test Data agent call failed",
                endpoint=endpoint_url,
                error=str(e),
                error_type=type(e).__name__
            )
            raise RuntimeError(f"Test Data agent error: {str(e)}")

    async def call_test_data_agent_streaming(
        self,
        state: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        Call the Test Data Generator Agent with SSE streaming.
        
        Makes a POST request and yields SSE events with test data.
        """
        endpoint_url = f"{settings.get_test_data_agent_url()}/generate-test-data"
        logger.info("Calling Test Data agent (streaming)", endpoint=endpoint_url)
        
        context = state.get("context", {})
        
        test_cases = context.get("test_cases", [])
        if isinstance(test_cases, str):
            try:
                test_cases = json.loads(test_cases)
            except json.JSONDecodeError:
                test_cases = [{"description": test_cases}]
        
        output_format = context.get("output_format", "json")
        
        payload = {
            "test_cases": test_cases,
            "output_format": output_format,
        }
        
        logger.info("Test Data agent (streaming) - FINAL PAYLOAD", endpoint=endpoint_url, payload=payload)
        
        ssl_verify = False if not settings.ssl_verify else certifi.where()
        
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=ssl_verify,
                follow_redirects=True
            ) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload
                )
                
                logger.info("Test Data agent (streaming) HTTP response",
                           endpoint=endpoint_url,
                           status_code=response.status_code)
                
                if response.status_code >= 400:
                    error_body = response.text
                    try:
                        error_json = response.json()
                        error_detail = error_json.get("detail", error_json)
                    except Exception:
                        error_detail = error_body[:1000] if error_body else "No error details"
                    
                    logger.error("Test Data agent (streaming) returned error",
                                endpoint=endpoint_url,
                                status_code=response.status_code,
                                error_detail=error_detail)
                    raise RuntimeError(f"Test Data agent error (HTTP {response.status_code}): {error_detail}")
                
                result = response.json()
                logger.info("Test Data agent (streaming) response payload",
                           endpoint=endpoint_url,
                           result_payload=str(result)[:2000])
                
                response_event = {
                    "type": "response",
                    "stage": "test_data_agent",
                    "data": {
                        "success": True,
                        "test_data": result,
                        "output_format": output_format,
                        "result": result
                    }
                }
                yield format_child_sse_event(response_event, "test_data_agent")
                
                logger.info("Test Data agent (streaming) completed successfully", endpoint=endpoint_url)
                
        except httpx.HTTPStatusError as e:
            logger.error("Test Data agent (streaming) HTTP error",
                        endpoint=endpoint_url,
                        status_code=e.response.status_code,
                        error=str(e))
            raise RuntimeError(f"Test Data agent error: {str(e)}")
        except httpx.HTTPError as e:
            logger.error("Test Data agent (streaming) call failed",
                        endpoint=endpoint_url,
                        error=str(e),
                        error_type=type(e).__name__)
            raise RuntimeError(f"Test Data agent error: {str(e)}")


# MCP Tool Definitions for test orchestrator
MCP_TOOL_DEFINITIONS = [
    {
        "name": "generate_test_cases",
        "description": "Generate test scenarios from user stories",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_stories": {"type": "array", "description": "User stories to generate scenarios for"},
                "scenario_types": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["user_stories"]
        }
    },
    {
        "name": "generate_test_scripts",
        "description": "Generate automated test scripts from test cases",
        "inputSchema": {
            "type": "object",
            "properties": {
                "test_cases": {"type": "string", "description": "Test cases"},
                "framework_type": {"type": "string", "enum": ["Selenium BDD", "Selenium TestNG", "Playwright"]},
                "language": {"type": "string", "enum": ["Java", "JavaScript", "TypeScript", "Python", "C#"]},
                "script_generation_type": {"type": "string", "enum": ["Greenfield", "Brownfield"]}
            },
            "required": ["test_cases", "framework_type", "language"]
        }
    },
    {
        "name": "generate_test_data",
        "description": "Generate structured test data from test cases",
        "inputSchema": {
            "type": "object",
            "properties": {
                "test_cases": {"type": "array", "description": "Test cases to generate data for"},
                "output_format": {"type": "string", "enum": ["json", "excel"], "description": "Output format"}
            },
            "required": ["test_cases"]
        }
    }
]
