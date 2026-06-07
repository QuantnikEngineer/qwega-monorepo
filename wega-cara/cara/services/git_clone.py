"""Universal git-clone helper used by every repo provider.

A shallow ``git clone --depth 1`` over HTTPS works against GitHub, Harness
Code, GitLab, Bitbucket and self-hosted Gitness, so all providers share this
helper instead of maintaining provider-specific zipball downloaders. The
returned path is the cloned repository root, ready for the orchestrator's
context-file walker.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

from cara.core.errors import ExternalServiceError

logger = logging.getLogger(__name__)


def _inject_basic_auth(url: str, username: str, password: str) -> str:
    """Embed HTTP Basic credentials into ``url`` so ``git clone`` can use them.

    Anything that isn't ASCII-safe is URL-encoded.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ExternalServiceError(
            f"Only http/https clone URLs are supported (got scheme {parsed.scheme!r}).",
        )
    user = quote(username, safe="")
    secret = quote(password, safe="")
    netloc = f"{user}:{secret}@{parsed.hostname}"
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def clone_repository(
    *,
    clone_url: str,
    ref: str,
    target_dir: Path,
    username: str | None = None,
    password: str | None = None,
    timeout_seconds: int = 120,
) -> Path:
    """Shallow-clone ``clone_url`` at ``ref`` into ``target_dir``.

    The function returns the path to the cloned working tree. ``ref`` may be a
    branch name, tag, or full commit SHA. We clone with ``--depth 1`` and
    ``--single-branch`` so the network footprint stays minimal.

    Credentials are injected directly into the URL when both ``username`` and
    ``password`` are provided. The token never lands in argv (we keep the URL
    in env-style) and ``--no-progress`` keeps the credentials out of stderr.
    """
    if shutil.which("git") is None:
        raise ExternalServiceError(
            "Cannot clone repository: 'git' binary is not available in the runtime image.",
        )

    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)

    repo_root = target_dir / "repo"
    if repo_root.exists():
        shutil.rmtree(repo_root, ignore_errors=True)

    authed_url = clone_url
    if username and password:
        authed_url = _inject_basic_auth(clone_url, username, password)

    args = [
        "git",
        "-c",
        "advice.detachedHead=false",
        "clone",
        "--depth",
        "1",
        "--single-branch",
        "--no-tags",
        "--no-progress",
        "--branch",
        ref,
        authed_url,
        str(repo_root),
    ]

    logger.info(
        "git_clone_started clone_url=%s ref=%s target=%s",
        clone_url,
        ref,
        repo_root,
    )

    try:
        completed = subprocess.run(  # noqa: S603 - args is a hard-coded list
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExternalServiceError(
            f"git clone timed out after {timeout_seconds}s for {clone_url}@{ref}.",
        ) from exc

    if completed.returncode == 0:
        return repo_root

    # Branch name failed — fall back to cloning default + checkout SHA.
    if "Remote branch" in completed.stderr or "not found" in completed.stderr:
        logger.warning(
            "git_clone_branch_missing falling_back_to_sha clone_url=%s ref=%s",
            clone_url,
            ref,
        )
        return _clone_then_checkout(
            clone_url=authed_url,
            ref=ref,
            target_dir=target_dir,
            timeout_seconds=timeout_seconds,
        )

    raise ExternalServiceError(
        f"git clone failed for {clone_url}@{ref}: {completed.stderr.strip() or completed.stdout.strip()}",
    )


def _clone_then_checkout(
    *,
    clone_url: str,
    ref: str,
    target_dir: Path,
    timeout_seconds: int,
) -> Path:
    repo_root = target_dir / "repo"
    if repo_root.exists():
        shutil.rmtree(repo_root, ignore_errors=True)

    clone_cmd = [
        "git",
        "-c",
        "advice.detachedHead=false",
        "clone",
        "--filter=blob:none",
        "--no-progress",
        clone_url,
        str(repo_root),
    ]
    completed = subprocess.run(  # noqa: S603
        clone_cmd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise ExternalServiceError(
            f"git clone fallback failed: {completed.stderr.strip() or completed.stdout.strip()}",
        )

    checkout = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo_root), "checkout", ref],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    if checkout.returncode != 0:
        raise ExternalServiceError(
            f"git checkout {ref} failed: {checkout.stderr.strip() or checkout.stdout.strip()}",
        )
    return repo_root
