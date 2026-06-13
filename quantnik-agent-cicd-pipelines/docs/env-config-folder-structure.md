# Environment Configuration Folder Structure
## Per-Service Repository Structure

---

## Folder Structure

```
quantnik-brd/                           # Service repository
├── source/
│   ├── Dockerfile
│   ├── main.py
│   └── ...
│
└── config/                         # Environment configuration (root level)
    │
    ├── common.yaml                 # Shared across ALL clouds & environments
    │
    ├── secrets.yaml                # Secret references (names only)
    │
    ├── gcp/                        # GCP Cloud Run configs
    │   ├── common.yaml             # GCP-specific, all environments
    │   ├── dev.yaml
    │   ├── qa.yaml
    │   ├── staging.yaml
    │   └── prod.yaml
    │
    ├── azure/                      # Azure ACA configs
    │   ├── common.yaml             # Azure-specific, all environments
    │   ├── dev.yaml
    │   ├── qa.yaml
    │   ├── staging.yaml
    │   └── prod.yaml
    │
    └── aws/                        # AWS ECS configs
        ├── common.yaml             # AWS-specific, all environments
        ├── dev.yaml
        ├── qa.yaml
        ├── staging.yaml
        └── prod.yaml
```

---

## File Contents

### 1. `config/common.yaml`
**Shared across ALL clouds and environments**

```yaml
# config/common.yaml
# Global configuration - applies to all clouds and environments
# Maintained by: Development Team

service:
  name: quantnik-brd
  version: "3.0"

env:
  # Application settings
  PYTHONUNBUFFERED: "1"
  LOG_FORMAT: json
  
  # Timeouts and retries
  API_TIMEOUT: "30"
  MAX_RETRIES: "3"
  CONNECTION_TIMEOUT: "10"
  
  # Feature flags (global defaults)
  FEATURE_METRICS_ENABLED: "true"
  FEATURE_TRACING_ENABLED: "true"
```

---

### 2. `.harness/config/secrets.yaml`
**Secret references - same structure for all clouds**

```yaml
# config/secrets.yaml
# Secret references (names only - values stored in cloud secret managers)
# Maintained by: Development Team
# 
# To add a new secret:
# 1. Request DevOps to create secret in cloud secret managers
# 2. Add reference here
# 3. Use in code via os.getenv('SECRET_NAME')

secrets:
  # Database
  - envVar: DB_PASSWORD
    description: "PostgreSQL database password"
    required: true
    
  - envVar: DB_CONNECTION_STRING
    description: "Full database connection string"
    required: true

  # External APIs
  - envVar: OPENAI_API_KEY
    description: "OpenAI API key for LLM calls"
    required: true
    
  - envVar: JIRA_API_TOKEN
    description: "Jira API token for integration"
    required: false

  # Security
  - envVar: JWT_SECRET
    description: "JWT signing secret"
    required: true
    
  - envVar: ENCRYPTION_KEY
    description: "Data encryption key"
    required: true

  # Cache
  - envVar: REDIS_PASSWORD
    description: "Redis cache password"
    required: false
```

---

### 3. `.harness/config/gcp/common.yaml`
**GCP-specific settings for all environments**

```yaml
# config/gcp/common.yaml
# GCP Cloud Run specific configuration - all environments
# Maintained by: Development Team

env:
  # GCP-specific settings
  CLOUD_PROVIDER: gcp
  CLOUD_RUN_REGION: us-central1
  
  # GCP service URLs (base patterns)
  GCP_PROJECT_ID: quantnik-gcp-project
  
  # Logging
  GOOGLE_CLOUD_LOGGING: "true"
  
  # Health checks
  HEALTH_CHECK_PATH: /health
  READINESS_CHECK_PATH: /ready
```

---

### 4. `.harness/config/gcp/dev.yaml`
**GCP Dev environment**

