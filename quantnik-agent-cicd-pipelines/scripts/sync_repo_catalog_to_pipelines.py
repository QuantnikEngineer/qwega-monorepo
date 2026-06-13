"""
Sync repos catalog into orchestrator pipelines and worker matrices.

Updates:
- QUANTNIK10 orchestrator (quantnikVersion 1.0 repos)
- QUANTNIK30 orchestrator (quantnikVersion 3.0 repos)
- Worker pipelines: CloudRun, ACA, ECS
- All deploy stages: Deploy_Dev, Deploy_QA, Deploy_Staging, Deploy_Production
- Branch variables for each repo
- Branch mapping in Resolve_Branch_For_Repo step
"""

import argparse
import copy
import re
from pathlib import Path


def require_yaml_module():
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency 'pyyaml'. Install with: pip install pyyaml"
        ) from exc
    return yaml


def load_yaml(file_path: Path, yaml_module):
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as handle:
        return yaml_module.safe_load(handle)


def save_yaml(file_path: Path, content, yaml_module):
    with file_path.open("w", encoding="utf-8", newline="\n") as handle:
        yaml_module.safe_dump(content, handle, sort_keys=False, allow_unicode=True)


def to_string(value) -> str:
    if value is None:
        return ""
    return str(value)


def repo_name_to_variable_name(repo_name: str) -> str:
    """Convert repo name to a valid variable name for branch variables.
    
    Examples:
        QUANTNIK-BRD -> branchQUANTNIKBRD
        Quantnik-Orchestrator-Agent -> branchQuantnikOrchestratorAgent
        QUANTNIK-testcases-to-testdata-Agent -> branchQuantnikTestcasesToTestdataAgent
    """
    # Remove special chars and convert to camelCase
    parts = re.split(r'[-_]+', repo_name)
    camel = parts[0] + ''.join(word.capitalize() for word in parts[1:])
    # Remove any remaining non-alphanumeric
    camel = re.sub(r'[^a-zA-Z0-9]', '', camel)
    return f"branch{camel}"


def repo_name_to_case_key(repo_name: str) -> str:
    """Convert repo name to lowercase key used in shell case statement."""
    return repo_name.lower().replace('_', '_')


