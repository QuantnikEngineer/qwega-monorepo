import hashlib
import hmac
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cara.core.config import Settings
from cara.core.errors import AuthenticationError, ExternalServiceError, NotFoundError
from cara.models.domain import (
    PullRequestContext,
    PullRequestFileChange,
    RepositoryScanContext,
    RepoProviderName,
)
from cara.services.git_clone import clone_repository

EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}
EXCLUDED_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".jar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".pyc",
    ".pyo",
    ".class",
}

# Positive allowlist of source / config / docs extensions. Files with any of
# these extensions are accepted into the context without paying the per-file
# binary-sniff cost in `_is_text_file`. Anything outside the list still falls
# through to the sniff so we don't silently drop legitimate text formats.
TEXT_EXTENSIONS = {
    ".py", ".pyi", ".pyw",
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".kts", ".scala",
    ".rb", ".php", ".cs", ".cpp", ".cc", ".cxx",
    ".c", ".h", ".hpp", ".hh", ".swift", ".m", ".mm",
    ".sh", ".bash", ".zsh", ".ps1", ".lua",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".md", ".rst", ".txt", ".html", ".htm", ".css", ".scss", ".sass",
    ".xml", ".sql", ".tf", ".graphql", ".proto",
    ".env",
}

# Files without an extension (or with an unusual one) that we still want to
# treat as text — e.g. `Dockerfile`, `Makefile`. Match is case-insensitive.
KNOWN_TEXT_FILENAMES = {
    "dockerfile",
    "makefile",
    "license",
    "readme",
    "changelog",
    "notice",
    "authors",
    "contributors",
}

# Lower number = higher priority when truncating to MAX_CONTEXT_FILES.
# Source code first, then build/config, then web assets, then docs/data.
_EXTENSION_PRIORITY: dict[str, int] = {
    # source code
    ".py": 0, ".pyi": 0,
    ".ts": 0, ".tsx": 0, ".js": 0, ".jsx": 0, ".mjs": 0, ".cjs": 0,
    ".go": 0, ".rs": 0, ".java": 0, ".kt": 0, ".kts": 0, ".scala": 0,
    ".rb": 0, ".php": 0, ".cs": 0, ".cpp": 0, ".cc": 0, ".c": 0, ".h": 0,
    ".hpp": 0, ".hh": 0, ".swift": 0, ".m": 0, ".mm": 0,
    # shell / build scripts
    ".sh": 1, ".bash": 1, ".zsh": 1, ".ps1": 1, ".tf": 1,
    # config / data
    ".json": 2, ".yaml": 2, ".yml": 2, ".toml": 2, ".ini": 2, ".cfg": 2,
    ".conf": 2, ".env": 2, ".sql": 2, ".graphql": 2, ".proto": 2,
    # web assets
    ".html": 3, ".htm": 3, ".css": 3, ".scss": 3, ".sass": 3, ".xml": 3,
    # docs
    ".md": 4, ".rst": 4, ".txt": 4,
}

# Path segments that should de-prioritize a file (tests / fixtures / generated).
_DEPRIORITIZED_PATH_SEGMENTS = {
    "tests",
    "test",
    "__tests__",
    "spec",
    "specs",
    "fixtures",
    "generated",
    "vendor",
    "third_party",
    "third-party",
    "examples",
    "example",
}


def verify_webhook_signature(
    secret: str | None,
    payload: bytes,
    signature_header: str | None,
) -> None:
    if secret is None:
        return

    if signature_header is None:
        raise AuthenticationError("Missing X-Hub-Signature-256 header.")

    expected_signature = f"sha256={hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()}"
    if not hmac.compare_digest(expected_signature, signature_header):
        raise AuthenticationError("Invalid GitHub webhook signature.")


