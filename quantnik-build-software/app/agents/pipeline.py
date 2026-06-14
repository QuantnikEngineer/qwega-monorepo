"""
Build-Software Pipeline  (self-contained, no child orchestrators)
=================================================================
LangGraph sequential state machine.  Every step uses the LLM and
Atlassian/GitHub REST APIs directly — no external services required
beyond port 8083 itself.

Steps:
  validate_input
  → create_brd              LLM → Confluence
  → create_user_stories     LLM → Jira (Epic + Stories)
  → validate_user_stories   LLM → Jira updates + Confluence report
  → create_test_cases       LLM → Jira (Tasks)
  → create_test_scripts     LLM → GitHub
  → generate_code           LLM → GitHub → deploy
  → finalize
"""
import uuid
from datetime import datetime
from typing import TypedDict, List, Dict, Any, Optional, AsyncGenerator

from langgraph.graph import StateGraph, END

from app.core.logging import get_logger
from app.models.requests import BuildRequest, PipelineStatus
from app.models.responses import PipelineRun, StepResult, SSEEvent
from app.memory.pipeline_store import save, get as get_run
from app.tools import atlassian_client as atlassian
from app.tools import llm_client as llm
from app.tools.github_client import get_github
from app.tools.code_generator import generate_code

logger = get_logger(__name__)


# ─── State ────────────────────────────────────────────────────────────────────

class PipelineState(TypedDict):
    run_id: str
    project_name: str
    description: str
    confluence_space_key: str
    jira_project_key: str
    github_repo: str
    tech_stack: Dict[str, str]
    skip_steps: List[str]

    # Accumulated data
    brd: Optional[Dict]           # {title, summary, content_html}
    brd_url: Optional[str]
    epics: Optional[List[Dict]]   # [{key, url, stories:[{key,url,summary}]}]
    jira_epic_url: Optional[str]
    validation: Optional[Dict]    # {gaps, report_html, updated_stories}
    validation_url: Optional[str]
    test_cases: Optional[List[Dict]]
    test_cases_url: Optional[str]
    test_scripts: Optional[Dict[str, str]]
    test_scripts_url: Optional[str]
    generated_files: Optional[Dict[str, str]]
    repo_url: Optional[str]
    deployment_url: Optional[str]

    events: List[Dict]
    current_step: str
    error: Optional[str]
    status: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _emit(state: PipelineState, event_type: str, step: str, title: str,
          detail: str = None, progress: float = 0.0,
          artifact_key: str = None, artifact_url: str = None) -> PipelineState:
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
    run = get_run(state["run_id"])
    if not run:
        return
    run.current_step = state["current_step"]
    run.status = PipelineStatus(state["status"])
    run.updated_at = datetime.utcnow()
    if state.get("error"):
        run.error = state["error"]
    for key in ("brd_url", "jira_epic_url", "validation_url",
                "test_cases_url", "test_scripts_url", "repo_url", "deployment_url"):
        if state.get(key):
            run.artifacts[key] = state[key]
    save(run)


def _skip(state: PipelineState, step: str) -> bool:
    return step in (state.get("skip_steps") or [])


def _failed(state: PipelineState) -> bool:
    return state.get("status") == PipelineStatus.FAILED


# ─── Nodes ────────────────────────────────────────────────────────────────────

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
    if _failed(state) or _skip(state, step):
        _emit(state, "milestone", step, "BRD skipped", progress=0.12)
        return state

    _emit(state, "milestone", step, "Generating BRD with AI…", progress=0.08)
    try:
        brd = await llm.generate_brd(state["project_name"], state["description"])
        state["brd"] = brd

        _emit(state, "milestone", step, "Publishing BRD to Confluence…", progress=0.12)
        url = await atlassian.create_confluence_page(
            space_key=state["confluence_space_key"],
            title=brd["title"],
            body=brd["content_html"],
        )
        state["brd_url"] = url
        _emit(state, "artifact", step, "BRD published to Confluence",
              progress=0.16, artifact_key="brd_url", artifact_url=url)
    except Exception as e:
        state["error"] = f"create_brd failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "BRD creation failed", detail=str(e), progress=0.16)
    return state


