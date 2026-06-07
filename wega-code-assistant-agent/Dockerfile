# ---------------------------------------------------------------------------
# Dockerfile.cloudrun – wega-code-assistant-agent (Cloud Run)
# ---------------------------------------------------------------------------
# Unlike the Wega-Staging frontend (nginx + static files), this is a live
# Node.js server that streams chat responses via the Factory Droid CLI.
# ---------------------------------------------------------------------------

FROM us-central1-docker.pkg.dev/digital-rig-poc/wega-build-baseimages/node:20-slim AS builder

WORKDIR /app

# Install all OS-level dependencies in a single layer (smaller image, faster cold start)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         curl ca-certificates git bash python3 python3-pip gettext-base \
    && rm -rf /var/lib/apt/lists/*

# Install app dependencies first for better layer caching 
COPY package*.json ./
RUN npm ci --omit=dev

# Copy application source
COPY . .

# Install Factory Droid CLI used by server-side chat execution
RUN curl -fsSL https://app.factory.ai/cli | sh \
    && /root/.local/bin/droid --version
ENV PATH="/root/.local/bin:${PATH}"

# Pre-install Azure DevOps MCP server so npx doesn't fetch it on every cold start
RUN npm install -g @azure-devops/mcp \
    && ls -l /usr/local/bin/npx

# Pre-install Atlassian (Jira/Confluence) MCP server.
# Uses sooperset/mcp-atlassian which authenticates with a Jira API token and
# is fully headless — required because the Atlassian remote MCP at
# mcp.atlassian.com requires interactive OAuth which is impossible in Cloud Run.
#
# Notes:
#   - Run pip install as its own step so a failure surfaces clearly in build logs.
#   - `mcp-atlassian --help` is NOT executed at build time: some versions of
#     the package import config at startup and exit non-zero without env vars.
#     The entrypoint validates the binary exists before launching the server.
#   - A symlink at /usr/local/bin/mcp-atlassian guarantees the absolute path
#     used in mcp.json.template stays valid regardless of pip's install dir.
RUN pip3 install --break-system-packages --no-cache-dir mcp-atlassian

# Diagnose where pip actually placed the package and any console scripts.
# This step never fails — it only prints. The next step does the strict check.
RUN echo "=== pip3 show mcp-atlassian ===" \
    && pip3 show -f mcp-atlassian || true \
    && echo "=== files matching mcp* in common bin dirs ===" \
    && ls -la /usr/local/bin/ 2>/dev/null | grep -i mcp || true \
    && ls -la /usr/bin/ 2>/dev/null | grep -i mcp || true \
    && ls -la /root/.local/bin/ 2>/dev/null | grep -i mcp || true \
    && echo "=== full filesystem search ===" \
    && find / -name 'mcp*atlassian*' -o -name 'mcp_atlassian*' 2>/dev/null | head -50 || true \
    && echo "=== python module check ===" \
    && python3 -c "import mcp_atlassian; print('module path:', mcp_atlassian.__file__)" || true \
    && echo "=== end diagnostics ==="

# Resolve the mcp-atlassian launcher and create a stable symlink at
# /usr/local/bin/mcp-atlassian (the path used in mcp.json.template).
# Falls back to invoking the Python module directly if no console script exists.
RUN set -eux; \
    TARGET=/usr/local/bin/mcp-atlassian; \
    MCP_BIN="$(command -v mcp-atlassian || true)"; \
    if [ -z "$MCP_BIN" ]; then \
      MCP_BIN="$(find / -type f \( -name 'mcp-atlassian' -o -name 'mcp_atlassian' \) 2>/dev/null | head -n1)"; \
    fi; \
    if [ -n "$MCP_BIN" ] && [ -x "$MCP_BIN" ]; then \
      if [ "$MCP_BIN" = "$TARGET" ]; then \
        echo "mcp-atlassian already at $TARGET — no symlink needed"; \
      else \
        ln -sf "$MCP_BIN" "$TARGET"; \
      fi; \
    else \
      echo "No console script found — creating wrapper that invokes python -m mcp_atlassian"; \
      python3 -c "import mcp_atlassian"; \
      printf '#!/bin/sh\nexec python3 -m mcp_atlassian "$@"\n' > "$TARGET"; \
      chmod +x "$TARGET"; \
    fi; \
    ls -l "$TARGET"

# Copy MCP config template - env vars are substituted at runtime via entrypoint
COPY mcp.json.template /app/mcp.json.template
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Copy environment config files (non-sensitive settings loaded at runtime based on APP_PROFILE)
COPY .env.dev .env.qa .env.stage /app/

# Ensure default repo discovery has at least one folder under ./repos
RUN mkdir -p /app/repos && ln -sfn /app /app/repos/code-assist

# Production settings – Cloud Run injects PORT at runtime (default 8080)
ENV NODE_ENV=production \
    HOST=0.0.0.0

EXPOSE 8080

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["npm", "run", "serve"]
