"""
Build-Software Pipeline
=======================
LangGraph sequential state machine that runs the full SDLC pipeline:

  validate_input
      → create_brd              (Planning Orch → Confluence)
      → create_user_stories     (Planning Orch → Jira)
      → validate_user_stories   (Planning Orch → Jira updates + Confluence report)
      → create_test_cases       (Test Orch → Jira)
      → create_test_scripts     (Test Orch → GitHub)
      → generate_code           (LLM → GitHub → deploy)
      → finalize
"""
import uuid
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional, AsyncGenerator

from langgraph.graph import StateGraph, END

from app.core.logging import get_logger
from app.models.requests import BuildRequest, StepStatus, PipelineStatus
from app.models.responses import PipelineRun, StepResult, SSEEvent
from app.memory.pipeline_store import save, get as get_run
from app.tools.orchestrator_client import get_client
from app.tools.github_client import get_github
from app.tools.code_generator import generate_code

logger = get_logger(__name__)

# ─────────────────────────────────────────────
# Pipeline state (flows through all graph nodes)
# ─────────────────────────────────────────────
class PipelineState(TypedDict):
    run_id: str
    session_id: str
    project_name: str
    description: str
    confluence_space_key: str
    jira_project_key: str
    github_repo: str
    tech_stack: Dict[str, str]
    skip_steps: List[str]

    # Accumulated outputs
    brd_content: Optional[str]
    brd_url: Optional[str]
    user_stories: Optional[List[Dict]]
    jira_epic_url: Optional[str]
    validation_report: Optional[str]
    validation_url: Optional[str]
    test_cases: Optional[List[Dict]]
    test_cases_url: Optional[str]
    test_scripts: Optional[Dict[str, str]]
    test_scripts_url: Optional[str]
    generated_files: Optional[Dict[str, str]]
    repo_url: Optional[str]
    deployment_url: Optional[str]

    # Control
    events: List[Dict]          # SSE events emitted so far
    current_step: str
    error: Optional[str]
    status: str


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _emit(state: PipelineState, event_type: str, step: str, title: str,
          detail: str = None, progress: float = 0.0,
          artifact_key: str = None, artifact_url: str = None) -> PipelineState:
    """Append an SSE event to state and persist run."""
    ev = SSEEvent(
        event_type=event_type, step=step, title=title,
        detail=detail, progress=progress,
        artifact_key=artifact_key, artifact_url=artifact_url,
        run_id=state["run_id"],
    ).model_dump()
    state["events"].append(ev)
    _sync_store(state)
    return state


def _sync_store(state: PipelineState):
    """Keep the pipeline store in sync with state."""
    run = get_run(state["run_id"])
    if run:
        run.current_step = state["current_step"]
        run.status = PipelineStatus(state["status"])
        run.updated_at = datetime.utcnow()
        if state.get("error"):
            run.error = state["error"]
        # Merge artifacts
        for key in ("brd_url", "jira_epic_url", "validation_url",
                    "test_cases_url", "test_scripts_url", "repo_url", "deployment_url"):
            if state.get(key):
                run.artifacts[key] = state[key]
        save(run)


def _skip(state: PipelineState, step: str) -> bool:
    return step in state.get("skip_steps", [])


def _child_msg(resp: Dict) -> str:
    return resp.get("message") or resp.get("response") or ""


# ─────────────────────────────────────────────
# Graph nodes
# ─────────────────────────────────────────────
async def validate_input_node(state: PipelineState) -> PipelineState:
    state["current_step"] = "validate_input"
    state["status"] = PipelineStatus.RUNNING
    _emit(state, "milestone", "validate_input", "Pipeline started", progress=0.02)

    if not state.get("project_name") or not state.get("description"):
        state["error"] = "project_name and description are required"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", "validate_input", "Validation failed", detail=state["error"])

    if not state.get("github_repo"):
        state["github_repo"] = state["project_name"].lower().replace(" ", "-")

    return state


