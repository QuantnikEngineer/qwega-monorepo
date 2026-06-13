# Use official Python runtime as base image
ARG BASE_REGISTRY=docker.io
FROM ${BASE_REGISTRY}/python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code, utils/, scripts/ and the corporate cert/ bundle in a
# single layer. .dockerignore excludes .env, .git, __pycache__, IDE files, etc.
# so secrets/config must still be injected at runtime via deploy-time env vars
# (Harness CI / Cloud Run / K8s secrets). The cert/ folder is required so
# build_cert_bundle.build() can construct a combined CA PEM at runtime
# (certifi + cert/Cert.txt + optional LANGFUSE_CA_CERT env override) BEFORE
# any networking library is imported by main.py.
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Run the instrumented entry point (Langfuse tracing enabled).
# To run WITHOUT instrumentation, change to: CMD ["python", "api_server.py"]
CMD ["python", "main.py"]
