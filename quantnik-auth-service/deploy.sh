#!/bin/bash
# =============================================================================
# QUANTNIK Auth Service - Deployment Script
# =============================================================================
# Usage:
#   ./deploy.sh                     # Deploy without profile
#   ./deploy.sh --profile dev       # Deploy with dev profile (dev-quantnik-auth-service)
#   ./deploy.sh --profile prod      # Deploy with prod profile
#   ./deploy.sh --dry-run -p dev    # Preview commands without executing
#
# Prerequisites:
#   - gcloud CLI authenticated & project set
#   - Docker image builds successfully
#   - Database (PostgreSQL) accessible from Cloud Run
#   - JWT keys stored in GCP Secret Manager (for --use-secrets mode)
# =============================================================================

set -euo pipefail

SERVICE_BASE_NAME="quantnik-auth-service"
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
    echo "QUANTNIK Auth Service - Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --profile, -p <profile>   Environment profile (dev, qa, stage, prod)"
    echo "  --region, -r <region>     GCP region (default: us-central1)"
    echo "  --project, -j <project>   GCP project ID"
    echo "  --use-secrets             Use GCP Secret Manager for sensitive values"
    echo "  --dry-run                 Show commands without executing"
    echo "  --help, -h                Show this help message"
    echo ""
    echo "Deployment order: auth-service → api-gateway → frontend"
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

# --- Compute dependent service URLs ---
PROFILE_PREFIX=""
if [[ -n "$PROFILE" ]]; then
    PROFILE_PREFIX="${PROFILE}-"
fi

FRONTEND_SERVICE_NAME="${PROFILE_PREFIX}quantnik-frontend"
GATEWAY_SERVICE_NAME="${PROFILE_PREFIX}quantnik-api-gateway"

FRONTEND_URL="https://${FRONTEND_SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"

# --- Profile-specific configuration ---
if [[ "$PROFILE" == "prod" || "$PROFILE" == "stage" ]]; then
    COOKIE_SECURE="true"
    CORS_ORIGINS="${FRONTEND_URL}"
    APP_ENV="production"
    LOG_LEVEL="INFO"
    DEBUG="false"
else
    COOKIE_SECURE="false"
    CORS_ORIGINS="*"
    APP_ENV="${PROFILE:-development}"
    LOG_LEVEL="DEBUG"
    DEBUG="true"
fi

# --- Display configuration ---
echo ""
echo "=========================================="
echo "  QUANTNIK Auth Service — Deployment"
echo "=========================================="
echo "  Service Name:    $SERVICE_NAME"
echo "  Profile:         ${PROFILE:-'(none)'}"
echo "  Region:          $REGION"
echo "  Project:         $PROJECT"
echo "  Project Number:  $PROJECT_NUMBER"
echo "  Frontend URL:    $FRONTEND_URL"
echo "  Cookie Secure:   $COOKIE_SECURE"
echo "  CORS Origins:    $CORS_ORIGINS"
echo "  Use Secrets:     $USE_SECRETS"
echo "  Reg. Project:    ${REGISTRATION_DEFAULT_PROJECT_SLUG:-quantnik-sdlc-dev}"
echo "  Reg. Role:       ${REGISTRATION_DEFAULT_ROLE:-po_sm_ba}"
echo "=========================================="
echo ""

if [[ "$DRY_RUN" == true ]]; then
    log_warning "DRY RUN MODE — commands will not be executed"
fi

# --- Step 1: Build container image ---
BUILD_CMD="gcloud builds submit --tag gcr.io/${PROJECT}/${SERVICE_NAME} --gcs-log-dir=gs://${PROJECT}_cloudbuild/logs"

echo "Step 1: Building container image..."
log_info "Command: $BUILD_CMD"
if [[ "$DRY_RUN" == false ]]; then
    eval "$BUILD_CMD"
    log_success "Container image built successfully"
fi

