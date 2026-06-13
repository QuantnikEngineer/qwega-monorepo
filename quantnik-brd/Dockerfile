# syntax=docker/dockerfile:1

# ---- Base image ----
FROM public.ecr.aws/docker/library/python:3.11-slim

# Prevent Python from writing .pyc files; ensure unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ---- System dependencies + Node.js 20 LTS ----
# Node is required to run utils/generate_brd_docx.js as a subprocess
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        gnupg \
        ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ---- Install Python dependencies ----
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ---- Install Node.js dependencies ----
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev

# ---- Copy application code ----
COPY . .

# ---- Runtime environment ----
# Cloud Run sets PORT automatically; default to 8080 for local runs
ENV PORT=8080
ENV BRD_OUTPUT_DIR=/tmp/output

# Create a writable output directory (ephemeral on Cloud Run)
RUN mkdir -p /tmp/output

# ---- Non-root user ----
RUN groupadd --gid 1001 appuser \
 && useradd --uid 1001 --gid appuser --shell /bin/false appuser \
 && chown -R appuser:appuser /tmp/output
USER appuser

# ---- Health check ----
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]

# ---- Start command ----
EXPOSE 8080
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
