# FROM python:3.11-slim
FROM public.ecr.aws/docker/library/python:3.11-slim

WORKDIR /app

# Prevent man-pages and documentation from being installed (avoids GPL-licensed man-pages)
RUN echo 'path-exclude /usr/share/man/*' > /etc/dpkg/dpkg.cfg.d/excludes && \
    echo 'path-exclude /usr/share/doc/*' >> /etc/dpkg/dpkg.cfg.d/excludes && \
    echo 'path-exclude /usr/share/info/*' >> /etc/dpkg/dpkg.cfg.d/excludes && \
    rm -rf /usr/share/man /usr/share/doc /usr/share/info

# Install clang (Apache 2.0 + LLVM Exception - permissive license)
RUN apt-get update && apt-get install -y --no-install-recommends \
    clang \
    && rm -rf /var/lib/apt/lists/*

ENV CC=clang

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Cloud Run uses PORT env var)
EXPOSE 8080

# Run the application - Cloud Run sets PORT env var (default 8080)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
