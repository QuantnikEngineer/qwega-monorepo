from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class AgentClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0))

    async def close(self) -> None:
        await self._client.aclose()

    async def check_health(self, agent: str) -> dict[str, Any]:
        url = self._get_url(agent)
        if not url:
            return {"status": "not_configured"}
        try:
            response = await self._client.get(f"{url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            return {"status": "unhealthy", "error": str(exc)}

    async def call_ci_agent(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
        url = self._get_url("ci")
        if not url:
            raise ValueError("CI agent URL is not configured.")

        payload = context.get("ci_pipeline_request") or self._build_default_ci_request(message, context)
        render_mode = self._resolve_render_mode(context)
        if render_mode and "renderMode" not in payload:
            payload = {**payload, "renderMode": render_mode}
        try:
            response = await self._client.post(f"{url}/v1/pipelines/generate", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            return self._build_ci_error_response(exc.response)
        except httpx.HTTPError as exc:
            return {
                "status": "error",
                "message": "Unable to reach the CI agent.",
                "data": {
                    "error": {
                        "type": "transport_error",
                        "agent": "ci",
                        "detail": [str(exc)],
                    }
                },
                "suggested_actions": [
                    {
                        "action": "Retry CI pipeline generation",
                        "intent": "generate_ci_pipeline",
                        "agent": "ci",
                    }
                ],
            }

        data = response.json()
        return {
            "status": data.get("status", "success"),
            "message": data.get("message") or data.get("summary", "CI pipeline generated."),
            "data": data,
            "suggested_actions": [],
        }

    async def call_cd_agent(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
        url = self._get_url("cd")
        if not url:
            return {
                "status": "pending",
                "message": "CD agent repository is planned but not wired yet. CI agent generation is available now.",
                "data": {"message": "CD agent not configured."},
                "suggested_actions": [
                    {
                        "action": "Generate a CI pipeline instead",
                        "intent": "generate_ci_pipeline",
                        "agent": "ci",
                    }
                ],
            }
        return {
            "status": "pending",
            "message": f"CD agent endpoint is configured at {url} but no implementation contract has been added yet.",
            "data": {"message": "CD routing stub only."},
            "suggested_actions": [],
        }

    def _get_url(self, agent: str) -> str:
        if agent == "ci":
            return settings.ci_agent_url.rstrip("/")
        if agent == "cd":
            return settings.cd_agent_url.rstrip("/") if settings.cd_agent_url else ""
        return ""

    def _build_ci_error_response(self, response: httpx.Response) -> dict[str, Any]:
        payload = self._safe_json(response)
        details = self._extract_error_detail(response, payload)
        error_type = "guardrail_validation" if response.status_code == 400 else "upstream_http_error"
        detail_summary = details[0] if details else None
        if detail_summary and len(details) > 1:
            detail_summary = f"{detail_summary} (+{len(details) - 1} more)"
        message = (
            f"CI pipeline request failed guardrail validation: {detail_summary}"
            if response.status_code == 400
            else f"CI agent request failed with status {response.status_code}: {detail_summary}"
        )
        return {
            "status": "error",
            "message": message,
            "data": {
                "error": {
                    "type": error_type,
                    "agent": "ci",
                    "status_code": response.status_code,
                    "detail": details,
                    "upstream": payload,
                }
            },
            "suggested_actions": [
                {
                    "action": "Revise CI pipeline inputs and retry",
                    "intent": "generate_ci_pipeline",
                    "agent": "ci",
                }
            ],
        }

    def _safe_json(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _extract_error_detail(self, response: httpx.Response, payload: Any) -> list[str]:
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, list):
                return [str(item) for item in detail]
            if detail is not None:
                return [str(detail)]

        body = response.text.strip()
        if body:
            return [body]
        return [f"CI agent returned HTTP {response.status_code}."]

    def _build_default_ci_request(self, message: str, context: dict[str, Any]) -> dict[str, Any]:
        project_name = context.get("project_name") or context.get("projectName") or "quantnik-deployment-pipeline"
        pipeline_name = str(project_name).strip().lower().replace(" ", "-") + "-ci"
        payload = {
            "schemaVersion": "2.0.0",
            "mode": "deployment-orchestrator",
            "prompt": message,
            "assistantMode": "assistive-prefill",
            "pipelineName": pipeline_name,
            "target": {
                "platform": "azure-devops",
                "deploymentTarget": "kubernetes",
                "environment": "qa",
            },
            "repository": {
                "url": context.get("repository_url") or context.get("repositoryUrl"),
                "branch": context.get("branch") or "main",
            },
            "build": {
                "language": context.get("language") or "node",
                "framework": context.get("framework") or "react",
                "tool": context.get("build_tool") or context.get("buildTool") or "npm",
                "artifactType": context.get("artifact_type") or context.get("artifactType") or "container",
            },
            "quality": {
                "coverage": {
                    "enabled": True,
                    "minimum": 75,
                }
            },
            "execution": {
                "triggers": {"push": True, "pullRequest": True},
                "managedAgents": True,
                "caching": True,
                "parallelism": True,
                "failFast": True,
                "timeoutMinutes": 30,
            },
            "tools": [
                {"id": "unit-tests", "name": "Unit Tests", "category": "Build and Validation"},
                {"id": "linting", "name": "Linting", "category": "Build and Validation"},
                {"id": "gitleaks", "name": "Gitleaks", "category": "Quality and Security"},
                {"id": "docker-build", "name": "Docker Build", "category": "Packaging and Delivery"},
                {"id": "artifact-publish", "name": "Artifact Publish", "category": "Packaging and Delivery"},
            ],
            "stages": [
                {"order": 1, "stageId": "checkout", "name": "Checkout", "tools": []},
                {"order": 2, "stageId": "restore", "name": "Restore Dependencies", "tools": ["npm"]},
                {"order": 3, "stageId": "build", "name": "Build", "tools": ["npm"]},
                {"order": 4, "stageId": "unit-test", "name": "Unit Test", "tools": ["Unit Tests"]},
                {"order": 5, "stageId": "lint", "name": "Lint", "tools": ["Linting"]},
                {"order": 6, "stageId": "secret-scan", "name": "Secret Scan", "tools": ["Gitleaks"]},
                {"order": 7, "stageId": "docker-build", "name": "Docker Build", "tools": ["Docker Build"]},
                {"order": 8, "stageId": "publish-artifacts", "name": "Publish Artifacts", "tools": ["Artifact Publish"]},
            ],
        }
        render_mode = self._resolve_render_mode(context)
        if render_mode:
            payload["renderMode"] = render_mode
        return payload

    def _resolve_render_mode(self, context: dict[str, Any]) -> str | None:
        explicit_mode = context.get("render_mode") or context.get("renderMode")
        if isinstance(explicit_mode, str):
            normalized = explicit_mode.strip().lower()
            if normalized in {"template", "llm", "hybrid"}:
                return normalized

        use_llm = context.get("use_llm_rendering")
        if use_llm is None:
            use_llm = context.get("useLlmRendering")
        if use_llm is None:
            return None
        return "llm" if self._coerce_bool(use_llm) else "template"

    def _coerce_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "llm"}
        return bool(value)


_agent_client: AgentClient | None = None


def get_agent_client() -> AgentClient:
    global _agent_client
    if _agent_client is None:
        _agent_client = AgentClient()
    return _agent_client