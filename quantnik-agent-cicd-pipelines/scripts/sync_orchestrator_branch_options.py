"""
Sync live Git branches into orchestrator pipeline branch variables.

Updates:
- QUANTNIK10 orchestrator (quantnikVersion 1.0 repos)
- QUANTNIK30 orchestrator (quantnikVersion 3.0 repos)

Fetches branches from each repo via `git ls-remote` and updates
the `branch<RepoName>` variables with allowedValues.

Uses regex-based updates to preserve original YAML formatting.

When run with --auto-commit, will commit and push changes automatically.
Designed to run as a scheduled Harness pipeline.

Environment variables:
- SYNC_GIT_USERNAME: Git username for authentication
- SYNC_GIT_PASSWORD: Git token/password for authentication
- GIT_AUTHOR_NAME: Author name for commits (default: CI Pipeline)
- GIT_AUTHOR_EMAIL: Author email for commits (default: ci@harness.io)
"""

import argparse
import os
import re
import subprocess
from urllib.parse import quote
from pathlib import Path
from datetime import datetime


def require_yaml_module():
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit("Missing dependency 'pyyaml'. Install with: pip install pyyaml") from exc
    return yaml


def load_yaml(file_path: Path, yaml_module):
    """Load YAML for parsing repo catalog."""
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as handle:
        return yaml_module.safe_load(handle)


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def get_repos_by_version(catalog_yaml: dict) -> dict[str, list[str]]:
    """Get repo names organized by quantnikVersion."""
    repos = catalog_yaml.get("repos")
    if not isinstance(repos, list):
        raise SystemExit("onboardingrepos.yaml must contain top-level 'repos' list")

    result = {"1.0": [], "3.0": []}
    
    for repo in repos:
        if not isinstance(repo, dict):
            continue
        name = str(repo.get("repoName") or "").strip()
        if not name:
            continue
        
        version = str(repo.get("quantnikVersion") or "1.0")
        if version not in ["1.0", "3.0"]:
            version = "1.0"
        
        result[version].append(name)
    
    return result


def resolve_origin_url() -> str:
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit("Could not resolve git remote.origin.url")

    origin = proc.stdout.strip()
    if not origin:
        raise SystemExit("git remote.origin.url is empty")
    if not origin.endswith(".git"):
        raise SystemExit(f"Unsupported origin URL format: {origin}")
    return origin


def make_repo_remote(origin_url: str, repo_name: str) -> str:
    base = origin_url.rsplit("/", 1)[0]
    return f"{base}/{repo_name}.git"


def add_auth_to_https_url(url: str, username: str | None, password: str | None) -> str:
    if not username or not password:
        return url
    if not url.startswith("https://"):
        return url

    encoded_user = quote(username, safe="")
    encoded_pass = quote(password, safe="")
    return url.replace("https://", f"https://{encoded_user}:{encoded_pass}@", 1)


def fetch_branches(repo_url: str) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-remote", "--heads", repo_url],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "git ls-remote failed")

    branches: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        prefix = "refs/heads/"
        if ref.startswith(prefix):
            branch = ref[len(prefix):].strip()
            if branch:
                branches.append(branch)

    unique: list[str] = []
    seen = set()
    for branch in branches:
        if branch not in seen:
            seen.add(branch)
            unique.append(branch)
    return unique


def preferred_sort(branches: list[str]) -> list[str]:
    preferred = ["main", "master", "develop", "dev", "release"]
    preferred_present = [b for b in preferred if b in branches]
    remaining = sorted([b for b in branches if b not in preferred_present])
    return preferred_present + remaining


def parse_default(expr: str) -> str | None:
    match = re.search(r"\.default\(([^)]+)\)", expr)
    if match:
        return match.group(1)
    return None


def build_expr(default_branch: str, branches: list[str]) -> str:
    return f"<+input>.default({default_branch}).allowedValues({','.join(branches)})"


