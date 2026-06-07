#!/bin/bash
# =============================================================================
# Wega Test Orchestrator - Deployment Script
# =============================================================================
# Usage:
#   ./deploy.sh                     # Deploy without profile (service name: wega-test-orchestrator)
#   ./deploy.sh --profile dev       # Deploy with dev profile (service name: dev-wega-test-orchestrator)
#   ./deploy.sh --profile qa        # Deploy with qa profile
#   ./deploy.sh --profile stage     # Deploy with stage profile
#   ./deploy.sh --profile prod      # Deploy with prod profile
# =============================================================================

set -e

SERVICE_BASE_NAME="wega-test-orchestrator"
PROFILE=""
REGION="us-central1"
PROJECT=""
DRY_RUN=false

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
    echo "Wega Test Orchestrator - Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --profile, -p <profile>   Environment profile (dev, qa, stage, prod)"
    echo "  --region, -r <region>     GCP region (default: us-central1)"
    echo "  --project, -j <project>   GCP project ID"
    echo "  --dry-run                 Show commands without executing"
    echo "  --help, -h                Show this help message"
    echo ""
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --profile|-p) PROFILE="$2"; shift 2 ;;
        --region|-r) REGION="$2"; shift 2 ;;
        --project|-j) PROJECT="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --help|-h) show_help; exit 0 ;;
        *) log_error "Unknown option: $1"; show_help; exit 1 ;;
    esac
done

if [[ -n "$PROFILE" ]]; then
    case $PROFILE in
        dev|qa|stage|prod) log_info "Using profile: $PROFILE" ;;
        *) log_error "Invalid profile: $PROFILE"; exit 1 ;;
    esac
fi

if [[ -n "$PROFILE" ]]; then
    SERVICE_NAME="${PROFILE}-${SERVICE_BASE_NAME}"
else
    SERVICE_NAME="${SERVICE_BASE_NAME}"
fi

if [[ -z "$PROJECT" ]]; then
    PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [[ -z "$PROJECT" ]]; then
        log_error "No GCP project specified"; exit 1
    fi
fi

PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')

if [[ -n "$PROFILE" ]]; then
    ENV_FILE=".env.${PROFILE}"
    if [[ ! -f "$ENV_FILE" ]]; then
        log_warning "Profile-specific env file not found: $ENV_FILE, using .env"
        ENV_FILE=".env"
    fi
else
    ENV_FILE=".env"
fi

echo ""
echo "=========================================="
echo "  Deployment Configuration"
echo "=========================================="
echo "  Service Name:    $SERVICE_NAME"
echo "  Profile:         ${PROFILE:-'(none)'}"
echo "  Region:          $REGION"
echo "  Project:         $PROJECT"
echo "  Project Number:  $PROJECT_NUMBER"
echo "  Env File:        $ENV_FILE"
echo "=========================================="
echo ""

if [[ "$DRY_RUN" == true ]]; then
    log_warning "DRY RUN MODE - Commands will not be executed"
fi

BUILD_CMD="gcloud builds submit --tag gcr.io/${PROJECT}/${SERVICE_NAME}"

DEPLOY_CMD="gcloud run deploy ${SERVICE_NAME} \
    --image gcr.io/${PROJECT}/${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 600 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars APP_PROFILE=${PROFILE:-''} \
    --set-env-vars APP_ENV=${PROFILE:-development} \
    --set-env-vars GCP_PROJECT_NUMBER=${PROJECT_NUMBER} \
    --set-env-vars GCP_REGION=${REGION}"

echo "Step 1: Building container image..."
log_info "Command: $BUILD_CMD"
if [[ "$DRY_RUN" == false ]]; then
    eval $BUILD_CMD
    log_success "Container image built successfully"
fi

echo ""
echo "Step 2: Deploying to Cloud Run..."
log_info "Command: $DEPLOY_CMD"
if [[ "$DRY_RUN" == false ]]; then
    eval $DEPLOY_CMD
    log_success "Deployment completed successfully!"
    
    SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
    echo ""
    echo "=========================================="
    echo "  Deployment Complete!"
    echo "=========================================="
    echo "  Service URL: $SERVICE_URL"
    echo "  Health Check: ${SERVICE_URL}/health"
    echo "  API Docs: ${SERVICE_URL}/docs"
    echo "=========================================="
fi

log_success "Done!"
