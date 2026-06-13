import base64
import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse, quote

import httpx

from app.core.logging import logger
from app.core.exceptions import ParsingError


# ── Shared constants ───────────────────────────────────────────────────────────

# File extensions worth ingesting from a repo
_INDEXABLE_EXTENSIONS = {
    # Documentation
    ".md", ".rst", ".txt", ".adoc",
    # Config / IaC
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg",
    # CI/CD
    ".jenkinsfile", ".groovy",
    # Code (for SDLC context)
    ".py", ".java", ".js", ".ts", ".go", ".tf", ".hcl",
    # Docker / K8s
    ".dockerfile",
}

_INDEXABLE_NAMES = {
    "dockerfile", "makefile", "rakefile", "gemfile",
    "jenkinsfile", "procfile", "vagrantfile", "readme",
}

_MAX_FILE_BYTES = 1 * 1024 * 1024        # skip files > 1 MB
_REQUEST_TIMEOUT = 30.0


# ── Platform detection ─────────────────────────────────────────────────────────

def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "github.com" in host:
        return "github"
    if "harness.io" in host:
        return "harness"
    raise ParsingError(url, "Cannot detect platform. Supported: github.com, harness.io")


# ── Base helpers (shared by all platforms) ─────────────────────────────────────

def _is_indexable(path: str) -> bool:
    p = PurePosixPath(path)
    if p.name.lower() in _INDEXABLE_NAMES:
        return True
    return p.suffix.lower() in _INDEXABLE_EXTENSIONS


def _normalize_file(content: str, file_path: str, repo_url: str, branch: str) -> dict:
    """Transform raw file content into the pipeline-compatible dict."""
    ext = PurePosixPath(file_path).suffix.lower()

    sections: list[dict] = []
    if ext in (".md", ".rst", ".adoc"):
        for m in re.finditer(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE):
            sections.append({
                "title": m.group(2).strip(),
                "level": len(m.group(1)),
            })

    text = re.sub(r"\r\n|\r", "\n", content)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return {
        "text": text,
        "sections": sections,
        "tables": [],
        "page_count": 1,
        "word_count": len(text.split()),
        "metadata": {
            "source_url": repo_url,
            "branch": branch,
            "file_path": file_path,
            "file_ext": ext,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  GitHub
# ══════════════════════════════════════════════════════════════════════════════

_GITHUB_API = "https://api.github.com"


class _GitHubClient:

    def __init__(self, token: str | None) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SDLC-KB-Bot/1.0",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    @staticmethod
    def parse_url(url: str) -> tuple[str, str]:
        parts = [p for p in urlparse(url.rstrip("/")).path.strip("/").split("/") if p]
        if len(parts) < 2:
            raise ParsingError(url, "Expected: https://github.com/owner/repo")
        return parts[0], parts[1].removesuffix(".git")

    async def default_branch(self, owner: str, repo: str) -> str:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, headers=self._headers()) as c:
            r = await c.get(f"{_GITHUB_API}/repos/{owner}/{repo}")
            r.raise_for_status()
            return r.json()["default_branch"]

    async def fetch_tree(self, owner: str, repo: str, branch: str) -> list[dict]:
        url = f"{_GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, headers=self._headers()) as c:
            r = await c.get(url)
            if r.status_code == 404:
                raise ParsingError(f"{owner}/{repo}", f"Branch '{branch}' not found or inaccessible")
            r.raise_for_status()
            data = r.json()
            if data.get("truncated"):
                logger.warning("repo_tree_truncated", owner=owner, repo=repo)
            return data.get("tree", [])

    async def fetch_files(
        self, owner: str, repo: str, branch: str, tree: list[dict],
    ) -> list[dict]:
        results: list[dict] = []
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT, headers=self._headers(), follow_redirects=True,
        ) as client:
            for entry in tree:
                try:
                    content = await self._fetch_blob(client, owner, repo, entry["sha"])
                    if content is None:
                        continue
                    results.append(_normalize_file(
                        content, entry["path"],
                        f"https://github.com/{owner}/{repo}", branch,
                    ))
                except Exception as exc:
                    logger.warning("repo_file_skip", path=entry["path"], error=str(exc))
        return results

    @staticmethod
    async def _fetch_blob(
        client: httpx.AsyncClient, owner: str, repo: str, sha: str,
    ) -> str | None:
        r = await client.get(f"{_GITHUB_API}/repos/{owner}/{repo}/git/blobs/{sha}")
        r.raise_for_status()
        blob = r.json()
        if blob.get("size", 0) > _MAX_FILE_BYTES:
            return None
        enc = blob.get("encoding", "")
        if enc == "base64":
            raw = base64.b64decode(blob["content"])
        elif enc == "utf-8":
            raw = blob["content"].encode("utf-8")
        else:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None


# ══════════════════════════════════════════════════════════════════════════════
#  Harness Code Repository
# ══════════════════════════════════════════════════════════════════════════════

_HARNESS_CODE_API = "https://app.harness.io/code/api/v1"


