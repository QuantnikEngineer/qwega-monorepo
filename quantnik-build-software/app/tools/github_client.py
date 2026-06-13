"""
GitHub client — create repos and push files via GitHub REST API.
"""
import httpx
import base64
from typing import Dict, Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

GH_API = "https://api.github.com"
HEADERS = lambda token: {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class GitHubClient:
    def __init__(self):
        self.token = settings.github_token
        self.org = settings.github_org

    def _h(self):
        return HEADERS(self.token)

    async def repo_exists(self, repo_name: str) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{GH_API}/repos/{self.org}/{repo_name}", headers=self._h())
            return r.status_code == 200

    async def create_repo(self, repo_name: str, description: str = "") -> str:
        """Create a repo and return its HTML URL."""
        async with httpx.AsyncClient() as client:
            payload = {
                "name": repo_name,
                "description": description,
                "private": True,
                "auto_init": True,
            }
            r = await client.post(f"{GH_API}/orgs/{self.org}/repos", json=payload, headers=self._h())
            if r.status_code in (201, 422):  # 422 = already exists
                if r.status_code == 422:
                    logger.info("Repo already exists", repo=repo_name)
                    return f"https://github.com/{self.org}/{repo_name}"
                return r.json()["html_url"]
            r.raise_for_status()
            return r.json()["html_url"]

    async def push_file(self, repo_name: str, file_path: str, content: str,
                        message: str = "chore: add generated file", branch: str = "main") -> str:
        """Create or update a single file in the repo. Returns file HTML URL."""
        encoded = base64.b64encode(content.encode()).decode()
        async with httpx.AsyncClient() as client:
            # Get current SHA if file exists
            sha = None
            get_r = await client.get(
                f"{GH_API}/repos/{self.org}/{repo_name}/contents/{file_path}",
                headers=self._h(), params={"ref": branch}
            )
            if get_r.status_code == 200:
                sha = get_r.json().get("sha")

            payload: Dict = {"message": message, "content": encoded, "branch": branch}
            if sha:
                payload["sha"] = sha

            put_r = await client.put(
                f"{GH_API}/repos/{self.org}/{repo_name}/contents/{file_path}",
                json=payload, headers=self._h()
            )
            put_r.raise_for_status()
            return put_r.json()["content"]["html_url"]

    async def push_files(self, repo_name: str, files: Dict[str, str], commit_msg: str) -> str:
        """Push multiple files. Returns repo HTML URL."""
        for path, content in files.items():
            await self.push_file(repo_name, path, content, message=commit_msg)
        return f"https://github.com/{self.org}/{repo_name}"


_gh: Optional[GitHubClient] = None


def get_github() -> GitHubClient:
    global _gh
    if _gh is None:
        _gh = GitHubClient()
    return _gh
