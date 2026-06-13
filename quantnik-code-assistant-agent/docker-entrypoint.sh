#!/bin/bash
# ---------------------------------------------------------------------------
# Docker Entrypoint - quantnik-code-assistant-agent
# ---------------------------------------------------------------------------
# 1. Loads environment-specific config from .env.{APP_PROFILE} file
# 2. Substitutes environment variables into mcp.json at container startup.
# This allows secrets from Cloud Run Secret Manager to be injected at runtime.
# ---------------------------------------------------------------------------

set -e

# ---------------------------------------------------------------------------
# STEP 1: Load environment-specific configuration based on APP_PROFILE
# ---------------------------------------------------------------------------
APP_PROFILE="${APP_PROFILE:-dev}"
ENV_FILE="/app/.env.${APP_PROFILE}"

if [ -f "$ENV_FILE" ]; then
  echo "Loading environment config from: $ENV_FILE"
  # Export all variables from the env file (skip comments and empty lines)
  set -a
  source "$ENV_FILE"
  set +a
  echo "Environment profile '$APP_PROFILE' loaded successfully"
else
  echo "WARNING: Environment file not found: $ENV_FILE"
  echo "Available profiles: dev, qa, stage"
fi

# ---------------------------------------------------------------------------
# STEP 2: Ensure droid CLI is in PATH
# ---------------------------------------------------------------------------
export PATH="/root/.local/bin:$PATH"

# Verify droid is accessible
if command -v droid &> /dev/null; then
  echo "droid CLI found: $(which droid)"
  droid --version || true
else
  echo "WARNING: droid CLI not found in PATH!"
  echo "PATH=$PATH"
  ls -la /root/.local/bin/ 2>/dev/null || echo "/root/.local/bin does not exist"
fi

MCP_TEMPLATE="/app/mcp.json.template"
MCP_TARGET="/root/.factory/mcp.json"

# ---------------------------------------------------------------------------
# Verify MCP server binaries exist at the absolute paths used in mcp.json.
# Fail fast with a clear log instead of producing a silent "not connected"
# error at runtime.
# ---------------------------------------------------------------------------
for bin in /usr/local/bin/mcp-atlassian /usr/local/bin/npx; do
  if [ ! -x "$bin" ]; then
    echo "ERROR: required MCP binary missing or not executable: $bin"
    exit 1
  fi
done
echo "MCP binaries verified: /usr/local/bin/mcp-atlassian, /usr/local/bin/npx"

# Derive ADO_ORG from ADO_ORGANIZATION_URL if not explicitly set
# (e.g. https://dev.azure.com/WiproPracticeWork -> WiproPracticeWork)
if [ -z "${ADO_ORG:-}" ] && [ -n "${ADO_ORGANIZATION_URL:-}" ]; then
  ADO_ORG="$(basename "$ADO_ORGANIZATION_URL")"
  export ADO_ORG
  echo "Derived ADO_ORG=$ADO_ORG from ADO_ORGANIZATION_URL"
fi

# Ensure .factory directory exists
mkdir -p /root/.factory

# Substitute environment variables in mcp.json template
if [ -f "$MCP_TEMPLATE" ]; then
  echo "Generating mcp.json from template..."

  # Render template: replace ${VAR} placeholders with env values
  envsubst < "$MCP_TEMPLATE" > "$MCP_TARGET"

  # Warn about any unresolved placeholders so the failure mode is obvious in logs
  if grep -q '\${' "$MCP_TARGET"; then
    echo "WARNING: mcp.json still contains unresolved variables:"
    grep -o '\${[A-Z_][A-Z0-9_]*}' "$MCP_TARGET" | sort -u | sed 's/^/  - /'
  fi

  echo "mcp.json generated successfully at $MCP_TARGET"
else
  echo "Warning: MCP template not found at $MCP_TEMPLATE"
fi

# ---------------------------------------------------------------------------
# STEP 3: Sanity-check Jira / Atlassian MCP credentials
# ---------------------------------------------------------------------------
# The Jira MCP server (sooperset/mcp-atlassian) is invoked as a stdio child
# process by droid. It reads JIRA_URL / JIRA_EMAIL / JIRA_API_TOKEN from the
# process environment (droid passes them through via the env block in
# mcp.json). We do not write any token files to disk.
if [ -z "$JIRA_URL" ] || [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_API_TOKEN" ]; then
  echo "WARNING: Jira MCP credentials missing — the 'jira' MCP server will fail to start."
  echo "  JIRA_URL=${JIRA_URL:-<unset>}"
  echo "  JIRA_EMAIL=${JIRA_EMAIL:+<set>}${JIRA_EMAIL:-<unset>}"
  echo "  JIRA_API_TOKEN=${JIRA_API_TOKEN:+<set>}${JIRA_API_TOKEN:-<unset>}"
  echo "  Run setup-secrets.sh to provision JIRA_EMAIL and JIRA_API_TOKEN in Secret Manager."
else
  echo "Jira MCP credentials present (URL=$JIRA_URL, user=$JIRA_EMAIL)"
fi

# Sanity-check Azure DevOps MCP credentials
if [ -z "${ADO_ORGANIZATION_URL:-}" ] || [ -z "${ADO_PAT:-}" ]; then
  echo "WARNING: Azure DevOps MCP credentials missing — the 'ado' MCP server will fail to start."
  echo "  ADO_ORGANIZATION_URL=${ADO_ORGANIZATION_URL:-<unset>}"
  echo "  ADO_PAT=${ADO_PAT:+<set>}${ADO_PAT:-<unset>}"
else
  echo "ADO MCP credentials present (org=$ADO_ORG)"
fi

# Execute the main command
exec "$@"