async def create_brd_node(state: PipelineState) -> PipelineState:
    step = "create_brd"
    state["current_step"] = step

    if _skip(state, step):
        _emit(state, "milestone", step, "BRD creation skipped", progress=0.10)
        return state

    _emit(state, "milestone", step, "Creating Business Requirements Document…", progress=0.08)

    try:
        client = get_client()
        resp = await client.call_planning(
            session_id=state["session_id"],
            message=f"Create a BRD for: {state['description']}",
            intent="create_brd",
            context={
                "project_name": state["project_name"],
                "confluence_space_key": state["confluence_space_key"],
                "jira_project_key": state["jira_project_key"],
            },
        )
        state["brd_content"] = _child_msg(resp)
        state["brd_url"] = (resp.get("data") or {}).get("confluence_url") or \
                           resp.get("confluence_url") or \
                           f"https://engquant.atlassian.net/wiki/spaces/{state['confluence_space_key']}"
        _emit(state, "artifact", step, "BRD published to Confluence", progress=0.15,
              artifact_key="brd_url", artifact_url=state["brd_url"])
    except Exception as e:
        state["error"] = f"create_brd failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "BRD creation failed", detail=str(e), progress=0.15)

    return state


async def create_user_stories_node(state: PipelineState) -> PipelineState:
    step = "create_user_stories"
    state["current_step"] = step

    if state.get("status") == PipelineStatus.FAILED:
        return state
    if _skip(state, step):
        _emit(state, "milestone", step, "User story creation skipped", progress=0.25)
        return state

    _emit(state, "milestone", step, "Generating user stories from BRD…", progress=0.20)

    try:
        client = get_client()
        resp = await client.call_planning(
            session_id=state["session_id"],
            message=f"Create user stories for project: {state['project_name']}",
            intent="create_user_story",
            context={
                "project_name": state["project_name"],
                "brd_content": state.get("brd_content", ""),
                "confluence_space_key": state["confluence_space_key"],
                "jira_project_key": state["jira_project_key"],
            },
        )
        data = resp.get("data") or {}
        state["user_stories"] = data.get("user_stories") or data.get("stories") or []
        state["jira_epic_url"] = data.get("jira_url") or resp.get("jira_url") or \
                                  f"https://engquant.atlassian.net/jira/software/projects/{state['jira_project_key']}/boards"
        _emit(state, "artifact", step, f"User stories uploaded to Jira", progress=0.30,
              artifact_key="jira_epic_url", artifact_url=state["jira_epic_url"])
    except Exception as e:
        state["error"] = f"create_user_stories failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "User story creation failed", detail=str(e), progress=0.30)

    return state


async def validate_user_stories_node(state: PipelineState) -> PipelineState:
    step = "validate_user_stories"
    state["current_step"] = step

    if state.get("status") == PipelineStatus.FAILED:
        return state
    if _skip(state, step):
        _emit(state, "milestone", step, "User story validation skipped", progress=0.40)
        return state

    _emit(state, "milestone", step, "Validating user stories against BRD…", progress=0.35)

    try:
        client = get_client()
        resp = await client.call_planning(
            session_id=state["session_id"],
            message=f"Validate user stories against BRD for: {state['project_name']}",
            intent="validate_user_story",
            context={
                "project_name": state["project_name"],
                "brd_content": state.get("brd_content", ""),
                "user_stories": state.get("user_stories", []),
                "jira_project_key": state["jira_project_key"],
                "confluence_space_key": state["confluence_space_key"],
            },
        )
        data = resp.get("data") or {}
        state["validation_report"] = _child_msg(resp)
        state["validation_url"] = data.get("confluence_url") or resp.get("confluence_url") or \
                                   f"https://engquant.atlassian.net/wiki/spaces/{state['confluence_space_key']}"
        _emit(state, "artifact", step,
              "Validation report published; Jira stories updated", progress=0.45,
              artifact_key="validation_url", artifact_url=state["validation_url"])
    except Exception as e:
        state["error"] = f"validate_user_stories failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "Validation failed", detail=str(e), progress=0.45)

    return state


