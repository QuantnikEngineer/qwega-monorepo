# Complete Security Tools Implementation Guide: Semgrep, Trivy, Snyk & SonarQube

## Overview

This document outlines comprehensive requirements and implementation steps for all security scanning tools in the Quantnik Agent CICD Pipeline:

- **Semgrep** (SAST - currently active)
- **Trivy** (Container scanning - currently active)  
- **Snyk** (Dependency + Container scanning - recommended addition)
- **SonarQube** (Code quality + Security - advanced addition)

Includes free tier, professional, and enterprise plan requirements for each tool.

---

## Part 1: SEMGREP Integration (SAST)

### 1.1 Semgrep Overview

**Purpose:** Static Application Security Testing (SAST) - Identifies security vulnerabilities, code quality issues, and compliance violations in source code.

**Current Status:** ✅ **ACTIVE** - Already integrated and running in pipeline

**Capability Comparison:**

| Feature | Free Tier | Pro | Enterprise |
|---------|-----------|-----|------------|
| CLI Analysis | ✅ | ✅ | ✅ |
| Local Caching | ✅ | ✅ | ✅ |
| 3500+ Built-in Rules | ✅ | ✅ | ✅ |
| Custom Rules | ✅ | ✅ | ✅ |
| CI/CD Integration | ✅ | ✅ | ✅ |
| JSON/SARIF Reports | ✅ | ✅ | ✅ |
| Semgrep App (Web Dashboard) | Limited | ✅ | ✅ |
| SSO/SAML | ❌ | ❌ | ✅ |
| Advanced Filtering | ❌ | ✅ | ✅ |
| Triage Management | ❌ | ✅ | ✅ |
| Deduplication | ❌ | ✅ | ✅ |
| PR Comments | ❌ | ✅ | ✅ |
| Dedicated Support | ❌ | Business Hours | 24/7 |
| SLA Guarantee | ❌ | ❌ | ✅ |

### 1.2 Free Tier Requirements (Current Implementation)

#### 1.2.1 Prerequisites
- [ ] Semgrep CLI installed (via pip or npm)
- [ ] No authentication required
- [ ] Shell access in CI/CD environment
- [ ] ~30-60s per scan for typical codebases

#### 1.2.2 Current Pipeline Implementation

**Location:** After `CloneRepo`, before `BuildAndPushECR` in Build_Repo stage

**Current YAML** (already in pipeline):
```yaml
- step:
    type: Run
    name: Semgrep_SAST_Scan
    identifier: SemgrepSastScan
    spec:
      shell: Sh
      command: |
        echo "Installing Semgrep..."
        pip install semgrep -q 2>&1
        
        # Verify installation
        if ! command -v semgrep &> /dev/null; then
          echo "Semgrep not found via pip, trying npm..."
          npm install -g semgrep -q 2>&1
        fi
        
        echo "Verifying Semgrep installation:"
        semgrep --version
        
        cd source
        echo "Running Semgrep SAST scan on <+matrix.repo.repoName>"
        
        semgrep --json --output=../semgrep-report.json . 2>&1 || echo "Semgrep scan completed with status check warnings"
        
        echo "✓ Semgrep scan completed"
    outputVariables: []
```

### 1.3 Professional Tier Requirements (+$50/month)

#### 1.3.1 Semgrep App Features
- [ ] Create account at https://semgrep.dev
- [ ] Connect GitHub/GitLab repository
- [ ] Generate API token for CI/CD
- [ ] Store token in Harness: `semgrepApiToken`

#### 1.3.2 Professional Implementation

**Add to pipeline variables:**
```yaml
- name: semgrepApiToken
  type: Secret
  value: <+secrets.getValue("semgrepApiToken")>
- name: semgrepOrgSlug
  type: String
  value: <+input>.default(your-org-slug)
```

**Enhanced Pipeline Step:**
```yaml
- step:
    type: Run
    name: Semgrep_SAST_Scan_Pro
    identifier: SemgrepSastScanPro
    spec:
      shell: Sh
      command: |
        echo "Installing Semgrep Pro..."
        pip install semgrep -q 2>&1
        
        cd source
        echo "Running Semgrep with Pro features..."
        
        # Login to Semgrep App
        semgrep login --token <+secrets.getValue("semgrepApiToken")>
        
        # Run scan with app integration
        semgrep --config=p/security-audit \
                --json \
                --output=../semgrep-report.json \
                --organization=<+pipeline.variables.semgrepOrgSlug> \
                . 2>&1
        
        # Push results to app
        semgrep ci 2>&1 || echo "Results pushed to Semgrep App"
        
        cd ..
        echo "✓ Semgrep scan with Pro triage completed"
    outputVariables: []
```

**Pro Features Enabled:**
- ✅ Centralized dashboard at semgrep.dev
- ✅ Triage and deduplication of findings
- ✅ Advanced filtering capabilities
- ✅ Integration with PR/MR workflows
- ✅ History and trend tracking

### 1.4 Enterprise Tier Requirements (+$5000+/year)

#### 1.4.1 Enterprise Features
- [ ] Dedicated account manager
- [ ] Custom rule development support
- [ ] SSO/SAML authentication
- [ ] Advanced filtering and policies
- [ ] 24/7 priority support
- [ ] SLA guarantees (>99.5% uptime)

#### 1.4.2 Enterprise Implementation

