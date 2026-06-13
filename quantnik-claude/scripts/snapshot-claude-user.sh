#!/usr/bin/env bash
# Snapshot the build host's ~/.claude/ user-level config into the repo so the
# Docker build can COPY it into the container. Run this immediately before
# `docker build` whenever you change skills, install plugins, or want to
# refresh MCP auth state.
#
# Outputs to: <repo-root>/.claude-user/  (gitignored)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${HOME}/.claude"
DEST="${REPO_ROOT}/.claude-user"

if [[ ! -d "${SRC}" ]]; then
  echo "ERROR: ${SRC} does not exist — is the claude CLI installed?" >&2
  exit 1
fi

rm -rf "${DEST}"
mkdir -p "${DEST}"

# Skills — user-level skill definitions
if [[ -d "${SRC}/skills" ]]; then
  cp -R "${SRC}/skills" "${DEST}/"
  echo "snapshot: skills/  ($(ls "${DEST}/skills" | wc -l | tr -d ' ') skills)"
fi

# Plugins — installed plugins + marketplace registry
if [[ -d "${SRC}/plugins" ]]; then
  cp -R "${SRC}/plugins" "${DEST}/"
  echo "snapshot: plugins/"
fi

# Global theme / non-secret settings only
if [[ -f "${SRC}/settings.json" ]]; then
  cp "${SRC}/settings.json" "${DEST}/"
  echo "snapshot: settings.json"
fi

# MCP auth cache — helps the SDK skip re-auth flows on first boot
if [[ -f "${SRC}/mcp-needs-auth-cache.json" ]]; then
  cp "${SRC}/mcp-needs-auth-cache.json" "${DEST}/"
  echo "snapshot: mcp-needs-auth-cache.json"
fi

# Explicitly DO NOT copy:
#  - .credentials.json (replaced by CLAUDE_CODE_OAUTH_TOKEN env var)
#  - settings.local.json (host-specific permission grants)
#  - history.jsonl, sessions/, projects/, cache/, telemetry/ (large + personal)

echo "done → ${DEST}"