```yaml
# config/gcp/dev.yaml
# GCP Cloud Run - Development environment
# Maintained by: Development Team

env:
  # Environment identifier
  ENVIRONMENT: dev
  
  # Logging
  LOG_LEVEL: DEBUG
  
  # Debug features
  FEATURE_DEBUG_MODE: "true"
  FEATURE_VERBOSE_ERRORS: "true"
  
  # Service URLs
  API_BASE_URL: https://dev-api.quantnik.example.com
  AUTH_SERVICE_URL: https://dev-quantnik-auth-service-xxxxx.run.app
  
  # Database
  DB_HOST: dev-postgres.quantnik.internal
  DB_PORT: "5432"
  DB_NAME: quantnik_dev
  
  # Cache
  REDIS_HOST: dev-redis.quantnik.internal
  REDIS_PORT: "6379"
  
  # Performance (lower for dev)
  MAX_WORKERS: "2"
  MEMORY_LIMIT: "512Mi"
```

---

### 5. `.harness/config/gcp/qa.yaml`
**GCP QA environment**

```yaml
# config/gcp/qa.yaml
# GCP Cloud Run - QA environment
# Maintained by: Development Team

env:
  ENVIRONMENT: qa
  LOG_LEVEL: INFO
  
  FEATURE_DEBUG_MODE: "false"
  FEATURE_VERBOSE_ERRORS: "true"
  
  API_BASE_URL: https://qa-api.quantnik.example.com
  AUTH_SERVICE_URL: https://qa-quantnik-auth-service-xxxxx.run.app
  
  DB_HOST: qa-postgres.quantnik.internal
  DB_PORT: "5432"
  DB_NAME: quantnik_qa
  
  REDIS_HOST: qa-redis.quantnik.internal
  REDIS_PORT: "6379"
  
  MAX_WORKERS: "4"
  MEMORY_LIMIT: "1Gi"
```

---

### 6. `.harness/config/gcp/staging.yaml`
**GCP Staging environment**

```yaml
# config/gcp/staging.yaml
# GCP Cloud Run - Staging environment
# Maintained by: Development Team

env:
  ENVIRONMENT: staging
  LOG_LEVEL: INFO
  
  FEATURE_DEBUG_MODE: "false"
  FEATURE_VERBOSE_ERRORS: "false"
  
  API_BASE_URL: https://staging-api.quantnik.example.com
  AUTH_SERVICE_URL: https://staging-quantnik-auth-service-xxxxx.run.app
  
  DB_HOST: staging-postgres.quantnik.internal
  DB_PORT: "5432"
  DB_NAME: quantnik_staging
  
  REDIS_HOST: staging-redis.quantnik.internal
  REDIS_PORT: "6379"
  
  MAX_WORKERS: "4"
  MEMORY_LIMIT: "1Gi"
```

---

### 7. `.harness/config/gcp/prod.yaml`
**GCP Production environment**

```yaml
# config/gcp/prod.yaml
# GCP Cloud Run - Production environment
# Maintained by: Development Team
# 
# ⚠️  CAUTION: Changes to this file affect production!
#     Ensure proper review before merging.

env:
  ENVIRONMENT: prod
  LOG_LEVEL: WARN
  
  FEATURE_DEBUG_MODE: "false"
  FEATURE_VERBOSE_ERRORS: "false"
  
  API_BASE_URL: https://api.quantnik.example.com
  AUTH_SERVICE_URL: https://quantnik-auth-service-xxxxx.run.app
  
  DB_HOST: prod-postgres.quantnik.internal
  DB_PORT: "5432"
  DB_NAME: quantnik_prod
  
  REDIS_HOST: prod-redis.quantnik.internal
  REDIS_PORT: "6379"
  
  # Production performance
  MAX_WORKERS: "8"
  MAX_RETRIES: "5"
  MEMORY_LIMIT: "2Gi"
  
  # Production features
  FEATURE_RATE_LIMITING: "true"
  RATE_LIMIT_RPM: "1000"
```

---

### 8. `.harness/config/azure/common.yaml`
**Azure-specific settings for all environments**