def update_orchestrator_file(
    file_path: Path,
    repo_names: list[str],
    origin_url: str,
    git_username: str | None,
    git_password: str | None,
) -> tuple[int, list[str], bool]:
    """
    Update branch variables in orchestrator file using regex (preserves formatting).
    Returns (updated_count, notes, file_changed)
    """
    with file_path.open("r", encoding="utf-8") as f:
        content = f.read()
    
    original_content = content
    repo_by_normalized = {normalize_name(repo): repo for repo in repo_names}
    
    updated = 0
    notes: list[str] = []
    
    # Find all branch variables using regex
    # Pattern matches: - name: branchXXX followed by value: <+input>...
    pattern = r'(- name: branch([A-Za-z0-9_]+)\s+type: String\s+value: )(<\+input>[^\n]+)'
    
    def replace_branch_value(match):
        nonlocal updated
        prefix = match.group(1)
        var_suffix = match.group(2)
        current_value = match.group(3)
        
        # Find matching repo
        repo = repo_by_normalized.get(normalize_name(var_suffix))
        if not repo:
            notes.append(f"  SKIP branch{var_suffix}: no repo match in catalog")
            return match.group(0)  # Return unchanged
        
        repo_url = make_repo_remote(origin_url, repo)
        repo_url = add_auth_to_https_url(repo_url, git_username, git_password)
        
        try:
            branches = fetch_branches(repo_url)
        except RuntimeError as exc:
            notes.append(f"  FAIL {repo}: {exc}")
            return match.group(0)
        
        if not branches:
            notes.append(f"  SKIP {repo}: no branches found")
            return match.group(0)
        
        branches = preferred_sort(branches)
        
        # Determine default branch
        current_default = parse_default(current_value)
        if current_default and current_default in branches:
            default_branch = current_default
        elif "main" in branches:
            default_branch = "main"
        else:
            default_branch = branches[0]
        
        new_value = build_expr(default_branch, branches)
        
        if new_value != current_value:
            updated += 1
            notes.append(f"  UPDATE {repo}: {len(branches)} branches (default: {default_branch})")
            return prefix + new_value
        else:
            notes.append(f"  UNCHANGED {repo}")
            return match.group(0)
    
    content = re.sub(pattern, replace_branch_value, content)
    
    file_changed = content != original_content
    if file_changed:
        with file_path.open("w", encoding="utf-8") as f:
            f.write(content)
    
    return updated, notes, file_changed


