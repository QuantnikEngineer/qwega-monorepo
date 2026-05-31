# Template + Matrix migration guide (No Argo CD)

This guide helps you migrate from many duplicated stages to reusable templates while keeping direct deployment to EKS with `kubectl`.

## What was added

- Repo catalog: [.harness/catalog/onboardingrepos.yaml](../.harness/catalog/onboardingrepos.yaml)
- Build stage template: [.harness/templates/build-and-push-ecr-stage-template.yaml](../.harness/templates/build-and-push-ecr-stage-template.yaml)
- Deploy stage template: [.harness/templates/deploy-to-eks-stage-template.yaml](../.harness/templates/deploy-to-eks-stage-template.yaml)

## Migration steps

1. Keep your existing pipeline as baseline.
2. Register both templates in Harness (Project Templates).
3. Replace one repo pair first (for example: `unit-test-case-agent`) with template-based stages.
4. Validate build-only and build-and-deploy paths.
5. Migrate remaining repos one by one.

## Example: template-based build stage (single repo)

```yaml
- stage:
    name: Build_unit_test_case_agent
    identifier: Build_unit_test_case_agent
    template:
      templateRef: BuildAndPushRepo
      versionLabel: v1
      templateInputs:
        type: CI
        variables:
          - name: repoName
            type: String
            value: unit-test-case-agent
          - name: branch
            type: String
            value: main
          - name: backendImage
            type: String
            value: unit-test-case-agent-backend
          - name: backendDockerfile
            type: String
            value: source/backend/Dockerfile
          - name: backendContext
            type: String
            value: source/backend
          - name: frontendImage
            type: String
            value: unit-test-case-agent-frontend
          - name: frontendDockerfile
            type: String
            value: source/frontend/Dockerfile
          - name: frontendContext
            type: String
            value: source/frontend
```

## Example: template-based deploy stage (single repo)

```yaml
- stage:
    name: Deploy_unit_test_case_agent
    identifier: Deploy_unit_test_case_agent
    when:
      pipelineStatus: Success
      condition: (<+pipeline.variables.selectedRepo> == "all" || <+pipeline.variables.selectedRepo> == "unit-test-case-agent") && <+pipeline.variables.executionMode> == "build_and_deploy"
    template:
      templateRef: DeployRepoToEks
      versionLabel: v1
      templateInputs:
        type: CI
        variables:
          - name: backendDeployment
            type: String
            value: service-unit-test-case-agent-backend
          - name: backendContainer
            type: String
            value: backend
          - name: backendImage
            type: String
            value: unit-test-case-agent-backend
          - name: frontendDeployment
            type: String
            value: service-unit-test-case-agent-frontend
          - name: frontendContainer
            type: String
            value: frontend
          - name: frontendImage
            type: String
            value: unit-test-case-agent-frontend
```

## Notes for your current pipeline

- `buildaicode-wega_rag` uses different paths (`source/Backend`, `source/Frontend`) and different deployment/container names.
- Keep the one-time manifest apply step in a dedicated stage (or a separate bootstrap pipeline) to avoid repeated apply operations.
- Continue using `selectedRepo` and `executionMode` exactly as today.