def build_entries_by_version_and_target(repos: list[dict]) -> dict:
    """
    Build matrix entries organized by quantnikVersion and deployTarget.
    
    Returns:
        {
            "1.0": {
                "cloudrun": {"build": [...], "deploy": [...]},
                "aca": {"build": [...], "deploy": [...]},
                "ecs": {"build": [...], "deploy": [...]}
            },
            "3.0": { ... },
            "repo_names": {"1.0": [...], "3.0": [...]},
            "all_repos": [{"repoName": ..., "branch": ..., "quantnikVersion": ..., "variableName": ...}, ...]
        }
    """
    result = {
        "1.0": {
            "cloudrun": {"build": [], "deploy": []},
            "aca": {"build": [], "deploy": []},
            "ecs": {"build": [], "deploy": []},
        },
        "3.0": {
            "cloudrun": {"build": [], "deploy": []},
            "aca": {"build": [], "deploy": []},
            "ecs": {"build": [], "deploy": []},
        },
        "repo_names": {"1.0": [], "3.0": []},
        "all_repos": [],
    }

    for repo in repos:
        repo_name = to_string(repo.get("repoName")).strip()
        if not repo_name:
            continue

        quantnik_version = to_string(repo.get("quantnikVersion") or "1.0")
        if quantnik_version not in ["1.0", "3.0"]:
            quantnik_version = "1.0"

        deploy_target = to_string(repo.get("deployTarget") or "cloudrun").lower()
        if deploy_target not in ["cloudrun", "aca", "ecs"]:
            deploy_target = "cloudrun"

        branch = to_string(repo.get("branch") or "main")
        variable_name = repo_name_to_variable_name(repo_name)

        result["repo_names"][quantnik_version].append(repo_name)
        result["all_repos"].append({
            "repoName": repo_name,
            "branch": branch,
            "quantnikVersion": quantnik_version,
            "deployTarget": deploy_target,
            "variableName": variable_name,
            "caseKey": repo_name_to_case_key(repo_name),
        })

        backend = repo.get("backend") or {}
        frontend = repo.get("frontend") or {}

        # Common build entry fields
        build_entry = {
            "repoName": repo_name,
            "backendImage": to_string(backend.get("imageName")),
            "backendDockerfile": to_string(backend.get("dockerfile")),
            "backendContext": to_string(backend.get("context")),
            "frontendImage": to_string(frontend.get("imageName")),
            "frontendDockerfile": to_string(frontend.get("dockerfile")),
            "frontendContext": to_string(frontend.get("context")),
        }

        # For CloudRun entries
        cloudrun_build_entry = copy.deepcopy(build_entry)
        cloudrun_build_entry["cloudRunServiceBackend"] = to_string(backend.get("cloudRunService"))
        cloudrun_build_entry["cloudRunServiceFrontend"] = to_string(frontend.get("cloudRunService"))
        
        cloudrun_deploy_entry = {
            "repoName": repo_name,
            "backendImage": to_string(backend.get("imageName")),
            "frontendImage": to_string(frontend.get("imageName")),
            "cloudRunServiceBackend": to_string(backend.get("cloudRunService")),
            "cloudRunServiceFrontend": to_string(frontend.get("cloudRunService")),
        }

        # For ACA entries - use acaServiceName if provided (for short names), else derive from image
        aca_service_name = to_string(repo.get("acaServiceName"))
        if aca_service_name:
            # Use the provided short service name for ACA
            aca_backend_service = aca_service_name if backend.get("imageName") else ""
            aca_frontend_service = aca_service_name if frontend.get("imageName") else ""
        else:
            # Fallback: derive from image name
            aca_backend_service = to_string(backend.get("imageName")).replace("-backend", "") if backend.get("imageName") else ""
            aca_frontend_service = to_string(frontend.get("imageName")).replace("-frontend", "") if frontend.get("imageName") else ""
        aca_build_entry = copy.deepcopy(build_entry)
        aca_build_entry["acaServiceBackend"] = aca_backend_service
        aca_build_entry["acaServiceFrontend"] = aca_frontend_service
        
        aca_deploy_entry = {
            "repoName": repo_name,
            "backendImage": to_string(backend.get("imageName")),
            "frontendImage": to_string(frontend.get("imageName")),
            "acaServiceBackend": aca_backend_service,
            "acaServiceFrontend": aca_frontend_service,
        }

        # For ECS entries - use ecsServiceName if provided, else use repo name
        ecs_service_name = to_string(repo.get("ecsServiceName"))
        if not ecs_service_name:
            ecs_service_name = repo_name
        ecs_build_entry = copy.deepcopy(build_entry)
        ecs_build_entry["ecsServiceBackend"] = ecs_service_name if backend.get("imageName") else ""
        ecs_build_entry["ecsServiceFrontend"] = ecs_service_name if frontend.get("imageName") else ""
        
        ecs_deploy_entry = {
            "repoName": repo_name,
            "backendImage": to_string(backend.get("imageName")),
            "frontendImage": to_string(frontend.get("imageName")),
            "ecsServiceBackend": ecs_service_name if backend.get("imageName") else "",
            "ecsServiceFrontend": ecs_service_name if frontend.get("imageName") else "",
        }

        # Add repos to pipelines based on version
        # QUANTNIK 3.0 repos go to CloudRun, ACA, and ECS (same repos, different deploy targets)
        # QUANTNIK 1.0 repos use deployTarget to route to specific platforms
        if quantnik_version == "3.0":
            # All QUANTNIK 3.0 repos go to CloudRun, ACA, and ECS
            result[quantnik_version]["cloudrun"]["build"].append(cloudrun_build_entry)
            result[quantnik_version]["cloudrun"]["deploy"].append(cloudrun_deploy_entry)
            result[quantnik_version]["aca"]["build"].append(aca_build_entry)
            result[quantnik_version]["aca"]["deploy"].append(aca_deploy_entry)
            result[quantnik_version]["ecs"]["build"].append(ecs_build_entry)
            result[quantnik_version]["ecs"]["deploy"].append(ecs_deploy_entry)
        else:
            # QUANTNIK 1.0 repos - route based on deployTarget
            if deploy_target == "cloudrun":
                result[quantnik_version]["cloudrun"]["build"].append(cloudrun_build_entry)
                result[quantnik_version]["cloudrun"]["deploy"].append(cloudrun_deploy_entry)
            elif deploy_target == "aca":
                result[quantnik_version]["aca"]["build"].append(aca_build_entry)
                result[quantnik_version]["aca"]["deploy"].append(aca_deploy_entry)
            elif deploy_target == "ecs":
                result[quantnik_version]["ecs"]["build"].append(ecs_build_entry)
                result[quantnik_version]["ecs"]["deploy"].append(ecs_deploy_entry)

    return result


