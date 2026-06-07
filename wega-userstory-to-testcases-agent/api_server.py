"""
FastAPI Server for UserStory to Test Cases Agent
Exposes REST API endpoints for Docker deployment.
All core processing logic lives in userstory2TestCasesAgent.py.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any, List
from uuid import uuid4
from datetime import datetime
import threading
import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import uvicorn

from userstory2TestCasesAgent import get_scenario_type,run_bulk_job_jira,run_bulk_job_qtest,run_bulk_job_ado,process_single_story_jira,process_single_story_qtest,update_story_status,run_bulk_brownfield_job_jira

load_dotenv()

logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="UserStory to Test Cases API",description="Converts user stories into structured test cases using Vertex AI",version="1.0.0",docs_url="/docs",openapi_url="/openapi.json")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

# In-memory job store shared across background threads
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()
# Keep original inputs and target system so failed stories can be retried.
_job_inputs: Dict[str, List["StoryItem"]] = {}
_job_targets: Dict[str, str] = {}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    message: str
    
class StoryItem(BaseModel):
    userStoryJiraId: str
    userStory: str
    @field_validator("userStoryJiraId")
    @classmethod
    def validate_jira_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("userStoryJiraId cannot be empty")
        return v.strip()
    @field_validator("userStory")
    @classmethod
    def validate_story(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("userStory cannot be empty")
        return v.strip()
    
class BulkRequest(BaseModel):
    userStories: List[StoryItem]
    ScenarioTypes: List[str]
    @field_validator("userStories")
    @classmethod
    def check_stories(cls, v: List[StoryItem]):
        if not v:
            raise ValueError("userStories cannot be empty")
        if len(v) > 50:
            raise ValueError("Maximum 50 stories allowed per bulk request")
        return v
    @field_validator("ScenarioTypes")
    @classmethod
    def check_scenario_types(cls, v: List[str]):
        if not v:
            raise ValueError("At least one ScenarioType must be provided")
        if len(v) > 10:
            raise ValueError("Maximum 10 ScenarioTypes allowed per bulk request")
        return v
    
class BulkJobResponse(BaseModel):
    job_id: str
    total: int
    message: str
    poll_url: str

class BulkUserStoryItem(BaseModel):
    userStoryJiraId: str
    userStory: str
    @field_validator("userStoryJiraId")
    @classmethod
    def validate_jira_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("userStoryJiraId cannot be empty")
        return v.strip()
    @field_validator("userStory")
    @classmethod
    def validate_story(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("userStory cannot be empty")
        return v.strip()

class BulkGenerateTestCases(BaseModel):
    userStories: List[BulkUserStoryItem]
    ScenarioTypes: List[str]
    @field_validator("userStories")
    @classmethod
    def check_stories(cls, v: List[BulkUserStoryItem]):
        if not v:
            raise ValueError("userStories cannot be empty")
        if len(v) > 50:
            raise ValueError("Maximum 50 stories allowed per bulk request")
        return v
    @field_validator("ScenarioTypes")
    @classmethod
    def check_scenario_types(cls, v: List[str]):
        if not v:
            raise ValueError("At least one ScenarioType must be provided")
        if len(v) > 10:
            raise ValueError("Maximum 10 ScenarioTypes allowed per bulk request")
        return v

class SubmitBulkJobResponse(BaseModel):
    job_id: str
    total: int
    message: str
    poll_url: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _validate_scenario_types(requested: List[str]):
    logger.debug(f"Validating {len(requested)} scenario types: {requested}")
    valid   = get_scenario_type()
    invalid = [t for t in requested if t not in valid]
    if invalid:
        error_msg = f"Invalid ScenarioTypes: {', '.join(invalid)}. Valid types: {', '.join(valid)}"
        logger.error(f"Validation failed: {error_msg}")
        raise HTTPException(status_code=400,detail=error_msg)
    logger.debug(f"All {len(requested)} scenario types validated successfully")

def _create_job_entry(stories: List[StoryItem], scenario_types: List[str]) -> tuple[str, dict]:
    """Initialise a new job entry and return (job_id, job_entry)."""
    logger.debug(f"Creating new job entry for {len(stories)} stories and {len(scenario_types)} scenario types")
    job_id = str(uuid4())
    logger.info(f"New job created: {job_id}")
    entry  = {
        "job_id":          job_id,
        "created_at":      datetime.utcnow().isoformat() + "Z",
        "completed_at":    None,
        "status":          "pending",
        "total":           len(stories),
        "completed_count": 0,
        "failed_count":    0,
        "ScenarioTypes":   scenario_types,
        "stories": [
            {
                "index":               i,
                "userStoryJiraId":     s.userStoryJiraId,
                "status":              "pending",
                "results_by_scenario": {},
                "error":               None,
            }
            for i, s in enumerate(stories)
        ],
    }
    return job_id, entry

def _get_failed_story_indexes(job: Dict[str, Any], scenario_types: List[str]) -> List[int]:
    """Return story indexes that have at least one failed scenario."""
    logger.debug(f"Scanning job stories for failed scenarios...")
    failed_indexes: List[int] = []
    for story in job.get("stories", []):
        results = story.get("results_by_scenario", {})
        has_failed_scenario = any((results.get(st) or {}).get("status") == "failed" for st in scenario_types)
        if has_failed_scenario or story.get("status") in ("failed", "partial_passed"):
            failed_indexes.append(story.get("index"))
    logger.debug(f"Found {len(failed_indexes)} stories with failed scenarios")
    return failed_indexes

def _rerun_failed_same_job_jira(job_id: str, retry_items: List[tuple], scenario_types: List[str]):
    """Rerun failed (orig_index, StoryItem, scenario_type) triples within the same job entry (Jira/Xray)."""
    logger.info(f"Starting retry for Jira job {job_id} with {len(retry_items)} items")
    def _process(orig_index: int, story, scenario_type: str):
        logger.debug(f"[retry job={job_id}] Processing {story.userStoryJiraId}/{scenario_type}")
        with _jobs_lock:
            _jobs[job_id]["stories"][orig_index]["results_by_scenario"][scenario_type] = {"status": "processing"}
            update_story_status(_jobs, _jobs_lock, job_id, orig_index, scenario_types)
        try:
            logger.debug(f"[retry job={job_id}] Calling process_single_story_jira")
            result = process_single_story_jira(jira_story_id=story.userStoryJiraId,userstory=story.userStory,scenario_type=scenario_type)
            scenario_status = result.get("overall_status", "passed")
            with _jobs_lock:
                _jobs[job_id]["stories"][orig_index]["results_by_scenario"][scenario_type] = {"status": scenario_status,"result": result}
                update_story_status(_jobs, _jobs_lock, job_id, orig_index, scenario_types)
            logger.info(f"[retry job={job_id}] Story {story.userStoryJiraId}/{scenario_type} succeeded on retry")
        except Exception as e:
            logger.error(f"[retry job={job_id}] story {story.userStoryJiraId} / {scenario_type} failed: {e}", exc_info=True)
            with _jobs_lock:
                _jobs[job_id]["stories"][orig_index]["results_by_scenario"][scenario_type] = {"status": "failed","error": str(e)}
                update_story_status(_jobs, _jobs_lock, job_id, orig_index, scenario_types)
    with ThreadPoolExecutor(max_workers=min(10, len(retry_items))) as executor:
        futures = [executor.submit(_process, idx, story, st) for idx, story, st in retry_items]
        for f in as_completed(futures):
            f.result()
    _finalise_retry_job(job_id, scenario_types)
    logger.info(f"[retry job={job_id}] Jira retry completed")

def _rerun_failed_same_job_qtest(job_id: str, retry_items: List[tuple], scenario_types: List[str]):
    """Rerun failed (orig_index, StoryItem, scenario_type) triples within the same job entry (qTest)."""
    logger.info(f"Starting retry for qTest job {job_id} with {len(retry_items)} items")
    def _process(orig_index: int, story, scenario_type: str):
        logger.debug(f"[retry job={job_id}] Processing {story.userStoryJiraId}/{scenario_type}")
        with _jobs_lock:
            _jobs[job_id]["stories"][orig_index]["results_by_scenario"][scenario_type] = {"status": "processing"}
            update_story_status(_jobs, _jobs_lock, job_id, orig_index, scenario_types)
        try:
            logger.debug(f"[retry job={job_id}] Calling process_single_story_qtest")
            result = process_single_story_qtest(userstory=story.userStory,scenario_type=scenario_type)
            scenario_status = result.get("overall_status", "passed")
            with _jobs_lock:
                _jobs[job_id]["stories"][orig_index]["results_by_scenario"][scenario_type] = {"status": scenario_status,"result": result}
                update_story_status(_jobs, _jobs_lock, job_id, orig_index, scenario_types)
            logger.info(f"[retry job={job_id}] Story {story.userStoryJiraId}/{scenario_type} succeeded on retry")
        except Exception as e:
            logger.error(f"[retry job={job_id}] story {story.userStoryJiraId} / {scenario_type} failed: {e}", exc_info=True)
            with _jobs_lock:
                _jobs[job_id]["stories"][orig_index]["results_by_scenario"][scenario_type] = {"status": "failed","error": str(e)}
                update_story_status(_jobs, _jobs_lock, job_id, orig_index, scenario_types)
    with ThreadPoolExecutor(max_workers=min(10, len(retry_items))) as executor:
        futures = [executor.submit(_process, idx, story, st) for idx, story, st in retry_items]
        for f in as_completed(futures):
            f.result()
    _finalise_retry_job(job_id, scenario_types)
    logger.info(f"[retry job={job_id}] qTest retry completed")

def _finalise_retry_job(job_id: str, scenario_types: List[str]):
    """Recompute and set final job-level status after in-place retry."""
    logger.info(f"Finalizing retry for job {job_id}...")
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            logger.warning(f"Job {job_id} not found during retry finalization")
            return
        total_stories = len(job["stories"])
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
            f"Retry job {job_id} finalized. Status: {job['status']} "
            f"(passed={passed_stories}, partial={partial_stories}, failed={failed_stories}, processing={processing_stories})"
        )
        
# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", response_model=HealthResponse,tags=["Health"],summary="Health check endpoint (root)")
async def root():
    logger.debug("Health check endpoint called (root)")
    return {"status": "healthy", "message": "UserStory to TestCases API is running"}

@app.get("/health", response_model=HealthResponse,tags=["Health"],summary="Health check endpoint (/health)")
async def health_check():
    logger.debug("Health check endpoint called (/health)")
    return {"status": "healthy", "message": "Service is operational"}

@app.get("/scenario-types",tags=["Greenfield"],summary="List available scenario types for test case generation")
async def list_scenario_types():
    logger.debug("Listing available scenario types")
    types = get_scenario_type()
    logger.debug(f"Returning {len(types)} scenario types")
    return {"status": "success", "scenario_types": types}

# ── Greenfield: Jira / Xray ────────────────────────────────────────────────
@app.post("/v1/generate-test-cases/bulk", response_model=BulkJobResponse, status_code=202,tags=["Greenfield"],summary="Submit a batch of user stories for async processing and push results to Jira/Xray or qTest or Azure Devops")
async def bulk_generate_test_cases(request: BulkRequest, background_tasks: BackgroundTasks):
    """
    Submit a batch of user stories for async processing and push results to Jira/Xray or qTest or Azure Devops.
    Returns a job_id immediately. Poll GET /v1/jobs/{job_id} for status and results.
    """
    target_system = os.getenv("TEST_CASE_PROVIDER", "jira").strip().lower()
    if target_system not in ("jira", "qtest", "azure_devops"):
        raise HTTPException(status_code=500, detail="Invalid TARGET_SYSTEM. Set TARGET_SYSTEM to 'jira' or 'qtest'.")

    logger.info(f"Received bulk test case generation request with {len(request.userStories)} stories for target={target_system}")
    logger.debug(f"Scenario types: {request.ScenarioTypes}")
    try:
        _validate_scenario_types(request.ScenarioTypes)
        job_id, entry = _create_job_entry(request.userStories, request.ScenarioTypes)
        with _jobs_lock:
            _jobs[job_id] = entry
            _job_inputs[job_id] = request.userStories
            _job_targets[job_id] = target_system
        logger.info(f"Job {job_id} submitted for async processing ({target_system})")
        if target_system == "qtest":
            background_tasks.add_task(run_bulk_job_qtest,job_id, request.userStories, request.ScenarioTypes, _jobs, _jobs_lock)
            submit_message = f"qTest job submitted with {len(request.userStories)} stories and {len(request.ScenarioTypes)} scenario types. Poll /v1/jobs/{job_id} for status."
        elif target_system == "azure_devops":
            background_tasks.add_task(run_bulk_job_ado, job_id, request.userStories, request.ScenarioTypes, _jobs, _jobs_lock)
            submit_message = f"Azure DevOps job submitted with {len(request.userStories)} stories and {len(request.ScenarioTypes)} scenario types. Poll /v1/jobs/{job_id} for status."
        else:
            background_tasks.add_task(run_bulk_job_jira,job_id, request.userStories, request.ScenarioTypes, _jobs, _jobs_lock)
            submit_message = f"Jira job submitted with {len(request.userStories)} stories and {len(request.ScenarioTypes)} scenario types. Poll /v1/jobs/{job_id} for status."
        return {
            "job_id":    job_id,
            "total":     len(request.userStories),
            "message":   submit_message,
            "poll_url":  f"/v1/jobs/{job_id}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk_generate_test_cases: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ── Brownfield: update existing Jira/Xray test cases ──────────────────────
@app.post("/v1/generate-test-cases/bulk/brownfield",response_model=BulkJobResponse,status_code=202,summary="Brownfield: update & gap-fill existing Jira/Xray test cases",tags=["Brownfield"])
async def bulk_update_test_cases_brownfield(request: BulkRequest, background_tasks: BackgroundTasks):
    """
    **Brownfield update pipeline** – use when test cases already exist in Jira/Xray
    for the supplied user story IDs and you want to update them and fill in coverage gaps, instead of creating from scratch.
    For each (user story x scenario type) the API will:

    1. **Fetch** all existing Jira Test issues whose `label` equals `userStoryJiraId`.
    2. **Fetch** their Xray test steps via GraphQL.
    3. **Send** the user story + existing test cases to the LLM, asking it to:
       - Update outdated / incomplete test cases in-place.
       - Identify coverage gaps and generate new test cases.
    4. **Update** existing Jira issues (summary, description) and replace their Xray steps.
    5. **Create** brand-new Jira Test issues for gap-fill scenarios and link them to the
       configured test plan.

    If no existing test cases are found for a story, it automatically falls back to
    greenfield creation (identical to the `/bulk` endpoint).

    Returns `job_id` immediately. Poll `GET /v1/jobs/{job_id}` for status and results.
    """
    logger.info(f"Received brownfield test case update request with {len(request.userStories)} stories")
    logger.debug(f"Scenario types: {request.ScenarioTypes}")
    try:
        _validate_scenario_types(request.ScenarioTypes)
        job_id, entry = _create_job_entry(request.userStories, request.ScenarioTypes)
        with _jobs_lock:
            _jobs[job_id]        = entry
            _job_inputs[job_id]  = request.userStories
            _job_targets[job_id] = "jira_brownfield"
        logger.info(f"Brownfield job {job_id} submitted for async processing")
        background_tasks.add_task(run_bulk_brownfield_job_jira,job_id, request.userStories, request.ScenarioTypes, _jobs, _jobs_lock)
        return {
            "job_id":   job_id,
            "total":    len(request.userStories),
            "message":  (
                f"Brownfield job submitted with {len(request.userStories)} stories and "
                f"{len(request.ScenarioTypes)} scenario types. "
                f"Poll /v1/jobs/{job_id} for status."
            ),
            "poll_url": f"/v1/jobs/{job_id}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk_update_test_cases_brownfield: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ── Job status polling ─────────────────────────────────────────────────────
@app.get("/v1/jobs/{job_id}",tags=["Job Status"],summary="Poll the status and results of a bulk processing job")
async def get_job_status(job_id: str):
    """
    Poll the status of a bulk processing job.
    Job-level status:   pending | processing | passed | partial_passed | failed
    Story-level status: pending | processing | passed | partial_passed | failed
    """
    logger.debug(f"Status poll for job {job_id}")
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        logger.warning(f"Job {job_id} not found")
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    logger.debug(f"Returning status for job {job_id}: {job.get('status')}")
    return job

# ── Retry failed scenarios ─────────────────────────────────────────────────
@app.post("/v1/jobs/{job_id}/retry-failed", status_code=202,tags=["Job Status"],summary="Retry only the failed scenarios within a job")
async def retry_failed_stories(job_id: str, background_tasks: BackgroundTasks):
    """
    Rerun only the failed stories/scenarios within the same job (same job_id).
    Works for greenfield (jira / qtest) **and** brownfield jobs.
    Successful stories are left untouched. Poll GET /v1/jobs/{job_id} for updated status.
    """
    logger.info(f"Retry request received for job {job_id}")
    with _jobs_lock:
        job = _jobs.get(job_id)
        source_inputs = _job_inputs.get(job_id)
        target_system = _job_targets.get(job_id)
        if job is None:
            logger.warning(f"Job {job_id} not found for retry")
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        if job.get("status") == "processing":
            logger.warning(f"Job {job_id} is still processing, cannot retry")
            raise HTTPException(status_code=400,detail=f"Job '{job_id}' is currently processing. Wait for it to finish before retrying.")
        if not source_inputs:
            logger.warning(f"Job {job_id} has no original input payload for retry")
            raise HTTPException(status_code=400,detail="Original job input payload is not available. This can happen for jobs created before retry support was added.")
        scenario_types = job.get("ScenarioTypes", [])
        if not scenario_types:
            logger.warning(f"Job {job_id} has no scenario types")
            raise HTTPException(status_code=400, detail=f"Job '{job_id}' has no ScenarioTypes")
        failed_indexes = _get_failed_story_indexes(job, scenario_types)
        if not failed_indexes:
            logger.warning(f"Job {job_id} has no failed stories to retry")
            raise HTTPException(status_code=400, detail=f"Job '{job_id}' has no failed stories to retry")
        logger.info(f"Found {len(failed_indexes)} failed stories to retry in job {job_id}")
        #Build retry_items and reset each failed scenario back to pending in-place
        retry_items: List[tuple] = []
        for idx in failed_indexes:
            if idx >= len(source_inputs):
                continue
            story_state = job["stories"][idx]
            for st in scenario_types:
                if (story_state["results_by_scenario"].get(st) or {}).get("status") == "failed":
                    story_state["results_by_scenario"][st] = {"status": "pending"}
                    retry_items.append((idx, source_inputs[idx], st))
            story_state["status"] = "pending"
        if not retry_items:
            logger.warning(f"Job {job_id} could not identify failed scenario-level tasks to retry")
            raise HTTPException(status_code=400, detail="Could not identify failed scenario-level tasks to retry.")
        logger.debug(f"Resetting job {job_id} status and counts for retry")
        # Recompute counts reflecting the reset states
        completed = failed = 0
        for s in job["stories"]:
            for st in scenario_types:
                status = (s["results_by_scenario"].get(st) or {}).get("status")
                if status in ("passed", "partial_passed"):
                    completed += 1
                elif status == "failed":
                    failed += 1
        job["completed_count"] = completed
        job["failed_count"] = failed
        job["status"] = "processing"
        job["completed_at"] = None
    # Dispatch to the right rerun handler
    logger.info(f"Dispatching {len(retry_items)} retry tasks for job {job_id} to {target_system}")
    if target_system == "qtest":
        background_tasks.add_task(_rerun_failed_same_job_qtest, job_id, retry_items, scenario_types)
    elif target_system == "jira_brownfield":
        # Brownfield retry reuses the brownfield runner for failed items
        # Build mini story list preserving original indexes
        mini_stories  = [story for _, story, _ in retry_items]
        mini_scenario = list(dict.fromkeys(st for _, _, st in retry_items))  # dedup, order-preserving
        background_tasks.add_task(run_bulk_brownfield_job_jira, job_id, mini_stories, mini_scenario, _jobs, _jobs_lock)
    else:
        background_tasks.add_task(_rerun_failed_same_job_jira, job_id, retry_items, scenario_types)
    return {
        "job_id": job_id,
        "total_retried":  len(retry_items),
        "message": (
            f"Retry started for {len(retry_items)} failed scenario(s) within job {job_id}. "
            f"Poll /v1/jobs/{job_id} for status."),"poll_url": f"/v1/jobs/{job_id}"}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    # Reload is for local development only. In Cloud Run / production it doubles
    # the memory footprint (parent + reloader child) and can cause spurious
    # restarts. Opt-in via UVICORN_RELOAD=1.
    logger.info(f"Starting FastAPI server on port {port}")
    logger.info(f"API endpoints available at http://localhost:{port}/docs")
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=True, log_level="info")