class GitHubService:
    name: RepoProviderName = RepoProviderName.GITHUB

    def __init__(
        self,
        client: Any,
        token_provider: Callable[[], str],
        settings: Settings,
    ) -> None:
        self._client = client
        self._token_provider = token_provider
        self._settings = settings

    def ensure_pull_request_exists(self, owner: str, repo: str, pr_number: int) -> None:
        self._get_pull_request(owner, repo, pr_number)

    def ensure_repository_exists(self, owner: str, repo: str) -> None:
        self._get_repository(owner, repo)

    def get_repository_scan_context(
        self,
        owner: str,
        repo: str,
        ref: str | None = None,
        folder: str | None = None,
    ) -> RepositoryScanContext:
        repository = self._get_repository(owner, repo)
        default_branch = getattr(repository, "default_branch", None)
        effective_ref = ref or default_branch
        if not effective_ref:
            raise ExternalServiceError(
                f"Unable to determine a default branch for {owner}/{repo}.",
            )

        head_sha: str
        try:
            commit = repository.get_commit(effective_ref)
            head_sha = commit.sha
        except Exception as exc:
            self._raise_github_error(
                exc,
                f"Unable to resolve ref {effective_ref!r} in {owner}/{repo}.",
            )

        html_url = getattr(repository, "html_url", None) or (
            f"https://github.com/{owner}/{repo}"
        )
        normalized_folder = self._normalize_folder(folder)

        return RepositoryScanContext(
            owner=owner,
            repo=repo,
            ref=effective_ref,
            folder=normalized_folder,
            head_sha=head_sha,
            html_url=html_url,
            default_branch=default_branch,
        )

    def _normalize_folder(self, folder: str | None) -> str | None:
        if folder is None:
            return None
        cleaned = folder.strip().strip("/")
        return cleaned or None

    def get_pull_request_context(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> PullRequestContext:
        pull_request = self._get_pull_request(owner, repo, pr_number)
        files: list[PullRequestFileChange] = []
        diff_sections: list[str] = []

        for changed_file in pull_request.get_files():
            patch = getattr(changed_file, "patch", None)
            files.append(
                PullRequestFileChange(
                    filename=changed_file.filename,
                    status=changed_file.status,
                    additions=changed_file.additions,
                    deletions=changed_file.deletions,
                    patch=patch,
                ),
            )
            diff_body = patch or "Patch omitted by GitHub because the file is binary or too large."
            diff_sections.append(
                "\n".join(
                    [
                        f"diff --git a/{changed_file.filename} b/{changed_file.filename}",
                        f"change-type: {changed_file.status}",
                        diff_body,
                    ],
                ),
            )

        return PullRequestContext(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            title=pull_request.title,
            body=pull_request.body,
            html_url=pull_request.html_url,
            head_sha=pull_request.head.sha,
            head_ref=pull_request.head.ref,
            base_ref=pull_request.base.ref,
            diff="\n\n".join(diff_sections),
            files=files,
        )

    def download_repository_archive(
        self,
        owner: str,
        repo: str,
        ref: str,
        target_dir: Path,
    ) -> Path:
        clone_url = f"https://github.com/{owner}/{repo}.git"
        return clone_repository(
            clone_url=clone_url,
            ref=ref,
            target_dir=target_dir,
            username="x-access-token",
            password=self._token_provider(),
            timeout_seconds=self._settings.repository_archive_timeout_seconds,
        )

    def collect_context_files(
        self,
        repository_root: Path,
        max_files: int,
        max_file_bytes: int,
        folder: str | None = None,
    ) -> list[Path]:
        scan_root = repository_root
        if folder:
            scan_root = repository_root / folder
            if not scan_root.exists() or not scan_root.is_dir():
                raise NotFoundError(
                    f"Folder {folder!r} was not found in the repository archive.",
                )

        candidates: list[Path] = []
        # `os.walk(topdown=True)` honours in-place mutations of ``dirnames`` so
        # we never descend into excluded directories. This is dramatically
        # faster than ``rglob`` + post-filter for monorepos with `node_modules`,
        # `.git`, `__pycache__`, etc.
        for dirpath, dirnames, filenames in os.walk(scan_root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRECTORIES]
            for name in filenames:
                if name.endswith(".lock"):
                    continue
                path = Path(dirpath, name)
                suffix = path.suffix.lower()
                if suffix in EXCLUDED_SUFFIXES:
                    continue

                # Cheap fast path: known-text extensions skip the binary sniff.
                # Files with no extension (Dockerfile, Makefile, ...) are
                # accepted by name. Everything else falls through to the
                # 2 KB sniff so legitimate text formats are not silently dropped.
                name_lower = name.lower()
                if (
                    suffix in TEXT_EXTENSIONS
                    or name_lower in KNOWN_TEXT_FILENAMES
                    or self._is_text_file(path)
                ):
                    try:
                        if path.stat().st_size > max_file_bytes:
                            continue
                    except OSError:
                        continue
                    candidates.append(path)

        if len(candidates) <= max_files:
            candidates.sort(key=self._priority_key)
            return candidates

        candidates.sort(key=self._priority_key)
        return candidates[:max_files]

    def _priority_key(self, path: Path) -> tuple[int, int, str]:
        """Sort key used to rank candidate files when truncating to MAX_CONTEXT_FILES.

        Lower tuples sort first; the overall ordering is:
        1. base priority by extension (source > config > docs)
        2. de-prioritize files under tests / fixtures / generated paths
        3. smaller files first within the same priority bucket
        4. lexicographic fallback for stable ordering
        """
        suffix = path.suffix.lower()
        base = _EXTENSION_PRIORITY.get(suffix, 5)
        parts_lower = {p.lower() for p in path.parts}
        test_demote = 1 if parts_lower & _DEPRIORITIZED_PATH_SEGMENTS else 0
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        return (base + test_demote, size, str(path))

    def _get_repository(self, owner: str, repo: str) -> Any:
        try:
            return self._client.get_repo(f"{owner}/{repo}")
        except Exception as exc:
            self._raise_github_error(exc, f"Unable to access repository {owner}/{repo}.")

    def _get_pull_request(self, owner: str, repo: str, pr_number: int) -> Any:
        repository = self._get_repository(owner, repo)
        try:
            return repository.get_pull(pr_number)
        except Exception as exc:
            self._raise_github_error(
                exc,
                f"Unable to access pull request #{pr_number} in {owner}/{repo}.",
            )

    def _is_text_file(self, path: Path) -> bool:
        try:
            with path.open("rb") as handle:
                sample = handle.read(2048)
        except OSError:
            return False

        if b"\x00" in sample:
            return False

        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            return False

        return True

    def _raise_github_error(self, exc: Exception, default_message: str) -> None:
        try:
            from github import GithubException, UnknownObjectException
        except ImportError:
            raise ExternalServiceError(default_message) from exc

        if isinstance(exc, UnknownObjectException):
            raise NotFoundError(default_message) from exc
        if isinstance(exc, GithubException):
            raise ExternalServiceError(default_message) from exc
        raise ExternalServiceError(default_message) from exc
