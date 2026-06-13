# syntax=docker/dockerfile:1.7

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM node:20-bookworm-slim AS backend-build
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/package*.json ./
RUN npm ci --omit=dev

FROM node:20-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 quantnik

WORKDIR /app/backend
COPY --from=backend-build  /app/backend/node_modules ./node_modules
COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

# User-level Claude config (skills, plugins, settings) snapshotted from the
# build host via scripts/snapshot-claude-user.sh. Required so the deployed
# Agent SDK sees the same user skills/plugins as the local environment.
# create directory first
RUN mkdir -p /home/quantnik/.claude && chown -R quantnik:quantnik /home/quantnik

# copy only if exists (handled via wildcard trick)
COPY --chown=quantnik:quantnik .claude-user* /home/quantnik/.claude/

RUN mkdir -p /app/backend/data && chown -R quantnik:quantnik /app /home/quantnik

ENV NODE_ENV=production \
    PORT=6060 \
    HOME=/home/quantnik
EXPOSE 6060
USER quantnik

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "src/index.js"]