```yaml
# config/azure/common.yaml
# Azure Container Apps specific configuration - all environments
# Maintained by: Development Team

env:
  # Azure-specific settings
  CLOUD_PROVIDER: azure
  AZURE_REGION: eastus
  
  # Azure settings
  AZURE_SUBSCRIPTION_ID: your-subscription-id
  
  # Application Insights
  APPLICATIONINSIGHTS_ENABLED: "true"
  
  # Health checks
  HEALTH_CHECK_PATH: /health
  READINESS_CHECK_PATH: /ready
```

---

### 9. `.harness/config/azure/dev.yaml`
**Azure Dev environment**

```yaml
# config/azure/dev.yaml
# Azure Container Apps - Development environment

env:
  ENVIRONMENT: dev
  LOG_LEVEL: DEBUG
  
  FEATURE_DEBUG_MODE: "true"
  FEATURE_VERBOSE_ERRORS: "true"
  
  API_BASE_URL: https://dev-api.quantnik.azurecontainer.io
  AUTH_SERVICE_URL: https://dev-quantnik-auth.azurecontainer.io
  
  # Azure Database
  DB_HOST: dev-quantnik-db.postgres.database.azure.com
  DB_PORT: "5432"
  DB_NAME: quantnik_dev
  
  # Azure Cache for Redis
  REDIS_HOST: dev-quantnik-redis.redis.cache.windows.net
  REDIS_PORT: "6380"
  REDIS_SSL: "true"
  
  MAX_WORKERS: "2"
```

---

### 10. `.harness/config/azure/prod.yaml`
**Azure Production environment**

```yaml
# config/azure/prod.yaml
# Azure Container Apps - Production environment
#
# ⚠️  CAUTION: Changes affect production!

env:
  ENVIRONMENT: prod
  LOG_LEVEL: WARN
  
  FEATURE_DEBUG_MODE: "false"
  FEATURE_VERBOSE_ERRORS: "false"
  
  API_BASE_URL: https://api.quantnik.azurecontainer.io
  AUTH_SERVICE_URL: https://quantnik-auth.azurecontainer.io
  
  DB_HOST: prod-quantnik-db.postgres.database.azure.com
  DB_PORT: "5432"
  DB_NAME: quantnik_prod
  
  REDIS_HOST: prod-quantnik-redis.redis.cache.windows.net
  REDIS_PORT: "6380"
  REDIS_SSL: "true"
  
  MAX_WORKERS: "8"
  MAX_RETRIES: "5"
```

---

### 11. `.harness/config/aws/common.yaml`
**AWS-specific settings for all environments**

```yaml
# config/aws/common.yaml
# AWS ECS specific configuration - all environments
# Maintained by: Development Team

env:
  # AWS-specific settings
  CLOUD_PROVIDER: aws
  AWS_REGION: us-east-1
  
  # CloudWatch
  CLOUDWATCH_LOGGING: "true"
  
  # X-Ray tracing
  AWS_XRAY_ENABLED: "true"
  
  # Health checks
  HEALTH_CHECK_PATH: /health
  READINESS_CHECK_PATH: /ready
```

---

### 12. `.harness/config/aws/dev.yaml`
**AWS Dev environment**

```yaml
# config/aws/dev.yaml
# AWS ECS - Development environment

env:
  ENVIRONMENT: dev
  LOG_LEVEL: DEBUG
  
  FEATURE_DEBUG_MODE: "true"
  FEATURE_VERBOSE_ERRORS: "true"
  
  API_BASE_URL: https://dev-api.quantnik.aws.example.com
  AUTH_SERVICE_URL: https://dev-quantnik-auth.ecs.aws.example.com
  
  # AWS RDS
  DB_HOST: dev-quantnik-db.xxxxx.us-east-1.rds.amazonaws.com
  DB_PORT: "5432"
  DB_NAME: quantnik_dev
  
  # AWS ElastiCache
  REDIS_HOST: dev-quantnik-redis.xxxxx.cache.amazonaws.com
  REDIS_PORT: "6379"
  
  MAX_WORKERS: "2"
```

