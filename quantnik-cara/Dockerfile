# syntax=docker/dockerfile:1.7

# ---------- Stage 1: builder ----------
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY cara ./cara

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

# ---------- Stage 2: runtime ----------
FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080 \
    REPORTS_BASE_PATH=/tmp/reports

# `git` is required at runtime for the universal repo-clone path used by both
# GitHub and Harness Code providers; ca-certificates lets git verify HTTPS
# remotes. Both apt artefacts are removed afterwards to keep the image lean.
RUN apt-get update \
 && apt-get install --no-install-recommends -y git ca-certificates \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 999 app \
 && useradd  --system --uid 999 --gid 999 --home /app --shell /sbin/nologin app \
 && mkdir -p /tmp/reports \
 && chown -R app:app /tmp/reports

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY --chown=app:app main.py ./
COPY --chown=app:app cara ./cara

USER app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/openapi.json', timeout=3).status == 200 else 1)"

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
