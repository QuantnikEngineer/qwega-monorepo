# Dockerfile Base Registry Template

## Overview

All QUANTNIK repositories should update their Dockerfiles to use the `BASE_REGISTRY` build argument. This allows the same Dockerfile to work across CloudRun (GCP), ACA (Azure), and ECS (AWS) deployments.

## Base Image Registries

| Platform | Registry URL |
|----------|--------------|
| **CloudRun (GCP)** | `us-central1-docker.pkg.dev/digital-rig-poc/quantnik-build-baseimages` |
| **ACA (Azure)** | `quantnikdev.azurecr.io/base-images` |
| **ECS (AWS)** | `145748108830.dkr.ecr.ap-south-1.amazonaws.com/base-images` |

## Available Base Images

| Image | Tag | Description |
|-------|-----|-------------|
| python | 3.11-slim | Python 3.11 slim |
| python | 3.12-slim | Python 3.12 slim |
| node | 20-slim | Node.js 20 slim |
| nginx | stable-alpine | Nginx stable alpine |

## Dockerfile Template

### Python Backend (Single Stage)

```dockerfile
ARG BASE_REGISTRY=docker.io/library
FROM ${BASE_REGISTRY}/python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
CMD ["python", "main.py"]
```

### Python Backend (Multi-Stage)

```dockerfile
ARG BASE_REGISTRY=docker.io/library

# Build stage
FROM ${BASE_REGISTRY}/python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM ${BASE_REGISTRY}/python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .

EXPOSE 8000
CMD ["python", "main.py"]
```

### Node.js Frontend

```dockerfile
ARG BASE_REGISTRY=docker.io/library

# Build stage
FROM ${BASE_REGISTRY}/node:20-slim AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Runtime stage
FROM ${BASE_REGISTRY}/nginx:stable-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Node.js Backend

```dockerfile
ARG BASE_REGISTRY=docker.io/library
FROM ${BASE_REGISTRY}/node:20-slim

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .

EXPOSE 3000
CMD ["node", "server.js"]
```

## How It Works

1. Pipeline sets `baseImageRegistry` variable based on deployment target
2. `BuildAndPush` step passes it as Docker build argument:
   ```yaml
   buildArgs:
     BASE_REGISTRY: <+pipeline.variables.baseImageRegistry>
   ```
3. Dockerfile uses the ARG to construct full image path:
   ```dockerfile
   ARG BASE_REGISTRY=docker.io/library
   FROM ${BASE_REGISTRY}/python:3.11-slim
   ```

## Migration Steps

1. Update your Dockerfile to add `ARG BASE_REGISTRY=docker.io/library` at the top
2. Change `FROM python:3.11-slim` to `FROM ${BASE_REGISTRY}/python:3.11-slim`
3. For multi-stage builds, add the ARG before each FROM that needs it
4. Test locally: `docker build --build-arg BASE_REGISTRY=docker.io/library .`

## Notes

- Default `docker.io/library` allows local builds without specifying the argument
- AWS ECR Node image uses `common:node-20-slim` path (slightly different from others)
- All registries contain the same image content, just different locations
