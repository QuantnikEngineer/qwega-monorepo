#!/bin/bash
# =============================================================================
# WEGA API Gateway - Deployment Script
# =============================================================================

set -e

SERVICE_BASE_NAME="wega-api-gateway"
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
    echo "WEGA API Gateway - Deployment Script"
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
PROFILE_PREFIX=""
if [[ -n "$PROFILE" ]]; then
    PROFILE_PREFIX="${PROFILE}-"
fi

AUTH_SERVICE_NAME="${PROFILE_PREFIX}wega-auth-service"
ORCHESTRATOR_SERVICE_NAME="${PROFILE_PREFIX}wega-sdlc-orchestrator"
PLANNING_SERVICE_NAME="${PROFILE_PREFIX}wega-planning-orchestrator"
TESTCASE_SERVICE_NAME="${PROFILE_PREFIX}wega-userstory-to-testcases-agent"
RAG_SERVICE_NAME="${PROFILE_PREFIX}wega-rag"

AUTH_SERVICE_URL="https://${AUTH_SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"
ORCHESTRATOR_URL="https://${ORCHESTRATOR_SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"
PLANNING_ORCHESTRATOR_URL="https://${PLANNING_SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"
TESTCASE_AGENT_URL="https://${TESTCASE_SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"
RAG_SERVICE_URL="https://${RAG_SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"

echo ""
echo "=========================================="
echo "  Deployment Configuration"
echo "=========================================="
echo "  Service Name:         $SERVICE_NAME"
echo "  Profile:              ${PROFILE:-'(none)'}"
echo "  Region:               $REGION"
echo "  Project:              $PROJECT"
echo "  Project Number:       $PROJECT_NUMBER"
echo "  Auth Service URL:     $AUTH_SERVICE_URL"
echo "  Orchestrator URL:     $ORCHESTRATOR_URL"
echo "  Planning URL:         $PLANNING_ORCHESTRATOR_URL"
echo "  TestCase Agent URL:   $TESTCASE_AGENT_URL"
echo "  RAG Service URL:      $RAG_SERVICE_URL"
echo "=========================================="
echo ""

if [[ "$DRY_RUN" == true ]]; then
    log_warning "DRY RUN MODE - Commands will not be executed"
fi

BUILD_CMD="gcloud builds submit --tag gcr.io/${PROJECT}/${SERVICE_NAME} --gcs-log-dir=gs://${PROJECT}_cloudbuild/logs"

DEPLOY_CMD="gcloud run deploy ${SERVICE_NAME} \
    --image gcr.io/${PROJECT}/${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --ingress all \
    --memory 1Gi \
    --cpu 1 \
    --timeout 900 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars APP_ENV=${PROFILE:-development} \
    --set-env-vars GCP_PROJECT_NUMBER=${PROJECT_NUMBER} \
    --set-env-vars GCP_REGION=${REGION} \
    --set-env-vars GCP_PROFILE_PREFIX=${PROFILE_PREFIX} \
    --set-env-vars AUTH_SERVICE_URL=${AUTH_SERVICE_URL} \
    --set-env-vars ORCHESTRATOR_URL=${ORCHESTRATOR_URL} \
    --set-env-vars PLANNING_ORCHESTRATOR_URL=${PLANNING_ORCHESTRATOR_URL} \
    --set-env-vars TESTCASE_AGENT_URL=${TESTCASE_AGENT_URL} \
    --set-env-vars TESTCASE_POLL_URL=${TESTCASE_AGENT_URL} \
    --set-env-vars RAG_SERVICE_URL=${RAG_SERVICE_URL} \
    --set-env-vars CORS_ORIGINS=* \
    --set-env-vars INTERNAL_API_KEY=wega-internal-dev-key \
    --set-env-vars JWT_ISSUER=wega-auth \
    --set-env-vars JWT_AUDIENCE=wega-api \
    --set-env-vars LOGIN_RATE_LIMIT_MAX=${LOGIN_RATE_LIMIT_MAX:-15} \
    --set-env-vars LOGIN_RATE_LIMIT_WINDOW=${LOGIN_RATE_LIMIT_WINDOW:-60}"

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
    echo "=========================================="
fi

log_info "Post-deploy IAM (required for private downstream services):"
echo "  gcloud run services add-iam-policy-binding ${ORCHESTRATOR_SERVICE_NAME} \\"
echo "    --region ${REGION} --project ${PROJECT} \\"
echo "    --member serviceAccount:${SERVICE_NAME}@${PROJECT}.iam.gserviceaccount.com \\"
echo "    --role roles/run.invoker"
echo "  gcloud run services add-iam-policy-binding ${PLANNING_SERVICE_NAME} \\"
echo "    --region ${REGION} --project ${PROJECT} \\"
echo "    --member serviceAccount:${SERVICE_NAME}@${PROJECT}.iam.gserviceaccount.com \\"
echo "    --role roles/run.invoker"

log_success "Done!"