**Harness Integration:**
```yaml
- name: semgrepEnterpriseUrl
  type: String
  value: <+input>.default(https://semgrep.dev)
- name: semgrepEnterpriseApiToken
  type: Secret
  value: <+secrets.getValue("semgrepEnterpriseApiToken")>
```

**Enterprise Step with Custom Rules:**
```yaml
- step:
    type: Run
    name: Semgrep_Enterprise_Scan
    identifier: SemgrepEnterpriseScan
    spec:
      shell: Sh
      command: |
        echo "Installing Semgrep Enterprise..."
        pip install semgrep -q 2>&1
        
        cd source
        
        # Configure enterprise endpoint
        export SEMGREP_APP_URL=<+pipeline.variables.semgrepEnterpriseUrl>
        export SEMGREP_APP_TOKEN=<+secrets.getValue("semgrepEnterpriseApiToken")>
        
        echo "Running Enterprise Semgrep with custom policies..."
        
        # Include both built-in + custom enterprise rules
        semgrep --config=p/security-audit \
                --config=p/owasp-top-ten \
                --config=custom/enterprise-policies \
                --json \
                --output=../semgrep-report.json \
                --metrics=on \
                --force-color \
                . 2>&1
        
        echo "Pushing to Enterprise Dashboard..."
        semgrep ci --metrics 2>&1
        
        cd ..
        echo "✓ Enterprise Semgrep scan completed with policy enforcement"
    outputVariables: []
```

### 1.5 Semgrep Cost & Performance

| Tier | Cost | Rules | Support | Reports |
|------|------|-------|---------|---------|
| Free | $0 | 3500+ | Community | JSON/SARIF |
| Professional | $50/mo | 3500+ | Support Hours | Dashboard + API |
| Enterprise | $5000+/yr | Custom | 24/7 Dedicated | Full + Custom |

---

## Part 2: TRIVY Integration (Container Scanning)

### 2.1 Trivy Overview

**Purpose:** Container image scanning - Identifies vulnerabilities in OS packages, application dependencies, and misconfigurations in container images.

**Current Status:** ✅ **ACTIVE** - Already integrated and running in pipeline

**Capability Comparison:**

| Feature | Free | Professional | Enterprise |
|---------|------|--------------|------------|
| Container Image Scanning | ✅ | ✅ | ✅ |
| Filesystem Scanning | ✅ | ✅ | ✅ |
| Git Repository Scanning | ✅ | ✅ | ✅ |
| Config/IaC Scanning | ✅ | ✅ | ✅ |
| License Detection | ✅ | ✅ | ✅ |
| Multiple Report Formats | ✅ | ✅ | ✅ |
| Offline Database | Limited | ✅ | ✅ |
| Custom Policies (OPA/Rego) | ❌ | ✅ | ✅ |
| Webhook Integration | ❌ | ✅ | ✅ |
| API Server (persistent) | ❌ | ✅ | ✅ |
| RBAC | ❌ | ❌ | ✅ |
| Audit Logging | ❌ | ❌ | ✅ |
| Signed Artifacts | ❌ | ❌ | ✅ |
| SLA Support | ❌ | ❌ | ✅ |

### 2.2 Free Tier Requirements (Current Implementation)

#### 2.2.1 Prerequisites
- [ ] Trivy CLI (curl-based installation)
- [ ] No authentication required
- [ ] AWS ECR access for image scanning
- [ ] ~1-2 minutes per image scan

#### 2.2.2 Current Pipeline Implementation

**Location:** After `BuildAndPushECR`, before `Deploy_To_EKS` in Build_Repo stage

**Current YAML** (already in pipeline):
```yaml
- step:
    type: Run
    name: Trivy_Container_Scan
    identifier: TrivyContainerScan
    when:
      stageStatus: Success
    spec:
      shell: Sh
      command: |
        echo "Working directory:"
        pwd
        
        echo "Installing Trivy..."
        curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
        
        REGISTRY="<+pipeline.variables.ecrRegistry>"
        REGION="<+pipeline.variables.awsRegion>"
        SEVERITY="<+pipeline.variables.trivyScanSeverity>"
        
        echo "AWS Region: $REGION"
        echo "Registry: $REGISTRY"
        echo "Severity: $SEVERITY"
        
        # Scan backend image if it exists
        if [ ! -z "<+matrix.repo.backendImage>" ]; then
          BACKEND_IMAGE="$REGISTRY/<+matrix.repo.backendImage>:<+pipeline.variables.imageTag>"
          echo "Scanning backend image: $BACKEND_IMAGE"
          trivy image --severity $SEVERITY --exit-code 0 --format json --output trivy-backend-report.json "$BACKEND_IMAGE" 2>&1 || echo "Backend scan completed with warnings"
          if [ -f trivy-backend-report.json ]; then
            echo "✓ Backend report generated: $(wc -l < trivy-backend-report.json) lines"
          else
            echo "✗ Backend report NOT generated"
          fi
        fi
        
        # Scan frontend image if it exists
        if [ ! -z "<+matrix.repo.frontendImage>" ]; then
          FRONTEND_IMAGE="$REGISTRY/<+matrix.repo.frontendImage>:<+pipeline.variables.imageTag>"
          echo "Scanning frontend image: $FRONTEND_IMAGE"
          trivy image --severity $SEVERITY --exit-code 0 --format json --output trivy-frontend-report.json "$FRONTEND_IMAGE" 2>&1 || echo "Frontend scan completed with warnings"
          if [ -f trivy-frontend-report.json ]; then
            echo "✓ Frontend report generated: $(wc -l < trivy-frontend-report.json) lines"
          else
            echo "✗ Frontend report NOT generated"
          fi
        fi
        
        echo "Final directory listing:"
        ls -lah trivy-*.json 2>/dev/null || echo "No trivy reports found"
        echo "All files in working directory:"
        ls -la | head -20
        echo "Trivy container scans completed."
    outputVariables: []
```

