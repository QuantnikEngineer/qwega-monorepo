# syntax=docker/dockerfile:1

# ---- Base image ----
FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files; ensure unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ---- System dependencies ----
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# ---- Install Python dependencies ----
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && python -m spacy download en_core_web_sm

# ---- Copy application code (includes .env) ----
COPY . .

# ---- Runtime environment ----
# Cloud Run sets PORT automatically; default to 8080 for local runs
ENV PORT=8080

# ---- Start command ----
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
