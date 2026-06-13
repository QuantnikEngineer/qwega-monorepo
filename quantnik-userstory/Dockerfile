
# syntax=docker/dockerfile:1

# ---- Base image ----
FROM public.ecr.aws/docker/library/python:3.11-slim

# Prevent Python from writing .pyc files; ensure unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# ---- System dependencies (add more if your libs need them) ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# ---- Install Python dependencies ----
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ---- Copy application code and data ----
COPY . .

# ---- Runtime environment ----
# Cloud Run will set PORT; we default to 8080 for local runs
ENV PORT=8080

# ---- Start command ----
EXPOSE 8080
# ✅ Use $PORT so it works both locally and on Cloud Run
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