### 2.3 Professional Tier Requirements (Enterprise Subscription)

#### 2.3.1 Aqua Enterprise Scanner Integration
- [ ] Deploy Aqua Trivy Enterprise Scanner
- [ ] Configure persistent API server
- [ ] Register with Trivy Pro license key
- [ ] Store credential in Harness: `trivyProLicense`

#### 2.3.2 Professional Implementation

**Add to pipeline variables:**
```yaml
- name: trivyProLicenseKey
  type: Secret
  value: <+secrets.getValue("trivyProLicenseKey")>
- name: trivyServerUrl
  type: String
  value: <+input>.default(http://trivy-server.default.svc.cluster.local:8080)
- name: trivyEnableOfflineDb
  type: String
  value: <+input>.default(true).allowedValues(true,false)
```

**Professional Pipeline Step:**
```yaml
- step:
    type: Run
    name: Trivy_Professional_Scan
    identifier: TrivyProfessionalScan
    when:
      stageStatus: Success
    spec:
      shell: Sh
      command: |
        echo "Running Trivy Professional Scan..."
        
        REGISTRY="<+pipeline.variables.ecrRegistry>"
        TRIVY_SERVER="<+pipeline.variables.trivyServerUrl>"
        LICENSE_KEY="<+secrets.getValue("trivyProLicenseKey")>"
        
        # Configure Trivy Pro license
        export TRIVY_LICENSE=$LICENSE_KEY
        
        # Enable offline database
        if [ "<+pipeline.variables.trivyEnableOfflineDb>" == "true" ]; then
          echo "Downloading Trivy offline database..."
          trivy image --download-db-only 2>&1
        fi
        
        # Scan backend with Pro features
        if [ ! -z "<+matrix.repo.backendImage>" ]; then
          BACKEND_IMAGE="$REGISTRY/<+matrix.repo.backendImage>:<+pipeline.variables.imageTag>"
          echo "Professional scan: $BACKEND_IMAGE"
          trivy image \
            --severity CRITICAL,HIGH \
            --format json \
            --output trivy-backend-report.json \
            --list-all-pkgs \
            --format sarif \
            --output trivy-backend-report.sarif \
            "$BACKEND_IMAGE" 2>&1
        fi
        
        # Scan frontend with Pro features
        if [ ! -z "<+matrix.repo.frontendImage>" ]; then
          FRONTEND_IMAGE="$REGISTRY/<+matrix.repo.frontendImage>:<+pipeline.variables.imageTag>"
          echo "Professional scan: $FRONTEND_IMAGE"
          trivy image \
            --severity CRITICAL,HIGH \
            --format json \
            --output trivy-frontend-report.json \
            --list-all-pkgs \
            --format sarif \
            --output trivy-frontend-report.sarif \
            "$FRONTEND_IMAGE" 2>&1
        fi
        
        echo "✓ Professional Trivy scans completed with SARIF reports"
    outputVariables: []
```

**Pro Features Enabled:**
- ✅ Offline vulnerability database
- ✅ SARIF format reports (GitHub integration)
- ✅ All package listing (complete BOM)
- ✅ Custom policies (Rego/OPA)
- ✅ Vulnerability grouping and deduplication

### 2.4 Enterprise Tier Requirements (Aqua CSP)

#### 2.4.1 Aqua Cloud Security Platform
- [ ] Deploy Aqua CSP (Cloud Security Platform)
- [ ] Full K8s security posture management
- [ ] Advanced policy engine (Rego)
- [ ] Webhook integration for remediation
- [ ] RBAC and audit logging
- [ ] Annual license: $50,000+

#### 2.4.2 Enterprise Implementation

**Infrastructure:**
```yaml
- name: aquaCspUrl
  type: String
  value: <+input>.default(https://aqua-csp.quantnik-prod.svc.cluster.local:8443)
- name: aquaCspApiToken
  type: Secret
  value: <+secrets.getValue("aquaCspApiToken")>
- name: trivyEnterprisePolicy
  type: String
  value: <+input>.default(enterprise-security-policy)
```