def update_orchestrator(orchestrator_yaml: dict, repo_names: list[str], all_repos: list[dict], quantnik_version: str):
    """Update selectedRepo dropdown and branch variables in orchestrator pipeline."""
    pipeline = orchestrator_yaml.get("pipeline") or {}
    variables = pipeline.get("variables") or []
    
    # Update selectedRepo
    options = ["all", *repo_names]
    select_expr = f"<+input>.selectManyFrom({','.join(options)})"

    for variable in variables:
        if variable.get("name") == "selectedRepo":
            variable["value"] = select_expr
            break

    # Get repos for this version
    version_repos = [r for r in all_repos if r["quantnikVersion"] == quantnik_version]
    valid_branch_vars = {repo["variableName"] for repo in version_repos}
    
    # Remove old branch variables not in catalog, keep non-branch variables
    new_variables = []
    for var in variables:
        var_name = var.get("name", "")
        if var_name.startswith("branch"):
            if var_name in valid_branch_vars:
                new_variables.append(var)
            # else: skip/remove this old branch variable
        else:
            new_variables.append(var)
    
    # Add missing branch variables
    existing_branch_vars = {v.get("name") for v in new_variables if v.get("name", "").startswith("branch")}
    for repo in version_repos:
        var_name = repo["variableName"]
        if var_name not in existing_branch_vars:
            new_variables.append({
                "name": var_name,
                "type": "String",
                "value": f"<+input>.default({repo['branch']})"
            })
    
    pipeline["variables"] = new_variables
    
    # Update stage inputs - replace branch variables completely
    stages = pipeline.get("stages") or []
    for stage_wrapper in stages:
        stage = stage_wrapper.get("stage") or {}
        spec = stage.get("spec") or {}
        inputs = spec.get("inputs") or {}
        input_vars = inputs.get("variables") or []
        
        # Keep non-branch input vars, replace branch vars
        new_input_vars = [v for v in input_vars if not v.get("name", "").startswith("branch")]
        
        for repo in version_repos:
            var_name = repo["variableName"]
            new_input_vars.append({
                "name": var_name,
                "type": "String",
                "value": f"<+pipeline.variables.{var_name}>"
            })
        
        if new_input_vars:
            inputs["variables"] = new_input_vars
            spec["inputs"] = inputs
            stage["spec"] = spec


def update_worker_branch_variables(worker_yaml: dict, all_repos: list[dict]):
    """Replace branch variables in worker pipeline with only repos from catalog."""
    pipeline = worker_yaml.get("pipeline") or {}
    variables = pipeline.get("variables") or []
    
    valid_branch_vars = {repo["variableName"] for repo in all_repos}
    
    # Remove old branch variables not in catalog, keep non-branch variables
    new_variables = []
    for var in variables:
        var_name = var.get("name", "")
        if var_name.startswith("branch"):
            if var_name in valid_branch_vars:
                new_variables.append(var)
            # else: skip/remove this old branch variable
        else:
            new_variables.append(var)
    
    # Add missing branch variables
    existing_branch_vars = {v.get("name") for v in new_variables if v.get("name", "").startswith("branch")}
    for repo in all_repos:
        var_name = repo["variableName"]
        if var_name not in existing_branch_vars:
            new_variables.append({
                "name": var_name,
                "type": "String",
                "value": "<+input>"
            })
    
    pipeline["variables"] = new_variables