def run_git_command(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    proc = subprocess.run(
        ["git"] + args,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        error_msg = proc.stderr.strip() or proc.stdout.strip() or "Command failed"
        raise RuntimeError(f"git {' '.join(args)} failed: {error_msg}")
    return proc


def has_changes() -> bool:
    """Check if there are any uncommitted changes."""
    proc = run_git_command(["status", "--porcelain"], check=False)
    return bool(proc.stdout.strip())


def commit_and_push(
    files: list[str],
    commit_message: str,
    git_username: str | None,
    git_password: str | None,
) -> bool:
    """Stage, commit, and push changes. Returns True if changes were pushed."""
    if not has_changes():
        print("No changes to commit")
        return False

    # Configure git author
    author_name = os.getenv("GIT_AUTHOR_NAME", "CI Pipeline")
    author_email = os.getenv("GIT_AUTHOR_EMAIL", "ci@harness.io")
    
    run_git_command(["config", "user.name", author_name])
    run_git_command(["config", "user.email", author_email])

    # Stage files
    for file in files:
        run_git_command(["add", file])

    # Check if there are staged changes
    proc = run_git_command(["diff", "--cached", "--quiet"], check=False)
    if proc.returncode == 0:
        print("No staged changes to commit")
        return False

    # Commit
    run_git_command(["commit", "-m", commit_message])
    print(f"Committed: {commit_message}")

    # Push with authentication if provided
    origin_url = resolve_origin_url()
    if git_username and git_password:
        push_url = add_auth_to_https_url(origin_url, git_username, git_password)
        run_git_command(["push", push_url, "HEAD"])
    else:
        run_git_command(["push"])
    
    print("Pushed changes to remote")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync live Git branches into orchestrator branch variables"
    )
    parser.add_argument("--catalog", default=".harness/catalog/onboardingrepos.yaml",
                        help="Path to onboardingrepos.yaml")
    parser.add_argument("--quantnik10-orchestrator", default=".harness/pipeline-quantnik10-orchestrator.yaml",
                        help="Path to QUANTNIK 1.0 orchestrator pipeline")
    parser.add_argument("--quantnik30-orchestrator", default=".harness/pipeline-quantnik30-orchestrator.yaml",
                        help="Path to QUANTNIK 3.0 orchestrator pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be updated without saving")
    parser.add_argument("--auto-commit", action="store_true",
                        help="Automatically commit and push changes (for CI/CD pipelines)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    yaml_module = require_yaml_module()

    catalog_path = Path(args.catalog)
    catalog_yaml = load_yaml(catalog_path, yaml_module)

    repos_by_version = get_repos_by_version(catalog_yaml)
    
    total_repos = len(repos_by_version["1.0"]) + len(repos_by_version["3.0"])
    if total_repos == 0:
        raise SystemExit("No repo names found in catalog")

    origin_url = resolve_origin_url()
    git_username = os.getenv("SYNC_GIT_USERNAME")
    git_password = os.getenv("SYNC_GIT_PASSWORD")

    if git_username and git_password:
        print("Using SYNC_GIT_USERNAME/SYNC_GIT_PASSWORD for authentication")
    else:
        print("No auth credentials provided (set SYNC_GIT_USERNAME and SYNC_GIT_PASSWORD for private repos)")

    total_updated = 0
    modified_files: list[str] = []

    # Update QUANTNIK 1.0 orchestrator
    quantnik10_path = Path(args.quantnik10_orchestrator)
    if quantnik10_path.exists() and repos_by_version["1.0"]:
        print(f"\nProcessing QUANTNIK 1.0 orchestrator ({len(repos_by_version['1.0'])} repos)...")
        
        if args.dry_run:
            # For dry-run, still process but don't save (use temp copy)
            import tempfile
            import shutil
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
                tmp_path = Path(tmp.name)
            shutil.copy(quantnik10_path, tmp_path)
            updated, notes, _ = update_orchestrator_file(
                tmp_path, repos_by_version["1.0"], origin_url, git_username, git_password
            )
            tmp_path.unlink()
        else:
            updated, notes, changed = update_orchestrator_file(
                quantnik10_path, repos_by_version["1.0"], origin_url, git_username, git_password
            )
            if changed:
                modified_files.append(str(quantnik10_path))
        
        for note in notes:
            print(note)
        print(f"QUANTNIK10: {updated} branch variables updated")
        total_updated += updated

    # Update QUANTNIK 3.0 orchestrator
    quantnik30_path = Path(args.quantnik30_orchestrator)
    if quantnik30_path.exists() and repos_by_version["3.0"]:
        print(f"\nProcessing QUANTNIK 3.0 orchestrator ({len(repos_by_version['3.0'])} repos)...")
        
        if args.dry_run:
            import tempfile
            import shutil
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as tmp:
                tmp_path = Path(tmp.name)
            shutil.copy(quantnik30_path, tmp_path)
            updated, notes, _ = update_orchestrator_file(
                tmp_path, repos_by_version["3.0"], origin_url, git_username, git_password
            )
            tmp_path.unlink()
        else:
            updated, notes, changed = update_orchestrator_file(
                quantnik30_path, repos_by_version["3.0"], origin_url, git_username, git_password
            )
            if changed:
                modified_files.append(str(quantnik30_path))
        
        for note in notes:
            print(note)
        print(f"QUANTNIK30: {updated} branch variables updated")
        total_updated += updated

    print(f"\n{'DRY RUN: ' if args.dry_run else ''}Total: {total_updated} branch variables updated")

    # Auto-commit and push if requested
    if args.auto_commit and not args.dry_run and modified_files:
        print("\n--- Auto-commit enabled ---")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_message = f"[CI] Sync branch options from live repos ({timestamp})\n\nUpdated {total_updated} branch variables across orchestrators."
        try:
            pushed = commit_and_push(modified_files, commit_message, git_username, git_password)
            if pushed:
                print("Changes committed and pushed successfully")
            else:
                print("No changes to push")
        except RuntimeError as exc:
            print(f"ERROR: Failed to commit/push: {exc}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