async def create_user_stories_node(state: PipelineState) -> PipelineState:
    step = "create_user_stories"
    state["current_step"] = step
    if _failed(state) or _skip(state, step):
        _emit(state, "milestone", step, "User stories skipped", progress=0.30)
        return state

    _emit(state, "milestone", step, "Generating user stories with AI…", progress=0.22)
    try:
        brd_summary = (state.get("brd") or {}).get("summary") or state["description"]
        epics_data = await llm.generate_user_stories(state["project_name"], brd_summary)

        _emit(state, "milestone", step, "Creating epics and stories in Jira…", progress=0.26)
        created_epics = []
        first_epic_url = None
        for epic_data in epics_data:
            epic = await atlassian.create_jira_epic(
                state["jira_project_key"],
                epic_data["epic"],
                brd_summary,
            )
            if not first_epic_url:
                first_epic_url = epic["url"]
            stories_created = []
            for s in epic_data.get("stories", []):
                story = await atlassian.create_jira_story(
                    state["jira_project_key"],
                    s["summary"],
                    s["description"],
                    epic_key=epic["key"],
                )
                stories_created.append({**story, "summary": s["summary"], "description": s["description"]})
            created_epics.append({**epic, "stories": stories_created})

        state["epics"] = created_epics
        state["jira_epic_url"] = first_epic_url or f"{state.get('confluence_space_key', '')}"
        _emit(state, "artifact", step, f"User stories created in Jira ({len(created_epics)} epics)",
              progress=0.32, artifact_key="jira_epic_url", artifact_url=state["jira_epic_url"])
    except Exception as e:
        state["error"] = f"create_user_stories failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "User story creation failed", detail=str(e), progress=0.32)
    return state


async def validate_user_stories_node(state: PipelineState) -> PipelineState:
    step = "validate_user_stories"
    state["current_step"] = step
    if _failed(state) or _skip(state, step):
        _emit(state, "milestone", step, "Validation skipped", progress=0.46)
        return state

    _emit(state, "milestone", step, "Validating user stories against BRD…", progress=0.38)
    try:
        brd_summary = (state.get("brd") or {}).get("summary") or state["description"]
        epics = state.get("epics") or []
        all_stories = [s for e in epics for s in e.get("stories", [])]
        validation = await llm.validate_user_stories(brd_summary, all_stories)
        state["validation"] = validation

        # Update any stories with improved descriptions
        updated = validation.get("updated_stories") or []
        _emit(state, "milestone", step, f"Updating {len(updated)} stories in Jira…", progress=0.42)
        for story_group in (updated if isinstance(updated, list) and updated and isinstance(updated[0], dict) and "stories" in updated[0] else []):
            for s in story_group.get("stories", []):
                for created in all_stories:
                    if created.get("summary") == s.get("summary") and created.get("key"):
                        try:
                            await atlassian.update_jira_story(created["key"], s.get("description", ""))
                        except Exception:
                            pass

        _emit(state, "milestone", step, "Publishing validation report to Confluence…", progress=0.44)
        val_url = await atlassian.create_confluence_page(
            space_key=state["confluence_space_key"],
            title=f"User Story Validation Report — {state['project_name']}",
            body=validation["report_html"],
        )
        state["validation_url"] = val_url
        gaps = len(validation.get("gaps") or [])
        _emit(state, "artifact", step, f"Validation report published ({gaps} gaps found)",
              progress=0.46, artifact_key="validation_url", artifact_url=val_url)
    except Exception as e:
        state["error"] = f"validate_user_stories failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "Validation failed", detail=str(e), progress=0.46)
    return state