**Enterprise Pipeline Step:**
```yaml
- step:
    type: Run
    name: Trivy_Enterprise_Scan
    identifier: TrivyEnterpriseScan
    when:
      stageStatus: Success
    spec:
      shell: Sh
      command: |
        echo "Running Trivy Enterprise Scan with Aqua CSP..."
        
        REGISTRY="<+pipeline.variables.ecrRegistry>"
        CSP_URL="<+pipeline.variables.aquaCspUrl>"
        CSP_TOKEN="<+secrets.getValue("aquaCspApiToken")>"
        POLICY="<+pipeline.variables.trivyEnterprisePolicy>"
        
        # Configure Aqua CSP connection
        export TRIVY_REGISTRY_TOKEN=$CSP_TOKEN
        export TRIVY_CSP_URL=$CSP_URL
        
        echo "Authenticating with Aqua CSP..."
        
        # Scan backend with enterprise policy
        if [ ! -z "<+matrix.repo.backendImage>" ]; then
          BACKEND_IMAGE="$REGISTRY/<+matrix.repo.backendImage>:<+pipeline.variables.imageTag>"
          echo "Enterprise scan with policy: $POLICY"
          trivy image \
            --format json \
            --output trivy-backend-report.json \
            --format template \
            --template='@contrib/html.tpl' \
            --output trivy-backend-report.html \
            --custom-headers="Authorization: Bearer $CSP_TOKEN" \
            --registry-token=$CSP_TOKEN \
            "$BACKEND_IMAGE" 2>&1
        fi
        
        # Scan frontend with enterprise policy
        if [ ! -z "<+matrix.repo.frontendImage>" ]; then
          FRONTEND_IMAGE="$REGISTRY/<+matrix.repo.frontendImage>:<+pipeline.variables.imageTag>"
          trivy image \
            --format json \
            --output trivy-frontend-report.json \
            --format template \
            --template='@contrib/html.tpl' \
            --output trivy-frontend-report.html \
            --custom-headers="Authorization: Bearer $CSP_TOKEN" \
            --registry-token=$CSP_TOKEN \
            "$FRONTEND_IMAGE" 2>&1
        fi
        
        # Send scan results to webhook for remediation
        echo "Sending results to CSP for policy enforcement..."
        curl -X POST $CSP_URL/api/v1/scan-results \
          -H "Authorization: Bearer $CSP_TOKEN" \
          -H "Content-Type: application/json" \
          --data-binary @trivy-backend-report.json 2>&1
        
        echo "✓ Enterprise Trivy scans completed with policy enforcement"
    outputVariables: []
```

**Enterprise Features Enabled:**
- ✅ Centralized policy enforcement
- ✅ Advanced Rego policy language
- ✅ HTML report generation
- ✅ Webhook integration for automatic remediation
- ✅ RBAC and audit logging
- ✅ Integration with Aqua CSP dashboard

### 2.5 Trivy Cost & Performance

| Tier | Cost | Scans/Month | Support | Database |
|------|------|------------|---------|----------|
| Free | $0 | Unlimited | Community | Online |
| Professional | $2500-5000/yr | Unlimited | Business Hours | Offline + Online |
| Enterprise (CSP) | $50000+/yr | Unlimited | 24/7 | Full + Custom |

---

## Part 3: SNYK Integration

### 3.1 Snyk Overview

**Purpose:** Dependency vulnerability scanning and container image scanning with detailed remediation guidance.

**Capability Comparison:**

| Feature | Free | Developer | Pro | Enterprise |
|---------|------|-----------|-----|-----------|
| Dependency Scanning | ✅ | ✅ | ✅ | ✅ |
| Container Image Scanning | ✅ | ✅ | ✅ | ✅ |
| License Scanning | Limited | ✅ | ✅ | ✅ |
| Open Source Vulnerabilities | ✅ | ✅ | ✅ | ✅ |
| Code (SAST) | ❌ | ❌ | ✅ | ✅ |
| IaC Scanning | ❌ | ✅ | ✅ | ✅ |
| CLI Unlimited | ✅ | ✅ | ✅ | ✅ |
| Automated Remediation | ❌ | ✅ | ✅ | ✅ |
| API Access | ❌ | ✅ | ✅ | ✅ |
| Webhook Integration | ❌ | ❌ | ✅ | ✅ |
| Custom Rules (Policy) | ❌ | ❌ | ❌ | ✅ |
| SIEM Integration | ❌ | ❌ | ❌ | ✅ |
| SSO/SAML | ❌ | ❌ | $$$+ | ✅ |
| Dedicated Support | ❌ | ❌ | Optional | 24/7 |
| SLA | ❌ | ❌ | ❌ | ✅ (99.9%) |

### 3.2 Free Tier Requirements

#### 3.2.1 Snyk Account & API Token

- [ ] Create Snyk account at https://snyk.io/
- [ ] Navigate to Account Settings → API Token
- [ ] Copy the API token (keep this secure)
- [ ] Store in Harness as a secret: `snykApiToken`

**Harness Setup:**
```
Organization Settings → Secrets → New Secret
Name: snykApiToken
Value: <your-snyk-api-token>
Scope: Account or Organization
```

#### 3.2.2 Snyk CLI Installation

- [ ] Snyk CLI is installed automatically via npm in pipeline steps
- [ ] Alternative: Pre-install in Docker image for faster execution

#### 3.2.3 Snyk Command Access (Free Tier)

**Free Tier Capabilities:**
- ✅ `snyk test` - Dependency vulnerability scanning
- ✅ `snyk container test` - Container image scanning
- ✅ License scanning (basic)
- ❌ `snyk code test` - SAST (requires Pro/Enterprise)
- ❌ IaC scanning (Infrastructure as Code)
- ⚠️ Limited API access (CLI only)

**Limitations:**
- 100 dependency scans/month limit per organization (after that, CLI continues working)
- No automated remediation PRs
- No webhook integration
- Community support only
- No SLA

### 3.3 Implementation Steps (Free Tier)

#### Step 1: Add Snyk Authentication to Harness

**Create Secret in Harness:**
1. Go to Account Settings → Secrets → New Secret
2. Create Secret Name: `snykApiToken`
3. Add API Token value
4. Mark as: Reference Secret

#### Step 2: Add Snyk Dependency Scan Step

