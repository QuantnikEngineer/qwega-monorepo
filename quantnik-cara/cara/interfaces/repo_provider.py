"""Repository provider protocol.

Both ``GitHubService`` and ``HarnessCodeService`` satisfy this contract so the
review orchestrator can stay provider-agnostic. The ``name`` attribute lets
storage / logging tag artefacts with the originating SCM.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from cara.models.domain import (
    PullRequestContext,
    RepositoryScanContext,
    RepoProviderName,
)


@runtime_checkable
class RepoProvider(Protocol):
    name: RepoProviderName

    def ensure_pull_request_exists(self, owner: str, repo: str, pr_number: int) -> None: ...

    def ensure_repository_exists(self, owner: str, repo: str) -> None: ...

    def get_pull_request_context(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> PullRequestContext: ...

    def get_repository_scan_context(
        self,
        owner: str,
        repo: str,
        ref: str | None = None,
        folder: str | None = None,
    ) -> RepositoryScanContext: ...

    def download_repository_archive(
        self,
        owner: str,
        repo: str,
        ref: str,
        target_dir: Path,
    ) -> Path: ...

    def collect_context_files(
        self,
        repository_root: Path,
        max_files: int,
        max_file_bytes: int,
        folder: str | None = None,
    ) -> list[Path]: ...