# --- Step 2: Run database migrations via Cloud Run Job ---
# Migrations run as a separate job BEFORE the service deploys.
# This ensures: (a) migration failure aborts deploy (old app stays running),
# (b) no startup latency from migrations, (c) no multi-instance race condition.
JOB_NAME="${SERVICE_NAME}-migrate"
IMAGE="gcr.io/${PROJECT}/${SERVICE_NAME}"

# Resolve image digest so job and service use identical image
if [[ "$DRY_RUN" == false ]]; then
    IMAGE_DIGEST=$(gcloud container images describe "${IMAGE}:latest" --format='value(image_summary.fully_qualified_digest)' 2>/dev/null || echo "")
    if [[ -n "$IMAGE_DIGEST" ]]; then
        IMAGE="$IMAGE_DIGEST"
        log_info "Using image digest: $IMAGE"
    else
        log_warning "Could not resolve image digest — using tag :latest"
        IMAGE="${IMAGE}:latest"
    fi
else
    IMAGE="${IMAGE}:latest"
fi

# Build job env vars (migration only needs DATABASE_URL + QUANTNIK_SECRET_KEY)
JOB_ENV="--set-env-vars APP_ENV=${APP_ENV}"

if [[ "$USE_SECRETS" == true ]]; then
    JOB_SECRET_ARGS="--set-secrets DATABASE_URL=${PROFILE_PREFIX}quantnik-auth-database-url:latest"
    JOB_DB_ARGS=""
else
    JOB_SECRET_ARGS=""
    JOB_DB_ARGS="--set-env-vars DATABASE_URL=${DATABASE_URL}"
fi

if [[ -n "${QUANTNIK_SECRET_KEY:-}" && "$USE_SECRETS" == false ]]; then
    JOB_ENV="${JOB_ENV} --set-env-vars QUANTNIK_SECRET_KEY=${QUANTNIK_SECRET_KEY}"
fi

echo ""
echo "Step 2: Running database migrations (Cloud Run Job)..."

# Create or update the migration job
JOB_COMMON_ARGS="--image ${IMAGE} \
    --region ${REGION} \
    --command python \
    --args=-m,alembic,upgrade,head \
    --task-timeout 300 \
    --max-retries 0 \
    --memory 512Mi \
    ${JOB_ENV} ${JOB_DB_ARGS} ${JOB_SECRET_ARGS}"

if [[ "$DRY_RUN" == false ]]; then
    if gcloud run jobs describe "${JOB_NAME}" --region "${REGION}" &>/dev/null; then
        log_info "Updating existing migration job: ${JOB_NAME}"
        eval "gcloud run jobs update ${JOB_NAME} ${JOB_COMMON_ARGS}"
    else
        log_info "Creating migration job: ${JOB_NAME}"
        eval "gcloud run jobs create ${JOB_NAME} ${JOB_COMMON_ARGS}"
    fi
    log_success "Migration job configured"

    # Execute and wait for completion
    log_info "Executing migration job..."
    if gcloud run jobs execute "${JOB_NAME}" --region "${REGION}" --wait; then
        log_success "Database migrations completed successfully"
    else
        log_error "Migration job FAILED — aborting deployment (previous service revision stays active)"
        log_error "Inspect logs: gcloud run jobs executions list --job ${JOB_NAME} --region ${REGION}"
        log_error "View details: gcloud logging read 'resource.type=\"cloud_run_job\" resource.labels.job_name=\"${JOB_NAME}\"' --limit 50"
        exit 1
    fi
else
    log_warning "[DRY RUN] Would create/update and execute job: ${JOB_NAME}"
    log_info "  Image:   ${IMAGE}"
    log_info "  Command: python -m alembic upgrade head"
    log_info "  Timeout: 300s, Retries: 0, Memory: 512Mi"
fi