def update_worker_branch_mapping(worker_yaml: dict, all_repos: list[dict]):
    """Update the Resolve_Branch_For_Repo step with branch mapping for all repos."""
    pipeline = worker_yaml.get("pipeline") or {}
    stages = pipeline.get("stages") or []
    
    # Build the case statement entries
    case_entries = []
    for repo in all_repos:
        case_key = repo["caseKey"]
        var_name = repo["variableName"]
        case_entries.append(f'  "{case_key}") SELECTED_BRANCH="<+pipeline.variables.{var_name}>" ;;')
    
    case_block = "\n".join(case_entries)
    
    # Find the build stage and update the Resolve_Branch step
    for stage_wrapper in stages:
        stage = stage_wrapper.get("stage") or {}
        spec = stage.get("spec") or {}
        execution = spec.get("execution") or {}
        steps = execution.get("steps") or []
        
        for step_wrapper in steps:
            step = step_wrapper.get("step") or {}
            if step.get("identifier") == "ResolveBranch":
                step_spec = step.get("spec") or {}
                
                # Build the complete shell script
                script = f'''SELECTED_BRANCH=""
REPO_NAME_RAW="<+matrix.repo.repoName>"
REPO_NAME=$(printf '%s' "$REPO_NAME_RAW" | tr '[:upper:]' '[:lower:]' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

case "$REPO_NAME" in
{case_block}
  *) echo "No branch mapping found for repo: '$REPO_NAME_RAW'"; exit 1 ;;
esac

if [ -z "$SELECTED_BRANCH" ]; then
  echo "Branch value is empty for repo: <+matrix.repo.repoName>."
  exit 1
fi

echo "Resolved branch for <+matrix.repo.repoName>: $SELECTED_BRANCH"
export selectedBranch="$SELECTED_BRANCH"

OUTPUT_FILE="${{HARNESS_OUTPUT_PATH:-${{HARNESS_ENV_EXPORT_PATH:-}}}}"
if [ -n "$OUTPUT_FILE" ]; then
  echo "selectedBranch=$SELECTED_BRANCH" >> "$OUTPUT_FILE"
fi
'''
                step_spec["command"] = script
                step["spec"] = step_spec


def update_worker_cloudrun(worker_yaml: dict, entries: dict, all_repos: list[dict]):
    """Update CloudRun worker pipeline with build and all deploy stage matrices."""
    pipeline = worker_yaml.get("pipeline") or {}
    stages = pipeline.get("stages") or []

    build_entries = entries.get("build", [])
    deploy_entries = entries.get("deploy", [])

    # Update branch variables
    update_worker_branch_variables(worker_yaml, all_repos)
    
    # Update branch mapping
    update_worker_branch_mapping(worker_yaml, all_repos)

    if not build_entries and not deploy_entries:
        return

    for stage_wrapper in stages:
        stage = stage_wrapper.get("stage") or {}
        identifier = stage.get("identifier")
        strategy = stage.get("strategy") or {}
        matrix = strategy.get("matrix") or {}

        if identifier == "Build_Repo_GAR" and build_entries:
            matrix["repo"] = copy.deepcopy(build_entries)
            strategy["matrix"] = matrix
            stage["strategy"] = strategy
        elif identifier in ["Deploy_Dev", "Deploy_QA", "Deploy_Stage", "Deploy_Production"] and deploy_entries:
            matrix["repo"] = copy.deepcopy(deploy_entries)
            strategy["matrix"] = matrix
            stage["strategy"] = strategy


