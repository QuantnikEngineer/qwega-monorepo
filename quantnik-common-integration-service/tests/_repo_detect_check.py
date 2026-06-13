"""Standalone smoke test for _is_repo_url (no external deps)."""
from urllib.parse import urlparse

_REPO_HOST_SUFFIXES = (
    "github.com", "gitlab.com", "bitbucket.org",
    "dev.azure.com", "visualstudio.com", "harness.io",
)


def _is_repo_url(raw: str) -> bool:
    try:
        u = urlparse(raw)
        host = (u.hostname or "").lower()
        if not host:
            return False
        if not any(host == s or host.endswith("." + s) for s in _REPO_HOST_SUFFIXES):
            return False
        parts = [p for p in (u.path or "").strip("/").split("/") if p]
        if host.endswith("harness.io"):
            return "repos" in parts or len(parts) >= 4
        return len(parts) >= 2
    except Exception:
        return False


CASES = [
    ("https://github.com/owner/repo", True),
    ("https://github.com/owner/repo/blob/main/README.md", True),
    ("https://www.github.com/owner/repo", True),
    ("https://github.com/owner", False),
    ("https://github.com/", False),
    ("https://gist.github.com/user/abc123", True),
    ("https://gitlab.com/group/project", True),
    ("https://bitbucket.org/team/repo", True),
    ("https://dev.azure.com/org/project/_git/repo", True),
    ("https://example.com/some/page", False),
    ("https://docs.python.org/3/library/urllib.html", False),
    ("https://app.harness.io/ng/account/abc/orgs/o/projects/p/repos/r", True),
    ("https://harness.io/about", False),
    ("not a url", False),
    ("", False),
]


if __name__ == "__main__":
    ok, fail = 0, 0
    for url, expected in CASES:
        got = _is_repo_url(url)
        if got == expected:
            ok += 1
        else:
            fail += 1
            print(f"FAIL url={url!r} expected={expected} got={got}")
    print(f"PASSED {ok}/{ok+fail}")