# --- Step 3: Deploy to Cloud Run ---
# Auth service is kept public (--allow-unauthenticated) because the API gateway
# calls it via plain HTTP (JWKS fetch, login/refresh proxy, internal settings API).
# The gateway does NOT currently attach Cloud Run identity tokens, so making this
# service private would break gateway→auth communication.
# Internal routes are protected by INTERNAL_API_KEY header validation.
#
# Concurrency is set conservatively (10) because Argon2 password hashing is
# CPU-bound (64MB memory per hash with OWASP 2025 params). Most requests are
# lightweight (token validation, user CRUD), but login/register endpoints are heavy.

DEPLOY_CMD="gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --ingress all \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --concurrency 10 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars APP_ENV=${APP_ENV} \
    --set-env-vars DEBUG=${DEBUG} \
    --set-env-vars LOG_LEVEL=${LOG_LEVEL} \
    --set-env-vars JWT_ISSUER=quantnik-auth \
    --set-env-vars JWT_AUDIENCE=quantnik-api \
    --set-env-vars JWT_ACCESS_TOKEN_EXPIRE_MINUTES=${JWT_ACCESS_TOKEN_EXPIRE_MINUTES:-60} \
    --set-env-vars JWT_REFRESH_TOKEN_EXPIRE_DAYS=${JWT_REFRESH_TOKEN_EXPIRE_DAYS:-30} \
    --set-env-vars COOKIE_SECURE=${COOKIE_SECURE} \
    --set-env-vars COOKIE_SAMESITE=${COOKIE_SAMESITE:-lax} \
    --set-env-vars COOKIE_PATH=/auth \
    --set-env-vars CORS_ORIGINS=${CORS_ORIGINS} \
    --set-env-vars FRONTEND_URL=${FRONTEND_URL} \
    --set-env-vars GCP_PROJECT_NUMBER=${PROJECT_NUMBER} \
    --set-env-vars GCP_REGION=${REGION} \
    --set-env-vars GCP_PROFILE_PREFIX=${PROFILE_PREFIX} \
    --set-env-vars LOCKOUT_THRESHOLD=${LOCKOUT_THRESHOLD:-15} \
    --set-env-vars LOCKOUT_WINDOW_MINUTES=${LOCKOUT_WINDOW_MINUTES:-5} \
    --set-env-vars LOCKOUT_BACKOFF_BASE_SECONDS=${LOCKOUT_BACKOFF_BASE_SECONDS:-1} \
    --set-env-vars LOCKOUT_BACKOFF_MAX_SECONDS=${LOCKOUT_BACKOFF_MAX_SECONDS:-10} \
    --set-env-vars REGISTRATION_RATE_LIMIT_MAX=${REGISTRATION_RATE_LIMIT_MAX:-30} \
    --set-env-vars REGISTRATION_RATE_LIMIT_WINDOW=${REGISTRATION_RATE_LIMIT_WINDOW:-3600} \
    --set-env-vars SKIP_MIGRATIONS=true \
    --set-env-vars REGISTRATION_DEFAULT_PROJECT_SLUG=${REGISTRATION_DEFAULT_PROJECT_SLUG:-quantnik-sdlc-dev} \
    --set-env-vars REGISTRATION_DEFAULT_ROLE=${REGISTRATION_DEFAULT_ROLE:-po_sm_ba}"

# --- Secrets handling ---
if [[ "$USE_SECRETS" == true ]]; then
    log_info "Using GCP Secret Manager for sensitive values"
    # Volume mount for JWT key files (Secret Manager → file path)
    # Env var injection for connection string and API key
    DEPLOY_CMD="${DEPLOY_CMD} \
    --update-secrets=/app/keys/private.pem=${PROFILE_PREFIX}quantnik-auth-jwt-private-key:latest \
    --update-secrets=/app/keys/public.pem=${PROFILE_PREFIX}quantnik-auth-jwt-public-key:latest \
    --update-secrets=DATABASE_URL=${PROFILE_PREFIX}quantnik-auth-database-url:latest \
    --update-secrets=INTERNAL_API_KEY=${PROFILE_PREFIX}quantnik-internal-api-key:latest \
    --set-env-vars JWT_PRIVATE_KEY_PATH=/app/keys/private.pem \
    --set-env-vars JWT_PUBLIC_KEY_PATH=/app/keys/public.pem"