def update_worker_ecs(worker_yaml: dict, entries: dict, all_repos: list[dict]):
    """Update ECS worker pipeline with build and all deploy stage matrices."""
    pipeline = worker_yaml.get("pipeline") or {}
    stages = pipeline.get("stages") or []

    build_entries = entries.get("build", [])
    deploy_entries = entries.get("deploy", [])

    # Update branch variables
    update_worker_branch_variables(worker_yaml, all_repos)
    
    # Update branch mapping
    update_worker_branch_mapping(worker_yaml, all_repos)

    if not build_entries and not deploy_entries:
        return

    for stage_wrapper in stages:
        stage = stage_wrapper.get("stage") or {}
        identifier = stage.get("identifier")
        strategy = stage.get("strategy") or {}
        matrix = strategy.get("matrix") or {}

        if identifier == "Build_Repo_ECR" and build_entries:
            matrix["repo"] = copy.deepcopy(build_entries)
            strategy["matrix"] = matrix
            stage["strategy"] = strategy
        elif identifier in ["Deploy_Dev", "Deploy_QA", "Deploy_Stage", "Deploy_Production"] and deploy_entries:
            matrix["repo"] = copy.deepcopy(deploy_entries)
            strategy["matrix"] = matrix
            stage["strategy"] = strategy