class _HarnessClient:

    def __init__(self, token: str | None) -> None:
        self._token = token

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "SDLC-KB-Bot/1.0",
        }
        if self._token:
            h["x-api-key"] = self._token
        return h

    @staticmethod
    def parse_url(url: str) -> tuple[str, str, str, str]:
        """
        Parse a Harness Code UI URL → (account_id, org, project, repo).

        Accepted formats:
          https://app.harness.io/ng/account/{acct}/module/code/orgs/{org}/projects/{proj}/repos/{repo}
          https://app.harness.io/ng/account/{acct}/module/code/orgs/{org}/projects/{proj}/repos/{repo}/files/...
        """
        path = urlparse(url.rstrip("/")).path.strip("/")
        m = re.match(
            r"ng/account/([^/]+)/module/code/orgs/([^/]+)/projects/([^/]+)/repos/([^/]+)",
            path,
        )
        if not m:
            raise ParsingError(
                url,
                "Expected: https://app.harness.io/ng/account/{acct}/module/code/"
                "orgs/{org}/projects/{proj}/repos/{repo}",
            )
        return m.group(1), m.group(2), m.group(3), m.group(4)

    @staticmethod
    def _repo_ref(account_id: str, org: str, project: str, repo: str) -> str:
        """Build the terminated-path repo_ref used by the Harness Code API."""
        return f"{account_id}/{org}/{project}/{repo}/+"

    async def default_branch(
        self, account_id: str, org: str, project: str, repo: str,
    ) -> str:
        ref = self._repo_ref(account_id, org, project, repo)
        url = f"{_HARNESS_CODE_API}/repos/{ref}"
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, headers=self._headers(), verify=False) as c:
            r = await c.get(url)
            r.raise_for_status()
            return r.json().get("default_branch", "main")

    async def list_paths(
        self, account_id: str, org: str, project: str, repo: str, branch: str,
    ) -> list[str]:
        """Return a flat list of file paths via GET /repos/{ref}/paths."""
        ref = self._repo_ref(account_id, org, project, repo)
        url = f"{_HARNESS_CODE_API}/repos/{ref}/paths"
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, headers=self._headers(), verify=False) as c:
            r = await c.get(url, params={"git_ref": branch})
            if r.status_code == 404:
                raise ParsingError(
                    f"{org}/{project}/{repo}",
                    f"Branch '{branch}' not found or repo inaccessible",
                )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            return data.get("files", data.get("paths", []))

    async def fetch_raw(
        self,
        client: httpx.AsyncClient,
        account_id: str, org: str, project: str, repo: str,
        file_path: str,
        branch: str,
    ) -> str | None:
        """GET /repos/{ref}/raw/{path}?git_ref=..."""
        ref = self._repo_ref(account_id, org, project, repo)
        url = f"{_HARNESS_CODE_API}/repos/{ref}/raw/{file_path}"
        r = await client.get(url, params={"git_ref": branch})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        if len(r.content) > _MAX_FILE_BYTES:
            return None
        try:
            return r.text
        except Exception:
            return None

    async def fetch_files(
        self,
        account_id: str, org: str, project: str, repo: str,
        branch: str,
        paths: list[str],
        repo_url: str,
    ) -> list[dict]:
        results: list[dict] = []
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT, headers=self._headers(), follow_redirects=True, verify=False,
        ) as client:
            for fp in paths:
                try:
                    content = await self.fetch_raw(
                        client, account_id, org, project, repo, fp, branch,
                    )
                    if content is None:
                        continue
                    results.append(_normalize_file(content, fp, repo_url, branch))
                except Exception as exc:
                    logger.warning("repo_file_skip", path=fp, error=str(exc))
        return results


# ══════════════════════════════════════════════════════════════════════════════
#  Unified connector
# ══════════════════════════════════════════════════════════════════════════════

class RepositoryConnector:
    """
    Multi-platform repository connector.
    Supports GitHub and Harness Code Repository.
    Auto-detects platform from the URL.
    """

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    async def fetch_repo(
        self,
        repo_url: str,
        branch: str | None = None,
        path_filter: str | None = None,
    ) -> list[dict]:
        platform = detect_platform(repo_url)

        if platform == "github":
            return await self._fetch_github(repo_url, branch, path_filter)
        elif platform == "harness":
            return await self._fetch_harness(repo_url, branch, path_filter)
        else:
            raise ParsingError(repo_url, f"Unsupported platform: {platform}")

    # ── GitHub path ────────────────────────────────────────────────────────

    async def _fetch_github(
        self, repo_url: str, branch: str | None, path_filter: str | None,
    ) -> list[dict]:
        gh = _GitHubClient(self._token)
        owner, repo = gh.parse_url(repo_url)

        if not branch:
            branch = await gh.default_branch(owner, repo)

        tree = await gh.fetch_tree(owner, repo, branch)
        matched = [
            e for e in tree
            if e.get("type") == "blob"
            and (not path_filter or e["path"].startswith(path_filter))
            and _is_indexable(e["path"])
        ]

        logger.info(
            "repo_files_matched",
            platform="github", owner=owner, repo=repo, branch=branch,
            total=len(tree), matched=len(matched),
        )

        results = await gh.fetch_files(owner, repo, branch, matched)
        logger.info("repo_fetch_done", platform="github", owner=owner, repo=repo, files=len(results))
        return results

    # ── Harness path ───────────────────────────────────────────────────────

    async def _fetch_harness(
        self, repo_url: str, branch: str | None, path_filter: str | None,
    ) -> list[dict]:
        hn = _HarnessClient(self._token)
        account_id, org, project, repo = hn.parse_url(repo_url)

        if not branch:
            branch = await hn.default_branch(account_id, org, project, repo)

        all_paths = await hn.list_paths(account_id, org, project, repo, branch)

        # API may return strings or dicts with a "path" key
        flat_paths: list[str] = []
        for entry in all_paths:
            p = entry if isinstance(entry, str) else entry.get("path", "")
            if p:
                flat_paths.append(p)

        matched = [
            p for p in flat_paths
            if (not path_filter or p.startswith(path_filter))
            and _is_indexable(p)
        ]

        logger.info(
            "repo_files_matched",
            platform="harness", org=org, project=project, repo=repo, branch=branch,
            total=len(flat_paths), matched=len(matched),
        )

        results = await hn.fetch_files(
            account_id, org, project, repo, branch, matched, repo_url,
        )
        logger.info("repo_fetch_done", platform="harness", repo=repo, files=len(results))
        return results