else
    # --- Read DATABASE_URL from .env or environment ---
    # The auth-service uses PostgreSQL on AWS RDS (not SQLite).
    # In non-secret mode, the DATABASE_URL must be supplied via:
    #   1. DATABASE_URL environment variable (export before running), OR
    #   2. .env file in the repo root (gitignored, never committed)
    if [[ -z "${DATABASE_URL:-}" ]]; then
        # Try reading from .env file
        if [[ -f .env ]]; then
            DATABASE_URL=$(grep -E '^DATABASE_URL=' .env | head -1 | cut -d'=' -f2-)
        fi
    fi
    if [[ -z "${DATABASE_URL:-}" ]]; then
        log_error "DATABASE_URL not set. Export it or add to .env file."
        log_error "Expected: postgresql+asyncpg://user:pass@host:5432/quantnik_auth"
        exit 1
    fi
    log_info "DATABASE_URL sourced (driver: $(echo "$DATABASE_URL" | cut -d: -f1-2))"

    # --- Read QUANTNIK_SECRET_KEY (Fernet key for project secret encryption) ---
    if [[ -z "${QUANTNIK_SECRET_KEY:-}" ]]; then
        if [[ -f .env ]]; then
            QUANTNIK_SECRET_KEY=$(grep -E '^QUANTNIK_SECRET_KEY=' .env | head -1 | cut -d'=' -f2-)
        fi
    fi

    log_warning "Sensitive values passed as plain env vars (no Secret Manager)."
    log_warning "For production, use --use-secrets with GCP Secret Manager."
    DEPLOY_CMD="${DEPLOY_CMD} \
    --set-env-vars DATABASE_URL=${DATABASE_URL} \
    --set-env-vars JWT_PRIVATE_KEY_PATH=keys/private.pem \
    --set-env-vars JWT_PUBLIC_KEY_PATH=keys/public.pem \
    --set-env-vars INTERNAL_API_KEY=quantnik-internal-dev-key"

    if [[ -n "${QUANTNIK_SECRET_KEY:-}" ]]; then
        DEPLOY_CMD="${DEPLOY_CMD} \
    --set-env-vars QUANTNIK_SECRET_KEY=${QUANTNIK_SECRET_KEY}"
        log_info "QUANTNIK_SECRET_KEY sourced from .env"
    else
        log_warning "QUANTNIK_SECRET_KEY not set — project secret encryption will use ephemeral key"
    fi
fi

echo ""
echo "Step 3: Deploying to Cloud Run..."
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
    echo "  API Docs:     ${SERVICE_URL}/docs"
    echo "=========================================="
fi

# --- Post-deploy: Bootstrap (first deployment only) ---
echo ""
log_info "Post-deploy steps (first deployment only — run manually):"
echo ""
echo "  Bootstrap superadmin:"
echo "     gcloud run jobs create ${SERVICE_NAME}-bootstrap \\"
echo "       --image ${IMAGE} \\"
echo "       --region ${REGION} \\"
echo "       --set-env-vars DATABASE_URL=<your-db-url> \\"
echo "       --command python --args=scripts/create_superadmin.py"
echo "     gcloud run jobs execute ${SERVICE_NAME}-bootstrap --region ${REGION} --wait"
echo ""
echo "  Or run locally:"
echo "     python scripts/create_superadmin.py"
echo ""

# --- Post-deploy: IAM binding for gateway ---
log_info "IAM binding (if restricting auth-service access in future):"
echo "  gcloud run services add-iam-policy-binding ${SERVICE_NAME} \\"
echo "    --region ${REGION} --project ${PROJECT} \\"
echo "    --member serviceAccount:${GATEWAY_SERVICE_NAME}@${PROJECT}.iam.gserviceaccount.com \\"
echo "    --role roles/run.invoker"

echo ""
log_success "Done!"