def update_worker_aca(worker_yaml: dict, entries: dict, all_repos: list[dict]):
    """Update ACA worker pipeline with build and all deploy stage matrices."""
    pipeline = worker_yaml.get("pipeline") or {}
    stages = pipeline.get("stages") or []

    build_entries = entries.get("build", [])
    deploy_entries = entries.get("deploy", [])

    # Update branch variables
    update_worker_branch_variables(worker_yaml, all_repos)
    
    # Update branch mapping
    update_worker_branch_mapping(worker_yaml, all_repos)

    if not build_entries and not deploy_entries:
        return

    for stage_wrapper in stages:
        stage = stage_wrapper.get("stage") or {}
        identifier = stage.get("identifier")
        strategy = stage.get("strategy") or {}
        matrix = strategy.get("matrix") or {}

        if identifier == "Build_Repo_ACR" and build_entries:
            matrix["repo"] = copy.deepcopy(build_entries)
            strategy["matrix"] = matrix
            stage["strategy"] = strategy
        elif identifier in ["Deploy_Dev", "Deploy_QA", "Deploy_Stage", "Deploy_Production"] and deploy_entries:
            matrix["repo"] = copy.deepcopy(deploy_entries)
            strategy["matrix"] = matrix
            stage["strategy"] = strategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync repos catalog into orchestrator and worker pipelines"
    )
    parser.add_argument("--repos", default=".harness/catalog/onboardingrepos.yaml",
                        help="Path to onboardingrepos.yaml")
    parser.add_argument("--quantnik10-orchestrator", default=".harness/pipeline-quantnik10-orchestrator.yaml",
                        help="Path to QUANTNIK 1.0 orchestrator pipeline")
    parser.add_argument("--quantnik30-orchestrator", default=".harness/pipeline-quantnik30-orchestrator.yaml",
                        help="Path to QUANTNIK 3.0 orchestrator pipeline")
    parser.add_argument("--worker-cloudrun", default=".harness/pipeline-repo-worker-build-deploy-cloudrun.yaml",
                        help="Path to CloudRun worker pipeline")
    parser.add_argument("--worker-aca", default=".harness/pipeline-repo-worker-build-deploy-aca.yaml",
                        help="Path to ACA worker pipeline")
    parser.add_argument("--worker-ecs", default=".harness/pipeline-repo-worker-build-deploy-ecs.yaml",
                        help="Path to ECS worker pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be updated without saving")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    yaml_module = require_yaml_module()

    repos_path = Path(args.repos)
    repos_yaml = load_yaml(repos_path, yaml_module) or {}
    repos = repos_yaml.get("repos")
    if not isinstance(repos, list):
        raise SystemExit("onboardingrepos.yaml must contain top-level 'repos' list")

    entries = build_entries_by_version_and_target(repos)
    
    total_repos = len(entries["repo_names"]["1.0"]) + len(entries["repo_names"]["3.0"])
    if total_repos == 0:
        raise SystemExit("No valid repoName entries found in onboardingrepos.yaml")

    print(f"Found {len(entries['repo_names']['1.0'])} QUANTNIK 1.0 repos, {len(entries['repo_names']['3.0'])} QUANTNIK 3.0 repos")
    print(f"Total branch variables to sync: {len(entries['all_repos'])}")

    # Update QUANTNIK 1.0 orchestrator
    quantnik10_path = Path(args.quantnik10_orchestrator)
    if quantnik10_path.exists() and entries["repo_names"]["1.0"]:
        quantnik10_yaml = load_yaml(quantnik10_path, yaml_module)
        update_orchestrator(quantnik10_yaml, entries["repo_names"]["1.0"], entries["all_repos"], "1.0")
        if not args.dry_run:
            save_yaml(quantnik10_path, quantnik10_yaml, yaml_module)
        print(f"QUANTNIK10 orchestrator: {len(entries['repo_names']['1.0'])} repos + branch variables")

    # Update QUANTNIK 3.0 orchestrator
    quantnik30_path = Path(args.quantnik30_orchestrator)
    if quantnik30_path.exists() and entries["repo_names"]["3.0"]:
        quantnik30_yaml = load_yaml(quantnik30_path, yaml_module)
        update_orchestrator(quantnik30_yaml, entries["repo_names"]["3.0"], entries["all_repos"], "3.0")
        if not args.dry_run:
            save_yaml(quantnik30_path, quantnik30_yaml, yaml_module)
        print(f"QUANTNIK30 orchestrator: {len(entries['repo_names']['3.0'])} repos + branch variables")

    # Combine entries from both versions for workers (workers handle all repos)
    all_repos = entries["all_repos"]
    
    combined = {
        "cloudrun": {
            "build": entries["1.0"]["cloudrun"]["build"] + entries["3.0"]["cloudrun"]["build"],
            "deploy": entries["1.0"]["cloudrun"]["deploy"] + entries["3.0"]["cloudrun"]["deploy"],
        },
        "aca": {
            "build": entries["1.0"]["aca"]["build"] + entries["3.0"]["aca"]["build"],
            "deploy": entries["1.0"]["aca"]["deploy"] + entries["3.0"]["aca"]["deploy"],
        },
        "ecs": {
            "build": entries["1.0"]["ecs"]["build"] + entries["3.0"]["ecs"]["build"],
            "deploy": entries["1.0"]["ecs"]["deploy"] + entries["3.0"]["ecs"]["deploy"],
        },
    }

    # Update CloudRun worker
    cloudrun_path = Path(args.worker_cloudrun)
    if cloudrun_path.exists():
        cloudrun_yaml = load_yaml(cloudrun_path, yaml_module)
        update_worker_cloudrun(cloudrun_yaml, combined["cloudrun"], all_repos)
        if not args.dry_run:
            save_yaml(cloudrun_path, cloudrun_yaml, yaml_module)
        print(f"CloudRun worker: {len(combined['cloudrun']['build'])} build, {len(combined['cloudrun']['deploy'])} deploy, {len(all_repos)} branch vars")

    # Update ACA worker
    aca_path = Path(args.worker_aca)
    if aca_path.exists():
        aca_yaml = load_yaml(aca_path, yaml_module)
        update_worker_aca(aca_yaml, combined["aca"], all_repos)
        if not args.dry_run:
            save_yaml(aca_path, aca_yaml, yaml_module)
        print(f"ACA worker: {len(combined['aca']['build'])} build, {len(combined['aca']['deploy'])} deploy, {len(all_repos)} branch vars")

    # Update ECS worker
    ecs_path = Path(args.worker_ecs)
    if ecs_path.exists():
        ecs_yaml = load_yaml(ecs_path, yaml_module)
        update_worker_ecs(ecs_yaml, combined["ecs"], all_repos)
        if not args.dry_run:
            save_yaml(ecs_path, ecs_yaml, yaml_module)
        print(f"ECS worker: {len(combined['ecs']['build'])} build, {len(combined['ecs']['deploy'])} deploy, {len(all_repos)} branch vars")

    if args.dry_run:
        print("DRY RUN: No files were modified")
    else:
        print(f"Synced {total_repos} total repos with branch variables into orchestrators and workers")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
