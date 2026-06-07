"""Harness Code Repository provider.

Implements ``RepoProvider`` against Harness Code's REST API
(https://app.harness.io/gateway/code/api/v1/...). The repo identifier is the
URL-encoded triple ``{accountId}/{orgId}/{projectId}/{repoIdentifier}``; the
caller supplies it as the existing ``owner/repo`` pair where ``owner`` is the
``orgId/projectId`` slug and ``repo`` is the ``repoIdentifier``.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

from cara.core.config import Settings
from cara.core.errors import (
    AuthenticationError,
    ConfigurationError,
    ExternalServiceError,
    NotFoundError,
)
from cara.models.domain import (
    PullRequestContext,
    PullRequestFileChange,
    RepositoryScanContext,
    RepoProviderName,
)
from cara.services.git_clone import clone_repository

logger = logging.getLogger(__name__)


_OWNER_SPLITTER = re.compile(r"[/]+")


def _split_owner(owner: str) -> tuple[str, str]:
    """Split an owner string of the form ``orgId/projectId`` into its parts.

    Harness Code identifies repos by ``{org}/{project}/{repo}``. CARA's
    existing model only carries ``owner`` and ``repo`` so we pack
    ``org/project`` into ``owner`` and split here.
    """
    parts = [p for p in _OWNER_SPLITTER.split(owner) if p]
    if len(parts) != 2:
        raise ExternalServiceError(
            f"Harness owner must be 'orgId/projectId' (got {owner!r}).",
        )
    return parts[0], parts[1]


def verify_webhook_signature(
    secret: str | None,
    payload: bytes,
    signature_header: str | None,
) -> None:
    """Validate Harness Code webhook HMAC.

    Harness sends ``X-Harness-Signature: <sha256-hex>`` (no ``sha256=`` prefix
    in current docs). We accept both forms for forward-compatibility.
    """
    if secret is None:
        return

    if signature_header is None:
        raise AuthenticationError("Missing X-Harness-Signature header.")

    received = signature_header.split("=", 1)[-1].strip()
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthenticationError("Invalid Harness webhook signature.")


class HarnessCodeService:
    name: RepoProviderName = RepoProviderName.HARNESS

    def __init__(
        self,
        client: Any,
        token_provider: Callable[[], str],
        settings: Settings,
    ) -> None:
        self._client = client
        self._token_provider = token_provider
        self._settings = settings

    # ------------------------------------------------------------------
    # Repo identifier helpers
    # ------------------------------------------------------------------

    def _repo_ref(self, owner: str, repo: str) -> str:
        org, project = _split_owner(owner)
        account = self._settings.harness_account_id
        if not account:
            raise ConfigurationError(
                "HARNESS_ACCOUNT_ID is not configured; "
                "Harness Code requires the account identifier in the repo path.",
            )
        return (
            f"{quote(account, safe='')}/{quote(org, safe='')}/"
            f"{quote(project, safe='')}/{quote(repo, safe='')}/+"
        )

    def _api_url(self, suffix: str) -> str:
        return f"/gateway/code/api/v1/{suffix.lstrip('/')}"

    # ------------------------------------------------------------------
    # Existence checks
    # ------------------------------------------------------------------

    def ensure_pull_request_exists(self, owner: str, repo: str, pr_number: int) -> None:
        repo_ref = self._repo_ref(owner, repo)
        url = self._api_url(f"repos/{repo_ref}/pullreq/{pr_number}")
        response = self._client.get(url, params=self._account_params())
        if response.status_code == 404:
            raise NotFoundError(
                f"Pull request #{pr_number} not found in Harness repo {owner}/{repo}.",
            )
        if response.status_code >= 400:
            self._raise_http_error(response, "ensure_pull_request_exists")

    def ensure_repository_exists(self, owner: str, repo: str) -> None:
        repo_ref = self._repo_ref(owner, repo)
        url = self._api_url(f"repos/{repo_ref}")
        response = self._client.get(url, params=self._account_params())
        if response.status_code == 404:
            raise NotFoundError(f"Harness repository {owner}/{repo} not found.")
        if response.status_code >= 400:
            self._raise_http_error(response, "ensure_repository_exists")

    # ------------------------------------------------------------------
    # PR / scan context
    # ------------------------------------------------------------------

    def get_pull_request_context(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> PullRequestContext:
        repo_ref = self._repo_ref(owner, repo)
        params = self._account_params()

        pr_resp = self._client.get(
            self._api_url(f"repos/{repo_ref}/pullreq/{pr_number}"),
            params=params,
        )
        if pr_resp.status_code >= 400:
            self._raise_http_error(pr_resp, "get_pull_request")
        pr = pr_resp.json()

        files_resp = self._client.get(
            self._api_url(f"repos/{repo_ref}/pullreq/{pr_number}/files"),
            params=params,
        )
        if files_resp.status_code >= 400:
            self._raise_http_error(files_resp, "get_pull_request_files")
        raw_files = files_resp.json() or []

        files: list[PullRequestFileChange] = []
        diff_sections: list[str] = []
        for entry in raw_files:
            filename = entry.get("path") or entry.get("file_name") or ""
            status = entry.get("status") or entry.get("change_type") or "modified"
            additions = int(entry.get("additions") or entry.get("added") or 0)
            deletions = int(entry.get("deletions") or entry.get("removed") or 0)
            patch = entry.get("patch") or entry.get("diff")
            files.append(
                PullRequestFileChange(
                    filename=filename,
                    status=status,
                    additions=additions,
                    deletions=deletions,
                    patch=patch,
                ),
            )
            diff_body = patch or "Patch omitted by Harness Code (binary or oversized)."
            diff_sections.append(
                "\n".join(
                    [
                        f"diff --git a/{filename} b/{filename}",
                        f"change-type: {status}",
                        diff_body,
                    ],
                ),
            )

        head_sha = (
            pr.get("source_sha")
            or (pr.get("head") or {}).get("sha")
            or pr.get("merge_head_sha")
            or ""
        )
        head_ref = pr.get("source_branch") or (pr.get("head") or {}).get("ref") or ""
        base_ref = pr.get("target_branch") or (pr.get("base") or {}).get("ref") or ""

        return PullRequestContext(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            title=pr.get("title") or f"PR #{pr_number}",
            body=pr.get("description") or pr.get("body"),
            html_url=pr.get("url") or self._build_pr_url(owner, repo, pr_number),
            head_sha=head_sha,
            head_ref=head_ref,
            base_ref=base_ref,
            diff="\n\n".join(diff_sections),
            files=files,
        )

    def get_repository_scan_context(
        self,
        owner: str,
        repo: str,
        ref: str | None = None,
        folder: str | None = None,
    ) -> RepositoryScanContext:
        repo_ref = self._repo_ref(owner, repo)
        params = self._account_params()

        repo_resp = self._client.get(
            self._api_url(f"repos/{repo_ref}"),
            params=params,
        )
        if repo_resp.status_code >= 400:
            self._raise_http_error(repo_resp, "get_repository")
        repo_meta = repo_resp.json()

        default_branch = repo_meta.get("default_branch") or repo_meta.get("defaultBranch")
        effective_ref = ref or default_branch
        if not effective_ref:
            raise ExternalServiceError(
                f"Unable to determine a default branch for Harness repo {owner}/{repo}.",
            )

        commit_resp = self._client.get(
            self._api_url(f"repos/{repo_ref}/commits/{quote(effective_ref, safe='')}"),
            params=params,
        )
        if commit_resp.status_code >= 400:
            self._raise_http_error(commit_resp, "get_commit")
        commit = commit_resp.json() or {}
        head_sha = commit.get("sha") or commit.get("commit_id") or effective_ref

        normalized_folder = self._normalize_folder(folder)
        html_url = repo_meta.get("html_url") or self._build_repo_url(owner, repo)

        return RepositoryScanContext(
            owner=owner,
            repo=repo,
            ref=effective_ref,
            folder=normalized_folder,
            head_sha=head_sha,
            html_url=html_url,
            default_branch=default_branch,
        )

    @staticmethod
    def _normalize_folder(folder: str | None) -> str | None:
        if folder is None:
            return None
        cleaned = folder.strip().strip("/")
        return cleaned or None

    # ------------------------------------------------------------------
    # Archive download — delegates to universal git-clone
    # ------------------------------------------------------------------

    def download_repository_archive(
        self,
        owner: str,
        repo: str,
        ref: str,
        target_dir: Path,
    ) -> Path:
        org, project = _split_owner(owner)
        clone_url = self._git_clone_url(org=org, project=project, repo=repo)
        return clone_repository(
            clone_url=clone_url,
            ref=ref,
            target_dir=target_dir,
            username="x-api-key",
            password=self._token_provider(),
            timeout_seconds=self._settings.repository_archive_timeout_seconds,
        )

    def _git_clone_url(self, *, org: str, project: str, repo: str) -> str:
        account = self._settings.harness_account_id or ""
        host = self._git_host()
        return f"https://{host}/{account}/{org}/{project}/{repo}.git"

    def _git_host(self) -> str:
        # Harness Code git endpoints live under ``git.harness.io`` by default;
        # mirror the REST base URL so self-hosted Gitness deployments work.
        base = self._settings.harness_base_url.rstrip("/")
        if "app.harness.io" in base:
            return "git.harness.io"
        # Strip scheme for self-hosted (https://gitness.example.com → gitness.example.com).
        return base.split("://", 1)[-1]

    def _build_repo_url(self, owner: str, repo: str) -> str:
        org, project = _split_owner(owner)
        account = self._settings.harness_account_id or ""
        return (
            f"{self._settings.harness_base_url}/ng/account/{account}/"
            f"code/orgs/{org}/projects/{project}/repos/{repo}"
        )

    def _build_pr_url(self, owner: str, repo: str, pr_number: int) -> str:
        return f"{self._build_repo_url(owner, repo)}/pulls/{pr_number}"

    # ------------------------------------------------------------------
    # Context-file walker — reuse GitHub's identical logic
    # ------------------------------------------------------------------

    def collect_context_files(
        self,
        repository_root: Path,
        max_files: int,
        max_file_bytes: int,
        folder: str | None = None,
    ) -> list[Path]:
        # The walker doesn't depend on GitHub; we just delegate to the canonical
        # implementation in GitHubService to guarantee identical ranking.
        from cara.services.github_service import GitHubService

        delegate = GitHubService(
            client=None,
            token_provider=lambda: "",
            settings=self._settings,
        )
        return delegate.collect_context_files(
            repository_root=repository_root,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
            folder=folder,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _account_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self._settings.harness_account_id:
            params["accountIdentifier"] = self._settings.harness_account_id
        return params

    def _raise_http_error(self, response: Any, action: str) -> None:
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001 - non-JSON error body
            payload = {"message": response.text[:500] if hasattr(response, "text") else ""}
        message = payload.get("message") or payload.get("error") or "Harness API error."
        if response.status_code in (401, 403):
            raise AuthenticationError(f"{action}: {message}")
        if response.status_code == 404:
            raise NotFoundError(f"{action}: {message}")
        raise ExternalServiceError(f"{action} failed (HTTP {response.status_code}): {message}")