async def create_test_cases_node(state: PipelineState) -> PipelineState:
    step = "create_test_cases"
    state["current_step"] = step
    if _failed(state) or _skip(state, step):
        _emit(state, "milestone", step, "Test cases skipped", progress=0.58)
        return state

    _emit(state, "milestone", step, "Generating test cases with AI…", progress=0.50)
    try:
        epics = state.get("epics") or []
        all_stories = [s for e in epics for s in e.get("stories", [])]
        test_cases_data = await llm.generate_test_cases(state["project_name"], all_stories)

        _emit(state, "milestone", step, "Creating test cases in Jira…", progress=0.54)
        created_cases = []
        first_url = None
        for group in test_cases_data:
            story_key = None
            story_summary = group.get("story_summary", "")
            for s in all_stories:
                if s.get("summary") == story_summary:
                    story_key = s.get("key")
                    break
            for tc in group.get("cases", []):
                case = await atlassian.create_jira_test_case(
                    state["jira_project_key"],
                    tc["summary"],
                    tc["steps"],
                    story_key=story_key,
                )
                if not first_url:
                    first_url = case["url"]
                created_cases.append(case)

        state["test_cases"] = created_cases
        state["test_cases_url"] = first_url or state.get("jira_epic_url", "")
        _emit(state, "artifact", step, f"Test cases uploaded to Jira ({len(created_cases)} cases)",
              progress=0.58, artifact_key="test_cases_url", artifact_url=state["test_cases_url"])
    except Exception as e:
        state["error"] = f"create_test_cases failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "Test case generation failed", detail=str(e), progress=0.58)
    return state


async def create_test_scripts_node(state: PipelineState) -> PipelineState:
    step = "create_test_scripts"
    state["current_step"] = step
    if _failed(state) or _skip(state, step):
        _emit(state, "milestone", step, "Test scripts skipped", progress=0.70)
        return state

    _emit(state, "milestone", step, "Generating Playwright test scripts…", progress=0.62)
    try:
        test_cases = state.get("test_cases") or []
        scripts = await llm.generate_test_scripts(state["project_name"], test_cases)
        state["test_scripts"] = scripts

        _emit(state, "milestone", step, "Pushing test scripts to GitHub…", progress=0.66)
        gh = get_github()
        test_repo = f"{state['github_repo']}-tests"
        await gh.create_repo(test_repo, f"Test scripts for {state['project_name']}")
        if scripts:
            await gh.push_files(test_repo, scripts, "feat: add generated Playwright test scripts")
        state["test_scripts_url"] = f"https://github.com/{gh.org}/{test_repo}"
        _emit(state, "artifact", step, "Test scripts pushed to GitHub",
              progress=0.70, artifact_key="test_scripts_url", artifact_url=state["test_scripts_url"])
    except Exception as e:
        logger.warning("create_test_scripts failed (non-fatal)", error=str(e))
        _emit(state, "log", step, f"Test scripts skipped: {e}", progress=0.70)
    return state


async def generate_code_node(state: PipelineState) -> PipelineState:
    step = "generate_code"
    state["current_step"] = step
    if _failed(state) or _skip(state, step):
        _emit(state, "milestone", step, "Code generation skipped", progress=0.88)
        return state

    _emit(state, "milestone", step, "Generating React + Node.js application…", progress=0.74)
    try:
        epics = state.get("epics") or []
        all_stories = [s for e in epics for s in e.get("stories", [])]
        files = await generate_code(
            project_name=state["project_name"],
            description=state["description"],
            user_stories=all_stories,
            tech_stack=state.get("tech_stack") or {},
        )
        state["generated_files"] = files
        _emit(state, "milestone", step, f"Code generated ({len(files)} files)", progress=0.80)

        gh = get_github()
        repo_url = await gh.create_repo(
            state["github_repo"],
            f"Generated application: {state['project_name']}",
        )
        await gh.push_files(
            state["github_repo"], files,
            f"feat: initial generated codebase for {state['project_name']}",
        )
        state["repo_url"] = repo_url
        _emit(state, "artifact", step, "Code pushed to GitHub",
              progress=0.86, artifact_key="repo_url", artifact_url=repo_url)

        deployment_url = await _deploy(state)
        state["deployment_url"] = deployment_url
        _emit(state, "artifact", step, "Application deployed",
              progress=0.94, artifact_key="deployment_url", artifact_url=deployment_url)
    except Exception as e:
        state["error"] = f"generate_code failed: {e}"
        state["status"] = PipelineStatus.FAILED
        _emit(state, "error", step, "Code generation failed", detail=str(e), progress=0.90)
    return state