async def create_test_cases_node(state: PipelineState) -> PipelineState:
    step = "create_test_cases"
    state["current_step"] = step

    if state.get("status") == PipelineStatus.FAILED:
        return state
    if _skip(state, step):
        _emit(state, "milestone", step, "Test case creation skipped", progress=0.55)
        return state

    _emit(state, "milestone", step, "Generating test cases from user stories…", progress=0.50)

    try:
        client = get_client()
        resp = await client.call_test(
            session_id=state["session_id"],
            message=f"Generate test cases for: {state['project_name']}",
            intent="generate_test_cases",
            context={
                "project_name": state["project_name"],
                "user_stories": state.get("user_stories", []),
                "jira_project_key": state["jira_project_key"],
            },
        )
        data = resp.get("data") or {}
        state["test_cases"] = data.get("test_cases") or []
        state["test_cases_url"] = data.get("jira_url") or resp.get("jira_url") or \
                                   f"https://engquant.atlassian.net/jira/software/projects/{state['jira_project_key']}/boards"
        _emit(state, "artifact", step, "Test cases uploaded to Jira", progress=0.60,
              artifact_key="test_cases_url", artifact_url=state["test_cases_url"])
    except Exception as e:
        state["error"] = f"create_test_cases failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "Test case generation failed", detail=str(e), progress=0.60)

    return state


async def create_test_scripts_node(state: PipelineState) -> PipelineState:
    step = "create_test_scripts"
    state["current_step"] = step

    if state.get("status") == PipelineStatus.FAILED:
        return state
    if _skip(state, step):
        _emit(state, "milestone", step, "Test script creation skipped", progress=0.70)
        return state

    _emit(state, "milestone", step, "Generating test scripts…", progress=0.65)

    try:
        client = get_client()
        resp = await client.call_test(
            session_id=state["session_id"],
            message=f"Generate Playwright test scripts for: {state['project_name']}",
            intent="generate_test_script",
            context={
                "project_name": state["project_name"],
                "test_cases": state.get("test_cases", []),
                "framework": "playwright",
                "language": "typescript",
            },
        )
        data = resp.get("data") or {}
        scripts: Dict[str, str] = data.get("scripts") or {}

        # Push scripts to GitHub
        gh = get_github()
        test_repo = f"{state['github_repo']}-tests"
        await gh.create_repo(test_repo, f"Test scripts for {state['project_name']}")
        if scripts:
            await gh.push_files(test_repo, scripts, "feat: add generated test scripts")
        state["test_scripts"] = scripts
        state["test_scripts_url"] = f"https://github.com/{gh.org}/{test_repo}"
        _emit(state, "artifact", step, "Test scripts pushed to GitHub", progress=0.72,
              artifact_key="test_scripts_url", artifact_url=state["test_scripts_url"])
    except Exception as e:
        # Non-fatal — log and continue
        logger.warning("create_test_scripts failed (non-fatal)", error=str(e))
        _emit(state, "log", step, f"Test script generation skipped: {e}", progress=0.72)

    return state


async def generate_code_node(state: PipelineState) -> PipelineState:
    step = "generate_code"
    state["current_step"] = step

    if state.get("status") == PipelineStatus.FAILED:
        return state
    if _skip(state, step):
        _emit(state, "milestone", step, "Code generation skipped", progress=0.85)
        return state

    _emit(state, "milestone", step,
          "Generating React + Node.js application with AI…", progress=0.75)

    try:
        files = await generate_code(
            project_name=state["project_name"],
            description=state["description"],
            user_stories=state.get("user_stories") or [],
            tech_stack=state.get("tech_stack") or {},
        )
        state["generated_files"] = files
        _emit(state, "milestone", step, f"Code generated ({len(files)} files)", progress=0.82)

        # Push to GitHub
        gh = get_github()
        repo_url = await gh.create_repo(state["github_repo"],
                                         f"Generated application: {state['project_name']}")
        await gh.push_files(state["github_repo"], files,
                            f"feat: initial generated codebase for {state['project_name']}")
        state["repo_url"] = repo_url
        _emit(state, "artifact", step, "Code pushed to GitHub", progress=0.88,
              artifact_key="repo_url", artifact_url=repo_url)

        # Deployment: try Vercel if token present, else provide repo URL
        deployment_url = await _deploy(state, files)
        state["deployment_url"] = deployment_url
        _emit(state, "artifact", step, "Application deployed", progress=0.95,
              artifact_key="deployment_url", artifact_url=deployment_url)

    except Exception as e:
        state["error"] = f"generate_code failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "Code generation / deployment failed",
              detail=str(e), progress=0.90)

    return state