**Location in Pipeline:** Add after `CloneRepo` step in `Build_Repo` stage
```yaml
- step:
    type: Run
    name: Snyk_Dependency_Scan
    identifier: SnykDependencyScan
    spec:
      shell: Sh
      command: |
        echo "Installing Snyk CLI..."
        npm install -g snyk -q 2>&1
        
        echo "Authenticating with Snyk..."
        export SNYK_TOKEN=<+secrets.getValue("snykApiToken")>
        snyk auth $SNYK_TOKEN
        
        echo "Running Snyk dependency scan on <+matrix.repo.repoName>"
        cd source
        
        # Test dependencies for vulnerabilities
        snyk test --json --json-file-output=../snyk-dependency-report.json --severity-threshold=high || echo "Snyk test completed with findings"
        
        cd ..
        echo "✓ Snyk dependency scan completed"
    outputVariables: []
```

#### Step 3: Add Snyk Container Image Scan Step

**Location in Pipeline:** Add after `BuildAndPushECR` parallel steps

**Pipeline Configuration:**
```yaml
- step:
    type: Run
    name: Snyk_Container_Scan
    identifier: SnykContainerScan
    when:
      stageStatus: Success
    spec:
      shell: Sh
      command: |
        echo "Installing Snyk CLI..."
        npm install -g snyk -q 2>&1
        
        echo "Authenticating with Snyk..."
        export SNYK_TOKEN=<+secrets.getValue("snykApiToken")>
        snyk auth $SNYK_TOKEN
        
        REGISTRY="<+pipeline.variables.ecrRegistry>"
        
        # Scan backend image if it exists
        if [ ! -z "<+matrix.repo.backendImage>" ]; then
          BACKEND_IMAGE="$REGISTRY/<+matrix.repo.backendImage>:<+pipeline.variables.imageTag>"
          echo "Scanning backend container: $BACKEND_IMAGE"
          snyk container test "$BACKEND_IMAGE" --json --json-file-output snyk-backend-container-report.json --severity-threshold=high || true
        fi
        
        # Scan frontend image if it exists
        if [ ! -z "<+matrix.repo.frontendImage>" ]; then
          FRONTEND_IMAGE="$REGISTRY/<+matrix.repo.frontendImage>:<+pipeline.variables.imageTag>"
          echo "Scanning frontend container: $FRONTEND_IMAGE"
          snyk container test "$FRONTEND_IMAGE" --json --json-file-output snyk-frontend-container-report.json --severity-threshold=high || true
        fi
        
        echo "✓ Snyk container scans completed"
    outputVariables: []
```

#### Step 4: Add Display Step for Snyk Results

**Location in Pipeline:** Add after container scan step

**Pipeline Configuration:**
```yaml
- step:
    type: Run
    name: DisplaySnykResults
    identifier: DisplaySnykResults
    when:
      stageStatus: Success
    spec:
      shell: Sh
      command: |
        echo "========================================"
        echo "=== SNYK VULNERABILITY SCAN RESULTS ==="
        echo "========================================"
        
        echo ""
        echo "=== DEPENDENCY VULNERABILITIES ==="
        if [ -f snyk-dependency-report.json ]; then
          DEP_HIGH=$(jq '.metadata.severities.high // 0' snyk-dependency-report.json)
          DEP_MEDIUM=$(jq '.metadata.severities.medium // 0' snyk-dependency-report.json)
          DEP_LOW=$(jq '.metadata.severities.low // 0' snyk-dependency-report.json)
          echo "  🔴 HIGH: $DEP_HIGH"
          echo "  🟠 MEDIUM: $DEP_MEDIUM"
          echo "  🟡 LOW: $DEP_LOW"
          echo ""
          echo "Top vulnerable packages:"
          jq -r '.vulnerabilities[]? | select(.severity=="high") | "\(.nsp) - \(.title)"' snyk-dependency-report.json | head -5
        else
          echo "No dependency scan results"
        fi
        
        echo ""
        echo "=== CONTAINER IMAGE VULNERABILITIES ==="
        if [ -f snyk-backend-container-report.json ]; then
          BACKEND_HIGH=$(jq '.summary | select(.severities.high)' snyk-backend-container-report.json 2>/dev/null | wc -l)
          echo "Backend Image Vulnerabilities: $BACKEND_HIGH found"
        fi
        
        if [ -f snyk-frontend-container-report.json ]; then
          FRONTEND_HIGH=$(jq '.summary | select(.severities.high)' snyk-frontend-container-report.json 2>/dev/null | wc -l)
          echo "Frontend Image Vulnerabilities: $FRONTEND_HIGH found"
        fi
        
        echo ""
        echo "========================================"
    outputVariables: []
```

#### Step 5: Update Artifacts Configuration

Add to the `artifacts` section in `Build_Repo` stage:
```yaml
artifacts:
  - type: BuildContext
    name: security-reports
    spec:
      paths:
        - semgrep-report.json
        - trivy-backend-report.json
        - trivy-frontend-report.json
        - snyk-dependency-report.json           # NEW
        - snyk-backend-container-report.json    # NEW
        - snyk-frontend-container-report.json   # NEW
        - snyk-code-report.json                 # NEW (Pro+)
        - snyk-iac-report.json                  # NEW (Developer+)
```

---

## Part 4: SONARQUBE Integration

### 4.1 SonarQube Overview

**Purpose:** Comprehensive code quality, maintainability, security hotspot detection, and technical debt analysis.

**Differences from Semgrep:**
- Semgrep: Pattern-based SAST focused on security vulnerabilities
- SonarQube: Comprehensive code quality + security metrics tracking
- Together: Complete security and quality picture

**Capability Comparison:**

