# ---- Base image ----
FROM public.ecr.aws/docker/library/python:3.11-slim

# Prevent Python from writing .pyc files; ensure unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# ---- System dependencies ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# ---- Install uv ----
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# ---- Install Python dependencies via uv ----
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-editable --frozen

# ---- Copy application code and data ----
COPY . .

# ---- Runtime environment ----
# Cloud Run will set PORT; we default to 8080 for local runs
ENV PORT=8080
ENV OUTPUT_DIR=/tmp/outputs
ENV PATH="/app/.venv/bin:$PATH"

# Create a writable output directory (ephemeral on Cloud Run)
RUN mkdir -p /tmp/outputs

# ---- Start command ----
EXPOSE 8080
# Use $PORT so it works both locally and on Cloud Run
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
