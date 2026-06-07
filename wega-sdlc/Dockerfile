# Build stage
ARG BASE_REGISTRY=docker.io
FROM ${BASE_REGISTRY}/node:20-slim AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --legacy-peer-deps

# Copy source code
COPY . .

# Set environment variables for build
ENV NODE_ENV=production

# VITE_* vars are embedded in the JS bundle at build time.
# Override at Docker build: docker build --build-arg VITE_AUTH_ENABLED=false ...
ARG VITE_AUTH_ENABLED=true
ENV VITE_AUTH_ENABLED=$VITE_AUTH_ENABLED
ARG VITE_CODE_ASSISTANT_URL=https://dev-wega-code-assistant-agent-204952354085.us-central1.run.app
ENV VITE_CODE_ASSISTANT_URL=$VITE_CODE_ASSISTANT_URL
# VITE_GATEWAY_URL intentionally left empty — production uses relative URLs
# (nginx proxies /api, /auth, /jira, /confluence to GATEWAY_UPSTREAM at runtime)

RUN npm run build && \
    echo "Build completed. Checking build folder..." && \
    ls -la && \
    if [ -d "build" ]; then echo "build folder exists"; ls -la build; else echo "ERROR: build folder not found"; exit 1; fi

# Production stage
FROM ${BASE_REGISTRY}/nginx:stable-alpine

# Copy built assets from builder (using 'build' folder as per vite.config.ts)
COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx config TEMPLATE (credentials injected at runtime via envsubst)
COPY nginx.conf.template /etc/nginx/conf.d/default.conf.template

# Copy entrypoint script (auto-computes GATEWAY_UPSTREAM from K_SERVICE)
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