| Feature | Free Community | Developer ($29/mo) | Business ($529/mo) | Enterprise (contact) |
|---------|----------------|-------------------|-------------------|------------------|
| Multi-language Analysis | ✅ | ✅ | ✅ | ✅ |
| Code Quality Metrics | ✅ | ✅ | ✅ | ✅ |
| Security Rules | ✅ | ✅ | ✅ | ✅ |
| Security Hotspots | ✅ | ✅ | ✅ | ✅ |
| Code Coverage | ✅ | ✅ | ✅ | ✅ |
| Leak Period Tracking | ✅ | ✅ | ✅ | ✅ |
| PR Decoration | ✅ | ✅ | ✅ | ✅ |
| Webhooks | ❌ | ✅ | ✅ | ✅ |
| Governance | ❌ | ✅ | ✅ | ✅ |
| Project Transfer | ❌ | ✅ | ✅ | ✅ |
| Quality Model Customization | ❌ | ❌ | ✅ | ✅ |
| Audit Logs | ❌ | ❌ | ✅ | ✅ |
| SAML/SSO | ❌ | ❌ | Add-on $$$+ | ✅ |
| Dedicated Support | ❌ | ❌ | Optional | 24/7 |
| SLA | ❌ | ❌ | ❌ | ✅ (99.5%) |

### 4.2 Free Tier (SonarCloud Community) Prerequisites

#### 4.2.1 SonarQube Instance Setup

**Option A: SonarCloud (Recommended for Cloud)**
- [ ] Create account at https://sonarcloud.io/
- [ ] Register organization
- [ ] Generate token at User Settings → Security → Tokens
- [ ] Store token in Harness: `sonarcloudToken`

**Option B: Self-Hosted SonarQube (Enterprise)**
- [ ] Deploy SonarQube server (Docker, K8s, or VM)
- [ ] Access at `https://<your-sonarqube-url>`
- [ ] Generate token at User Settings → Security → Tokens
- [ ] Store URL + token in Harness

#### 4.2.2 SonarQube Connector in Harness

**For SonarCloud (Free/Community):**
```
Connectors → New Connector → SonarQube
Name: sonarcloud-connector-free
URL: https://sonarcloud.io
Authentication: Token
Token: <+secrets.getValue("sonarcloudToken")>
```

**For Self-Hosted SonarQube Community (Free):**
- [ ] Deploy via Docker: `docker run -d --name sonarqube sonarqube:community`
- [ ] Access: `http://localhost:9000` (default admin/admin)
- [ ] Create token at User Settings → Security → Tokens
- [ ] Store in Harness as `sonarqubeToken`

#### 4.2.3 Project Creation in SonarQube

For **each repository**, create project:
- Project Key: `quantnik-<repo-name>` (e.g., `quantnik-development-agent`)
- Project Name: `Quantnik - Development Agent`
- Organization: Your organization name

### 4.3 Free Tier Implementation

### 4.3 Free Tier Implementation

#### Step 1: Create SonarQube/SonarCloud Secrets

**In Harness:**
```
Account Settings → Secrets
1. Create: sonarcloudToken
   Value: <your-sonarcloud-token>
2. Create: sonarqubeUrl  
   Value: https://sonarcloud.io
```

#### Step 2: Add SonarQube Analysis Step (Free Tier)

**Location:** After `DisplaySemgrepResults` in Build_Repo stage

**Pipeline Configuration:**
```yaml
- step:
    type: Run
    name: SonarQube_Code_Quality_Scan
    identifier: SonarqubeCodeQualityScan
    spec:
      shell: Sh
      command: |
        echo "Installing SonarScanner CLI..."
        npm install -g sonarqube-scanner -q 2>&1
        
        echo "Running SonarQube analysis on <+matrix.repo.repoName>"
        
        cd source
        
        # Generate sonar-scanner configuration
        cat > ../sonar-project.properties <<EOF
        sonar.projectKey=quantnik-<+matrix.repo.repoName>
        sonar.projectName=Quantnik - <+matrix.repo.repoName>
        sonar.sources=.
        sonar.host.url=<+pipeline.variables.sonarqubeUrl>
        sonar.login=<+secrets.getValue("sonarcloudToken")>
        sonar.scm.provider=git
        sonar.scm.disabled=false
        sonar.sourceEncoding=UTF-8
        sonar.exclusions=**/node_modules/**,**/dist/**,**/.next/**
        sonar.javascript.lcov.reportPaths=coverage/lcov.info
        sonar.python.coverage.reportPath=coverage.xml
        EOF
        
        cd ..
        
        # Run SonarScanner
        sonar-scanner -Dproject.settings=sonar-project.properties 2>&1 || echo "SonarQube analysis completed"
        
        echo "✓ SonarQube analysis completed"
    outputVariables: []
```

#### Step 3: Add SonarQube Quality Gate Check (Optional - Free and above)

**Purpose:** Verify code meets quality standards before deployment