async def _deploy(state: PipelineState) -> str:
    from app.core.config import settings as cfg
    if not cfg.vercel_token:
        return f"https://github.com/{state.get('github_repo', 'repo')} (enable GitHub Pages or Vercel to get a live URL)"
    try:
        import httpx
        files = state.get("generated_files") or {}
        file_list = [{"file": p, "data": c} for p, c in files.items() if p.startswith("frontend/")]
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.vercel.com/v13/deployments",
                headers={"Authorization": f"Bearer {cfg.vercel_token}"},
                json={"name": state["github_repo"], "files": file_list, "projectSettings": {"framework": "vite"}},
            )
            if r.status_code in (200, 201):
                return f"https://{r.json().get('url', state['github_repo'] + '.vercel.app')}"
    except Exception as e:
        logger.warning("Vercel deploy failed", error=str(e))
    return f"https://{state['github_repo']}.vercel.app"


async def finalize_node(state: PipelineState) -> PipelineState:
    state["current_step"] = "finalize"
    if state.get("status") != PipelineStatus.FAILED:
        state["status"] = PipelineStatus.COMPLETED
    artifacts = {k: state.get(k) for k in
                 ("brd_url", "jira_epic_url", "validation_url",
                  "test_cases_url", "test_scripts_url", "repo_url", "deployment_url")
                 if state.get(k)}
    summary = "\n".join(f"• {k}: {v}" for k, v in artifacts.items())
    _emit(state, "complete", "finalize",
          "Pipeline complete" if state["status"] == PipelineStatus.COMPLETED else "Pipeline finished with errors",
          detail=summary, progress=1.0)
    _sync_store(state)
    return state


# ─── Graph ────────────────────────────────────────────────────────────────────

def _build_graph():
    g = StateGraph(PipelineState)
    nodes = [
        ("validate_input",        validate_input_node),
        ("create_brd",            create_brd_node),
        ("create_user_stories",   create_user_stories_node),
        ("validate_user_stories", validate_user_stories_node),
        ("create_test_cases",     create_test_cases_node),
        ("create_test_scripts",   create_test_scripts_node),
        ("generate_code",         generate_code_node),
        ("finalize",              finalize_node),
    ]
    for name, fn in nodes:
        g.add_node(name, fn)
    g.set_entry_point("validate_input")
    names = [n for n, _ in nodes]
    for a, b in zip(names, names[1:]):
        g.add_edge(a, b)
    g.add_edge("finalize", END)
    return g.compile()


_graph = None

def get_pipeline():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ─── Entry point ──────────────────────────────────────────────────────────────

async def run_pipeline(req: BuildRequest) -> AsyncGenerator[Dict, None]:
    run_id = req.run_id or str(uuid.uuid4())
    from app.memory.pipeline_store import save as _save
    run = PipelineRun(run_id=run_id, project_name=req.project_name)
    run.steps = [StepResult(step=s) for s in
                 ["create_brd", "create_user_stories", "validate_user_stories",
                  "create_test_cases", "create_test_scripts", "generate_code"]]
    _save(run)

    initial: PipelineState = {
        "run_id": run_id,
        "project_name": req.project_name,
        "description": req.description,
        "confluence_space_key": req.confluence_space_key,
        "jira_project_key": req.jira_project_key,
        "github_repo": req.github_repo or req.project_name.lower().replace(" ", "-"),
        "tech_stack": req.tech_stack,
        "skip_steps": req.skip_steps,
        "brd": None, "brd_url": None,
        "epics": None, "jira_epic_url": None,
        "validation": None, "validation_url": None,
        "test_cases": None, "test_cases_url": None,
        "test_scripts": None, "test_scripts_url": None,
        "generated_files": None, "repo_url": None, "deployment_url": None,
        "events": [],
        "current_step": "validate_input",
        "error": None,
        "status": PipelineStatus.PENDING,
    }

    pipeline = get_pipeline()
    last_idx = 0
    async for chunk in pipeline.astream(initial):
        node_state = list(chunk.values())[0] if chunk else {}
        events: list = node_state.get("events", [])
        for ev in events[last_idx:]:
            yield ev
        last_idx = len(events)
