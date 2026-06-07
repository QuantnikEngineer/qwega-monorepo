#!/bin/bash
# =============================================================================
# WEGA Frontend - Deployment Script
# =============================================================================
# Usage:
#   ./deploy.sh                     # Deploy without profile
#   ./deploy.sh --profile dev       # Deploy with dev profile (dev-wega-sdlc)
#   ./deploy.sh --profile prod      # Deploy with prod profile
#   ./deploy.sh --dry-run -p dev    # Preview commands without executing
#
# Prerequisites:
#   - gcloud CLI authenticated & project set
#   - API Gateway already deployed (GATEWAY_UPSTREAM must resolve)
#
# Deployment order: auth-service → api-gateway → frontend
# =============================================================================

set -euo pipefail

SERVICE_BASE_NAME="wega-sdlc"
PROFILE=""
REGION="us-central1"
PROJECT=""
DRY_RUN=false
USE_SECRETS=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_help() {
    echo "WEGA Frontend - Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --profile, -p <profile>   Environment profile (dev, qa, stage, prod)"
    echo "  --region, -r <region>     GCP region (default: us-central1)"
    echo "  --project, -j <project>   GCP project ID"
    echo "  --use-secrets             Use GCP Secret Manager for Atlassian credentials"
    echo "  --dry-run                 Show commands without executing"
    echo "  --help, -h                Show this help message"
    echo ""
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --profile|-p) PROFILE="$2"; shift 2 ;;
        --region|-r) REGION="$2"; shift 2 ;;
        --project|-j) PROJECT="$2"; shift 2 ;;
        --use-secrets) USE_SECRETS=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) show_help; exit 0 ;;
        *) log_error "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

# --- Validate profile ---
if [[ -n "$PROFILE" ]]; then
    case $PROFILE in
        dev|qa|stage|prod) log_info "Using profile: $PROFILE" ;;
        *) log_error "Invalid profile: $PROFILE (must be dev, qa, stage, or prod)"; exit 1 ;;
    esac
fi

# --- Compute service name ---
if [[ -n "$PROFILE" ]]; then
    SERVICE_NAME="${PROFILE}-${SERVICE_BASE_NAME}"
else
    SERVICE_NAME="${SERVICE_BASE_NAME}"
fi

# --- Resolve GCP project ---
if [[ -z "$PROJECT" ]]; then
    PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [[ -z "$PROJECT" ]]; then
        log_error "No GCP project specified. Use --project or set via gcloud config."; exit 1
    fi
fi

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')

# --- Compute gateway URL ---
PROFILE_PREFIX=""
if [[ -n "$PROFILE" ]]; then
    PROFILE_PREFIX="${PROFILE}-"
fi

GATEWAY_SERVICE_NAME="${PROFILE_PREFIX}wega-api-gateway"
GATEWAY_UPSTREAM="https://${GATEWAY_SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"

# --- Display configuration ---
echo ""
echo "=========================================="
echo "  WEGA Frontend — Deployment"
echo "=========================================="
echo "  Service Name:      $SERVICE_NAME"
echo "  Profile:           ${PROFILE:-'(none)'}"
echo "  Region:            $REGION"
echo "  Project:           $PROJECT"
echo "  Project Number:    $PROJECT_NUMBER"
echo "  Gateway Upstream:  $GATEWAY_UPSTREAM"
echo "  Use Secrets:       $USE_SECRETS"
echo "=========================================="
echo ""

if [[ "$DRY_RUN" == true ]]; then
    log_warning "DRY RUN MODE — commands will not be executed"
fi

# --- Step 1: Build container image ---
BUILD_CMD="gcloud builds submit --tag gcr.io/${PROJECT}/${SERVICE_NAME}"

echo "Step 1: Building container image..."
log_info "Command: $BUILD_CMD"
if [[ "$DRY_RUN" == false ]]; then
    eval "$BUILD_CMD"
    log_success "Container image built successfully"
fi

# --- Step 2: Deploy to Cloud Run ---
# Frontend is public (--allow-unauthenticated) — it serves the SPA.
# nginx.conf.template uses envsubst at container startup to inject:
#   GATEWAY_UPSTREAM  — API gateway URL for /api, /auth, /jira, /confluence proxies
#
# Atlassian credentials are NO LONGER needed here — the gateway resolves
# project-scoped credentials from auth-service at proxy time.
#
# VITE_* variables are baked at Docker build time (npm run build), not at deploy time.
# To change VITE_* values, rebuild the image.

DEPLOY_CMD="gcloud run deploy ${SERVICE_NAME} \
    --image gcr.io/${PROJECT}/${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --ingress all \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 5 \
    --set-env-vars GATEWAY_UPSTREAM=${GATEWAY_UPSTREAM}"

echo ""
echo "Step 2: Deploying to Cloud Run..."
log_info "Command: $DEPLOY_CMD"
if [[ "$DRY_RUN" == false ]]; then
    eval "$DEPLOY_CMD"
    log_success "Deployment completed successfully!"

    SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format 'value(status.url)')
    echo ""
    echo "=========================================="
    echo "  Deployment Complete!"
    echo "=========================================="
    echo "  Service URL:  $SERVICE_URL"
    echo "  Health Check: ${SERVICE_URL}/health"
    echo "=========================================="
fi

echo ""
log_success "Done!"