**Pipeline Configuration:**
```yaml
- step:
    type: Run
    name: SonarQube_Quality_Gate_Check
    identifier: SonarqubeQualityGateCheck
    when:
      stageStatus: Success
    spec:
      shell: Sh
      command: |
        echo "Checking SonarQube Quality Gate..."
        
        SONAR_URL="<+pipeline.variables.sonarqubeUrl>"
        PROJECT_KEY="quantnik-<+matrix.repo.repoName>"
        TOKEN="<+secrets.getValue("sonarcloudToken")>"
        
        # Wait for analysis to complete (max 2 minutes)
        for i in {1..12}; do
          GATE_STATUS=$(curl -s -u "$TOKEN": "$SONAR_URL/api/qualitygates/project_status?projectKey=$PROJECT_KEY" | jq -r '.projectStatus.status' 2>/dev/null)
          
          if [ "$GATE_STATUS" != "null" ]; then
            echo "Quality Gate Status: $GATE_STATUS"
            if [ "$GATE_STATUS" == "OK" ]; then
              echo "✓ Quality Gate PASSED"
              exit 0
            else
              echo "✗ Quality Gate FAILED"
              curl -s -u "$TOKEN": "$SONAR_URL/api/qualitygates/project_status?projectKey=$PROJECT_KEY" | jq '.projectStatus.conditions[]? | "\(.metricKey): \(.status)"'
              exit 1
            fi
          fi
          
          echo "Waiting for analysis completion... ($i/12)"
          sleep 10
        done
        
        echo "⚠️  Analysis did not complete within timeout"
    outputVariables: []
```

#### Step 5: Add Display SonarQube Results Step

**Pipeline Configuration:**
```yaml
- step:
    type: Run
    name: DisplaySonarQubeResults
    identifier: DisplaySonarqubeResults
    when:
      stageStatus: Success
    spec:
      shell: Sh
      command: |
        echo "========================================"
        echo "=== SONARQUBE CODE QUALITY RESULTS ==="
        echo "========================================"
        
        SONAR_URL="<+pipeline.variables.sonarqubeUrl>"
        PROJECT_KEY="quantnik-<+matrix.repo.repoName>"
        TOKEN="<+secrets.getValue("sonarcloudToken")>"
        
        echo ""
        echo "Project: $PROJECT_KEY"
        echo "Fetching metrics from SonarQube..."
        
        # Fetch project metrics
        METRICS=$(curl -s -u "$TOKEN": "$SONAR_URL/api/measures/component?component=$PROJECT_KEY&metricKeys=sqale_rating,reliability_rating,security_rating,coverage,duplicated_lines_density" | jq '.component.measures')
        
        echo "Code Quality Metrics:"
        echo "$METRICS" | jq -r '.[] | "\(.metric): \(.value)"' || echo "Unable to fetch metrics"
        
        echo ""
        echo "Dashboard: $SONAR_URL/dashboard?id=$PROJECT_KEY"
        echo ""
        echo "========================================"
    outputVariables: []
```

#### Step 6: Update Artifacts Configuration

```yaml
artifacts:
  - type: BuildContext
    name: security-reports
    spec:
      paths:
        - semgrep-report.json
        - trivy-backend-report.json
        - trivy-frontend-report.json
        - snyk-dependency-report.json
        - snyk-backend-container-report.json
        - snyk-frontend-container-report.json
        - sonar-project.properties  # NEW
```

### 2.4 SonarQube Configuration in Pipeline YAML

Add to pipeline variables:
```yaml
- name: sonarqubeUrl
  type: String
  value: <+input>.default(https://sonarcloud.io).allowedValues(https://sonarcloud.io,https://<your-sonarqube-url>)
- name: sonarcloudToken
  type: Secret
  value: <+secrets.getValue("sonarcloudToken")>
- name: sonarqubeConnectorRef
  type: String
  value: <+input>.default(sonarcloud-connector)
```

### 2.5 Advantages & Considerations

**Advantages:**
- ✅ Comprehensive code quality metrics (maintainability, complexity, duplication)
- ✅ Security hotspot detection (different from traditional SAST)
- ✅ Long-term trend tracking and historical data
- ✅ Can fail builds based on quality gates
- ✅ PR decoration for GitHub/GitLab
- ✅ Multi-language support

**Considerations:**
- ⚠️ Requires instance setup (SonarCloud or self-hosted)
- ⚠️ Additional cost for SonarQuube Server/Data Center (self-hosted enterprise)
- ⚠️ Analysis can be slower than Semgrep for large codebases
- ⚠️ Quality gates need configuration per project
- ⚠️ Network dependency on SonarQube servers
- ⚠️ Project structure must match SonarQube project keys

### 2.6 SonarQube Cost Comparison

| Tier | Cost | Projects | Support | Deployment |
|------|------|----------|---------|-----------|
| Community | Free | Unlimited | Community | Self-hosted |
| Developer | $29/mo | Unlimited | Email | SonarCloud |
| Business | $529/mo | Unlimited | Priority | SonarCloud |
| Enterprise | Contact | Unlimited | 24/7 Dedicated | Self-hosted + SAML |

---

## Part 5: Complete Integration Overview

### 5.1 Full Security Scanning Pipeline Architecture

```
┌─────────────────────────────────────────────┐
│  Source Code Clone (GitClone)               │
└────────────────┬────────────────────────────┘
                 │
    ┌────────────┼────────────┬────────────────┐
    │            │            │                │
    ▼            ▼            ▼                ▼
 SEMGREP    SNYK_DEP     SONARQUBE      (Code Analysis)
 (SAST)      (Deps)     (Quality)
    │            │            │
    └────────────┼────────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │  Build Container Images     │
    │ (Backend & Frontend)        │
    └────────────┬────────────────┘
                 │
      ┌──────────┴──────────┐
      │                     │
      ▼                     ▼
  TRIVY_SCAN         SNYK_CONTAINER
  (Container)        (Container)
      │                     │
      └──────────┬──────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │  Generate Reports & Display │
    │ - Semgrep Results           │
    │ - Trivy Results             │
    │ - SonarQube Quality Gate     │
    │ - Snyk Results              │
    └────────────┬────────────────┘
                 │
                 ▼
    ┌─────────────────────────────┐
    │  Deploy to EKS (if passing) │
    └─────────────────────────────┘
```

