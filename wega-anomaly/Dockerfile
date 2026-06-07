# WEGA Anomaly Agent - Production Dockerfile
# This builds a secure, optimized container that protects IP

FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production image
FROM python:3.11-slim

WORKDIR /app

# Create non-root user with explicit UID for security
# Using UID 10001 (non-privileged range) for Kubernetes runAsNonRoot compatibility
ARG APP_UID=10001
ARG APP_GID=10001

RUN groupadd --gid ${APP_GID} agent && \
    useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /bin/bash agent && \
    chown -R ${APP_UID}:${APP_GID} /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/agent/.local

# Copy application code
COPY --chown=${APP_UID}:${APP_GID} src/ ./src/

# Set environment
ENV PATH=/home/agent/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user using numeric UID (required for runAsNonRoot verification)
USER 10001

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