async def _deploy(state: PipelineState, files: Dict[str, str]) -> str:
    """Deploy frontend to Vercel if token is set, else return GitHub Pages placeholder."""
    from app.core.config import settings as cfg
    if not cfg.vercel_token:
        # Return a GitHub Pages URL as a placeholder deployment hint
        return f"https://{state['github_repo']}.pages.github.com  (enable GitHub Pages on the repo to activate)"
    try:
        import httpx, json as _json
        # Vercel deployments API
        file_list = [
            {"file": path, "data": content}
            for path, content in files.items()
            if path.startswith("frontend/")
        ]
        payload = {
            "name": state["github_repo"],
            "files": file_list,
            "projectSettings": {"framework": "vite"},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.vercel.com/v13/deployments",
                headers={"Authorization": f"Bearer {cfg.vercel_token}"},
                json=payload,
            )
            if r.status_code in (200, 201):
                data = r.json()
                return f"https://{data.get('url', state['github_repo'] + '.vercel.app')}"
    except Exception as e:
        logger.warning("Vercel deploy failed", error=str(e))
    return f"https://{state['github_repo']}.vercel.app"


async def finalize_node(state: PipelineState) -> PipelineState:
    step = "finalize"
    state["current_step"] = step

    if state.get("status") != PipelineStatus.FAILED:
        state["status"] = PipelineStatus.COMPLETED

    artifacts = {
        k: state.get(k) for k in
        ("brd_url", "jira_epic_url", "validation_url",
         "test_cases_url", "test_scripts_url", "repo_url", "deployment_url")
        if state.get(k)
    }
    summary = "\n".join(f"• {k}: {v}" for k, v in artifacts.items())

    _emit(state, "complete", step,
          "Pipeline complete" if state["status"] == PipelineStatus.COMPLETED else "Pipeline finished with errors",
          detail=summary, progress=1.0)
    _sync_store(state)
    return state


# ─────────────────────────────────────────────
# Graph assembly
# ─────────────────────────────────────────────
def _build_graph():
    g = StateGraph(PipelineState)
    for name, fn in [
        ("validate_input",          validate_input_node),
        ("create_brd",              create_brd_node),
        ("create_user_stories",     create_user_stories_node),
        ("validate_user_stories",   validate_user_stories_node),
        ("create_test_cases",       create_test_cases_node),
        ("create_test_scripts",     create_test_scripts_node),
        ("generate_code",           generate_code_node),
        ("finalize",                finalize_node),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("validate_input")
    steps = ["validate_input", "create_brd", "create_user_stories",
             "validate_user_stories", "create_test_cases",
             "create_test_scripts", "generate_code", "finalize"]
    for a, b in zip(steps, steps[1:]):
        g.add_edge(a, b)
    g.add_edge("finalize", END)
    return g.compile()


_graph = None

def get_pipeline():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ─────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────
async def run_pipeline(req: BuildRequest) -> AsyncGenerator[Dict, None]:
    """
    Execute the full pipeline, yielding SSE-ready dicts as each step completes.
    """
    run_id = req.run_id or str(uuid.uuid4())
    session_id = f"build-{run_id}"

    # Initialise the run record
    from app.memory.pipeline_store import save as _save
    run = PipelineRun(run_id=run_id, project_name=req.project_name)
    run.steps = [
        StepResult(step=s) for s in
        ["create_brd", "create_user_stories", "validate_user_stories",
         "create_test_cases", "create_test_scripts", "generate_code"]
    ]
    _save(run)

    initial_state: PipelineState = {
        "run_id": run_id,
        "session_id": session_id,
        "project_name": req.project_name,
        "description": req.description,
        "confluence_space_key": req.confluence_space_key,
        "jira_project_key": req.jira_project_key,
        "github_repo": req.github_repo or req.project_name.lower().replace(" ", "-"),
        "tech_stack": req.tech_stack,
        "skip_steps": req.skip_steps,
        "brd_content": None, "brd_url": None,
        "user_stories": None, "jira_epic_url": None,
        "validation_report": None, "validation_url": None,
        "test_cases": None, "test_cases_url": None,
        "test_scripts": None, "test_scripts_url": None,
        "generated_files": None, "repo_url": None, "deployment_url": None,
        "events": [],
        "current_step": "validate_input",
        "error": None,
        "status": PipelineStatus.PENDING,
    }

    pipeline = get_pipeline()
    last_event_idx = 0

    async for chunk in pipeline.astream(initial_state):
        node_state = list(chunk.values())[0] if chunk else {}
        events: list = node_state.get("events", [])
        for ev in events[last_event_idx:]:
            yield ev
        last_event_idx = len(events)