### 5.2 Security Tool Comparison

| Tool | Category | Language | Cost | Auth Required |
|------|----------|----------|------|---------------|
| **Semgrep** | SAST | Multi | Free | No |
| **Trivy** | Container | Any | Free | No |
| **Snyk** | Dependency/Container | Multi | Free (limited) | Yes - Token |
| **SonarQube** | Code Quality + Security | Multi | Free (Cloud) | Yes - Token |

### 5.3 Recommended Deployment Phases

**Phase 1 (Current - Already Done):**
- ✅ Semgrep (SAST)
- ✅ Trivy (Container)

**Phase 2 (Recommended - Low Effort):**
- Add Snyk (Dependency + Container)
- Minimal configuration needed
- Uses existing API token auth pattern

**Phase 3 (Optional - Higher Effort):**
- Add SonarQube (Code Quality)
- Requires instance setup
- More comprehensive but slower analysis

---

## Part 6: Implementation Checklist

### Snyk Implementation Checklist
- [ ] Create Snyk account
- [ ] Generate API token
- [ ] Store token in Harness as secret
- [ ] Add Snyk dependency scan step
- [ ] Add Snyk container scan step
- [ ] Add display results step
- [ ] Test with one repository
- [ ] Update all 16 matrix entries
- [ ] Validate artifact capture

### SonarQube Implementation Checklist
- [ ] Choose SonarCloud or self-hosted SonarQube
- [ ] Create account/instance
- [ ] Generate authentication token
- [ ] Create Harness connector
- [ ] Create projects for all 16 repos
- [ ] Add SonarScanner step
- [ ] Add quality gate check step (optional)
- [ ] Add display results step
- [ ] Configure quality gate rules
- [ ] Test with one repository
- [ ] Update all 16 matrix entries

---

## Part 7: Troubleshooting & Known Issues

### Snyk Issues

**Issue: Authentication fails (401 Unauthorized)**
- Solution: Verify token is valid at https://snyk.io
- Check: Token has not expired, is in correct secret name
- Workaround: Use `--insecure` flag if behind proxy

**Issue: Rate limiting on free tier**
- Solution: Implement retry logic with exponential backoff
- Alternative: Upgrade to paid plan, or spread scans over time

**Issue: Container image not found**
- Solution: Ensure image is pushed to ECR before running container scan
- Check: AWS credentials, region, image existence with AWS CLI

### SonarQube Issues

**Issue: Analysis never completes**
- Solution: Check SonarQube instance resources (memory, CPU)
- Increase quality gate check timeout

**Issue: Project key mismatch**
- Solution: Ensure project key in SonarQube matches command parameters
- Format: Use consistent naming: `quantnik-<repo-name>`

**Issue: Quality gate returns null status**
- Solution: Wait longer for analysis to complete (typically 30-60s)
- Check: Project exists in SonarQube, initial scan has run

---

## Part 8: Cost & Resource Estimation

### Snyk
- **Free Tier:** 100 dependency scans/month per organization
- **Free Tier:** Unlimited container image scans
- **Cost Estimate:** Free → $100+/month (if rate limiting becomes issue)
- **Infrastructure:** Minimal (API calls only)

### SonarQube
- **SonarCloud Free:** Public projects, up to 3 private projects
- **SonarCloud Paid:** $10-100/month depending on usage
- **Self-Hosted:** Free (SonarQube Community Edition) → Enterprise pricing
- **Infrastructure:** 2-4GB RAM minimum, ~20GB storage per 1M LOC

### Combined (Both Tools)
- **Estimated Monthly Cost:** $0-200 depending on tier selections
- **Pipeline Runtime Increase:** +2-5 minutes per build
- **Total Artifacts Size:** ~50-100MB per build (if storing all reports)

---

## Part 9: Migration Path from Current Setup

**Current State:**
- Semgrep ✅ Running
- Trivy ✅ Running

**Recommended Sequence:**
1. **Week 1:** Add Snyk (dependency scanning first, test with 2-3 repos)
2. **Week 2:** Add Snyk container scanning (parallel with Trivy)
3. **Week 3-4:** Set up SonarCloud instance, create 16 projects
4. **Week 4-5:** Add SonarQube step to pipeline, test quality gates

**Success Criteria:**
- All tools run without errors
- Reports generate and display correctly
- No significant pipeline slowdown (<10 minutes total)
- Quality gates configured and enforced

---

## Part 10: References & Documentation

### Official Documentation
- **Snyk CLI:** https://docs.snyk.io/cli-tools/install-the-snyk-cli
- **SonarQube:** https://docs.sonarqube.org/
- **SonarCloud:** https://docs.sonarcloud.io/
- **Harness SonarQube Integration:** https://docs.harness.io/article/8j3vu6yre7-sonarqube-step

### Helpful Resources
- Snyk API Reference: https://snyk.docs.apiary.io/
- SonarQube Web API: https://docs.sonarqube.org/latest/api/overview/
- Quality Gate Configuration: https://docs.sonarqube.org/latest/user-guide/quality-gates/

---

**Document Version:** 1.0  
**Last Updated:** March 16, 2026  
**Status:** Ready for Implementation Review
