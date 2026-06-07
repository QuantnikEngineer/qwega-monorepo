#!/bin/bash
# =============================================================================
# Wega Common Integration Service - Deployment Script
# =============================================================================
# Usage:
#   ./deploy.sh                     # Deploy without profile (service name: wega-common-integration-service)
#   ./deploy.sh --profile dev       # Deploy with dev profile (service name: dev-wega-common-integration-service)
#   ./deploy.sh --profile qa        # Deploy with qa profile
#   ./deploy.sh --profile stage     # Deploy with stage profile
#   ./deploy.sh --profile prod      # Deploy with prod profile
#
# Options:
#   --profile, -p    Environment profile (dev, qa, stage, prod)
#   --region, -r     GCP region (default: us-central1)
#   --project, -j    GCP project ID (uses gcloud config if not specified)
#   --dry-run        Show commands without executing
#   --help, -h       Show this help message
# =============================================================================

set -e

# Default values
SERVICE_BASE_NAME="wega-common-integration-service"
PROFILE=""
REGION="us-central1"
PROJECT=""
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    echo "Wega Common Integration Service - Deployment Script"
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
    echo "Examples:"
    echo "  ./deploy.sh                          # Deploy as wega-common-integration-service"
    echo "  ./deploy.sh --profile dev            # Deploy as dev-wega-common-integration-service"
    echo "  ./deploy.sh -p qa -r us-east1        # Deploy as qa-wega-common-integration-service in us-east1"
    echo "  ./deploy.sh --profile stage --dry-run  # Show deployment commands without executing"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile|-p)
            PROFILE="$2"
            shift 2
            ;;
        --region|-r)
            REGION="$2"
            shift 2
            ;;
        --project|-j)
            PROJECT="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate profile if provided
if [[ -n "$PROFILE" ]]; then
    case $PROFILE in
        dev|qa|stage|prod)
            log_info "Using profile: $PROFILE"
            ;;
        *)
            log_error "Invalid profile: $PROFILE. Valid profiles are: dev, qa, stage, prod"
            exit 1
            ;;
    esac
fi

# Construct service name
if [[ -n "$PROFILE" ]]; then
    SERVICE_NAME="${PROFILE}-${SERVICE_BASE_NAME}"
else
    SERVICE_NAME="${SERVICE_BASE_NAME}"
fi

# Get project ID if not specified
if [[ -z "$PROJECT" ]]; then
    PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [[ -z "$PROJECT" ]]; then
        log_error "No GCP project specified and none found in gcloud config"
        log_error "Use --project <project-id> or run: gcloud config set project <project-id>"
        exit 1
    fi
fi

# Get project number for dynamic URL construction
PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')

# Determine env file based on profile
if [[ -n "$PROFILE" ]]; then
    ENV_FILE=".env.${PROFILE}"
    if [[ ! -f "$ENV_FILE" ]]; then
        log_warning "Profile-specific env file not found: $ENV_FILE"
        log_warning "Falling back to .env"
        ENV_FILE=".env"
    fi
else
    ENV_FILE=".env"
fi

# Display deployment info
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
    echo ""
fi

# Build command
BUILD_CMD="gcloud builds submit --tag gcr.io/${PROJECT}/${SERVICE_NAME}"

# Deploy command with environment variables from env file
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
echo ""

if [[ "$DRY_RUN" == false ]]; then
    eval $BUILD_CMD
    log_success "Container image built successfully"
else
    log_warning "[DRY RUN] Skipping build"
fi

echo ""
echo "Step 2: Deploying to Cloud Run..."
log_info "Command: $DEPLOY_CMD"
echo ""

if [[ "$DRY_RUN" == false ]]; then
    eval $DEPLOY_CMD
    log_success "Deployment completed successfully!"
    
    # Get service URL
    SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')
    echo ""
    echo "=========================================="
    echo "  Deployment Complete!"
    echo "=========================================="
    echo "  Service URL: $SERVICE_URL"
    echo "  Health Check: ${SERVICE_URL}/health"
    echo "  API Docs: ${SERVICE_URL}/docs"
    echo "=========================================="
else
    log_warning "[DRY RUN] Skipping deployment"
fi

echo ""
log_success "Done!"
