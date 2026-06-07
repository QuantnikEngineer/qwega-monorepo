# syntax=docker/dockerfile:1

# ============================================================================
# WEGA CI/CD Agent - Production Dockerfiles
# ============================================================================
# Multi-stage build for optimized image size and security
# Includes: Python 3.12, Jinja2 templates, LLM integration
# ============================================================================

FROM python:3.12-slim AS base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ============================================================================
# Build Stage - Install dependencies
# ============================================================================
FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment for clean dependency isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ============================================================================
# Production Stage - Final image
# ============================================================================
FROM base AS production

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# SECURITY: Create non-root user for running the application
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appgroup . .

# SECURITY: Switch to non-root user
USER appuser

# Environment configuration
ENV PORT=8092 \
    HOST=0.0.0.0 \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    DEFAULT_RENDER_MODE=hybrid

# Expose service port
EXPOSE 8092

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the application
CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT}"]
