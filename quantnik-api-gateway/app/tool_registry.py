"""Gateway tool registry — explicit allowlist of tools that can be proxied.

This is a security boundary: only tools listed here get proxy routes registered.
The ToolAdapter for each tool defines its upstream path handling and any extra headers.
Auth strategy is owned by the auth-service, not duplicated here.

To add a new tool: add one ToolAdapter entry below and ensure the auth-service
service_registry has a matching tool_id with the correct _auth_type in default_config.
"""

from app.models.tool_adapter import ToolAdapter

TOOL_ADAPTERS: dict[str, ToolAdapter] = {
    "jira": ToolAdapter(
        tool_id="jira",
        prefix="/jira",
    ),
    "confluence": ToolAdapter(
        tool_id="confluence",
        prefix="/confluence",
        upstream_path_prefix="/wiki",
    ),
    "github": ToolAdapter(
        tool_id="github",
        prefix="/github",
    ),
    "qtest": ToolAdapter(
        tool_id="qtest",
        prefix="/qtest",
    ),
    "sonarqube": ToolAdapter(
        tool_id="sonarqube",
        prefix="/sonarqube",
    ),
    "sharepoint": ToolAdapter(
        tool_id="sharepoint",
        prefix="/sharepoint",
    ),
    "harness-pipelines": ToolAdapter(
        tool_id="harness-pipelines",
        prefix="/harness-pipelines",
    ),
    "harness-repo": ToolAdapter(
        tool_id="harness-repo",
        prefix="/harness-repo",
    ),
    "snyk": ToolAdapter(
        tool_id="snyk",
        prefix="/snyk",
    ),
    "trivy": ToolAdapter(
        tool_id="trivy",
        prefix="/trivy",
    ),
}