---

### 13. `.harness/config/aws/prod.yaml`
**AWS Production environment**

```yaml
# config/aws/prod.yaml
# AWS ECS - Production environment
#
# ⚠️  CAUTION: Changes affect production!

env:
  ENVIRONMENT: prod
  LOG_LEVEL: WARN
  
  FEATURE_DEBUG_MODE: "false"
  FEATURE_VERBOSE_ERRORS: "false"
  
  API_BASE_URL: https://api.quantnik.aws.example.com
  AUTH_SERVICE_URL: https://quantnik-auth.ecs.aws.example.com
  
  DB_HOST: prod-quantnik-db.xxxxx.us-east-1.rds.amazonaws.com
  DB_PORT: "5432"
  DB_NAME: quantnik_prod
  
  REDIS_HOST: prod-quantnik-redis.xxxxx.cache.amazonaws.com
  REDIS_PORT: "6379"
  
  MAX_WORKERS: "8"
  MAX_RETRIES: "5"
```

---

## Configuration Merge Order

Pipeline merges configs in this order (later overrides earlier):

```
1. common.yaml                    # Global defaults
       ↓
2. {cloud}/common.yaml            # Cloud-specific defaults
       ↓
3. {cloud}/{env}.yaml             # Environment-specific
       ↓
4. secrets.yaml                   # Secret references added
```

**Example for GCP Dev:**
```
common.yaml → gcp/common.yaml → gcp/dev.yaml → secrets.yaml
```

**Resulting environment variables:**
```
# From common.yaml
PYTHONUNBUFFERED=1
LOG_FORMAT=json
API_TIMEOUT=30

# From gcp/common.yaml
CLOUD_PROVIDER=gcp
GCP_PROJECT_ID=quantnik-gcp-project

# From gcp/dev.yaml (overrides LOG_LEVEL from common)
ENVIRONMENT=dev
LOG_LEVEL=DEBUG
API_BASE_URL=https://dev-api.quantnik.example.com

# From secrets.yaml (injected from GCP Secret Manager)
DB_PASSWORD=<actual_value>
OPENAI_API_KEY=<actual_value>
```

---

## Quick Reference

| File | Purpose | Example Content |
|------|---------|-----------------|
| `common.yaml` | All clouds, all envs | `API_TIMEOUT`, `LOG_FORMAT` |
| `secrets.yaml` | Secret references | `DB_PASSWORD`, `API_KEY` |
| `gcp/common.yaml` | GCP all envs | `GCP_PROJECT_ID`, `CLOUD_PROVIDER` |
| `gcp/dev.yaml` | GCP Dev only | `LOG_LEVEL=DEBUG`, `DB_HOST` |
| `gcp/prod.yaml` | GCP Prod only | `LOG_LEVEL=WARN`, `MAX_WORKERS=8` |
| `azure/common.yaml` | Azure all envs | `AZURE_REGION`, `CLOUD_PROVIDER` |
| `azure/dev.yaml` | Azure Dev only | Azure-specific Dev settings |
| `aws/common.yaml` | AWS all envs | `AWS_REGION`, `CLOUD_PROVIDER` |
| `aws/dev.yaml` | AWS Dev only | AWS-specific Dev settings |

---

## Developer Workflow

### Adding a new env variable (all environments)
```yaml
# Edit .harness/config/common.yaml
env:
  NEW_VARIABLE: "value"
```

### Adding a cloud-specific variable
```yaml
# Edit .harness/config/gcp/common.yaml (for all GCP envs)
# OR .harness/config/gcp/dev.yaml (for GCP Dev only)
env:
  GCP_SPECIFIC_VAR: "value"
```

### Adding a new secret
```yaml
# Edit .harness/config/secrets.yaml
secrets:
  - envVar: NEW_SECRET
    description: "Description"
    required: true
```

---

*QUANTNIK CI/CD - Environment Configuration Structure*
*Version 1.0 | May 2026*
