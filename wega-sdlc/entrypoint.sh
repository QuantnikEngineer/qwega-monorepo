#!/bin/sh
set -e

# ── Auto-compute GATEWAY_UPSTREAM from Cloud Run metadata ──
# Cloud Run injects K_SERVICE (e.g. "dev-wega-sdlc").
# Extract the env prefix (dev/qa/stage) and build the gateway URL.
# This eliminates the need to set GATEWAY_UPSTREAM manually per environment.

if [ -z "$GATEWAY_UPSTREAM" ]; then
    # K_SERVICE is set by Cloud Run (e.g. "dev-wega-sdlc", "qa-wega-sdlc")
    if [ -n "$K_SERVICE" ]; then
        ENV_PREFIX=$(echo "$K_SERVICE" | cut -d'-' -f1)
        PROJECT_NUMBER="${GCP_PROJECT_NUMBER:-204952354085}"
        REGION="${GCP_REGION:-us-central1}"
        GATEWAY_UPSTREAM="https://${ENV_PREFIX}-wega-api-gateway-${PROJECT_NUMBER}.${REGION}.run.app"
        echo "[entrypoint] Auto-computed GATEWAY_UPSTREAM from K_SERVICE=$K_SERVICE"
    else
        # Local dev fallback
        GATEWAY_UPSTREAM="${GATEWAY_UPSTREAM:-http://host.docker.internal:8080}"
        echo "[entrypoint] Using local dev fallback for GATEWAY_UPSTREAM"
    fi
    export GATEWAY_UPSTREAM
fi

echo "[entrypoint] GATEWAY_UPSTREAM=$GATEWAY_UPSTREAM"

# Inject into nginx config and start
envsubst '${GATEWAY_UPSTREAM}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'
