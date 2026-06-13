"""
Quantnik Build-Software Orchestrator
=====================================
POST /v1/build          — start the full pipeline (streaming SSE)
POST /v1/build/async    — start async, returns run_id immediately
GET  /v1/build/{run_id} — poll status
GET  /v1/build/{run_id}/stream — re-stream events for a run
GET  /health
"""
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.models.requests import BuildRequest
from app.models.responses import PipelineRun, PipelineStatus
from app.agents.pipeline import run_pipeline, get_pipeline
from app.memory.pipeline_store import save, get as get_run, all_runs

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Build-Software Orchestrator starting", port=settings.port)
    get_pipeline()          # warm up LangGraph
    yield
    logger.info("Build-Software Orchestrator stopping")


app = FastAPI(
    title="Quantnik Build-Software Orchestrator",
    description="""
End-to-end software delivery pipeline:

1. **Create BRD** → publish to Confluence
2. **Create User Stories** → push to Jira
3. **Validate User Stories** → update Jira + publish report to Confluence
4. **Create Test Cases** → push to Jira
5. **Create Test Scripts** → push to GitHub
6. **Generate Code** (React + Node.js) → push to GitHub → deploy → return URL
""",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── SSE helper ───────────────────────────────────────────────────────────────
def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "timestamp": datetime.utcnow().isoformat(),
        "planning_url": settings.get_planning_url(),
        "test_url": settings.get_test_url(),
    }


@app.post("/v1/build", summary="Run full pipeline (streaming SSE)")
async def build_stream(req: BuildRequest):
    """
    Start the build pipeline and stream Server-Sent Events.
    Each event has: event_type, step, title, detail, progress (0-1), artifact_key, artifact_url.
    The final event has event_type='complete'.
    """
    async def generate():
        try:
            async for event in run_pipeline(req):
                yield _sse(event)
        except Exception as e:
            logger.error("Pipeline error", error=str(e))
            yield _sse({"event_type": "error", "step": "unknown",
                        "title": "Unexpected error", "detail": str(e), "progress": 1.0})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.post("/v1/build/async", summary="Start pipeline, return run_id immediately")
async def build_async(req: BuildRequest):
    """Fire-and-forget: returns run_id immediately. Poll /v1/build/{run_id} for status."""
    import asyncio
    run_id = req.run_id or str(uuid.uuid4())
    req.run_id = run_id

    run = PipelineRun(run_id=run_id, project_name=req.project_name)
    save(run)

    async def _bg():
        try:
            async for _ in run_pipeline(req):
                pass
        except Exception as e:
            logger.error("Background pipeline error", run_id=run_id, error=str(e))

    asyncio.create_task(_bg())

    return {
        "run_id": run_id,
        "status": PipelineStatus.RUNNING,
        "stream_url": f"/v1/build/{run_id}/stream",
        "status_url": f"/v1/build/{run_id}",
        "message": "Pipeline started. Poll status_url or connect to stream_url for live progress.",
    }


@app.get("/v1/build/{run_id}", summary="Poll pipeline status")
async def build_status(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run


@app.get("/v1/build/{run_id}/stream", summary="Re-stream events for a completed/running run")
async def build_restream(run_id: str):
    """Stream all events emitted so far for a run (useful for reconnecting clients)."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    async def generate():
        # Re-emit buffered events from the pipeline state
        # (events are stored in run.artifacts as a side-channel; for full replay
        #  integrate with Redis Streams or similar in production)
        yield _sse({"event_type": "milestone", "step": "connect",
                    "title": f"Connected to run {run_id}",
                    "detail": f"Current status: {run.status}", "progress": 0.0})
        for key, url in run.artifacts.items():
            yield _sse({"event_type": "artifact", "artifact_key": key,
                        "artifact_url": url, "title": key.replace("_", " ").title()})
        if run.status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED):
            yield _sse({"event_type": "complete", "step": "finalize",
                        "title": run.status.value, "progress": 1.0})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.get("/v1/builds", summary="List all pipeline runs")
async def list_builds():
    return [
        {"run_id": r.run_id, "project_name": r.project_name,
         "status": r.status, "created_at": r.created_at, "artifacts": r.artifacts}
        for r in all_runs().values()
    ]
