# Dockerfile for Wega Userstory Validator
# Optimized for Google Cloud Platform deployment (Cloud Run / GKE)

# Use official Python runtime as base image. FROM python:3.11-slim
FROM public.ecr.aws/docker/library/python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    APP_HOME=/app

# Set work directory
WORKDIR ${APP_HOME}

# Install system dependencies including build tools for pycairo/xhtml2pdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libcairo2-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy requirements first (for better Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .

# Change ownership to non-root user
RUN chown -R appuser:appuser ${APP_HOME}

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:${PORT}/health || exit 1

# Run the application with Gunicorn for production
# Using 2 workers as recommended for Cloud Run
CMD exec gunicorn --bind :${PORT} --workers 2 --threads 4 --timeout 120 server:app
