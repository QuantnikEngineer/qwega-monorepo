# syntax=docker/dockerfile:1

# ---- uv installer ----
FROM ghcr.io/astral-sh/uv:latest AS uv

# ---- Build stage ----
FROM public.ecr.aws/docker/library/python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-hashes -o /tmp/requirements.txt \
 && grep -viE "^(torch|triton|nvidia)" /tmp/requirements.txt > /tmp/req-filtered.txt \
 && uv pip install --system --native-tls torch --index-url https://download.pytorch.org/whl/cpu \
 && uv pip install --system --native-tls -r /tmp/req-filtered.txt \
 && python -m spacy download en_core_web_sm

# ---- Runtime stage ----
FROM public.ecr.aws/docker/library/python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=appuser:appuser . .
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

# Create upload directory owned by appuser
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app/uploads

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["/app/start.sh"]
