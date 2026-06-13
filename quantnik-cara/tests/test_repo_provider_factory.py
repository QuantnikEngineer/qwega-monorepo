from cara.models.domain import RepoProviderName
from cara.services.repo_provider_factory import detect_provider_from_text


def test_detect_provider_returns_github_for_empty_text() -> None:
    assert detect_provider_from_text("") == RepoProviderName.GITHUB
    assert detect_provider_from_text(None) == RepoProviderName.GITHUB


def test_detect_provider_recognises_github_urls() -> None:
    assert (
        detect_provider_from_text("Review https://github.com/acme/rocket/pull/42")
        == RepoProviderName.GITHUB
    )


def test_detect_provider_recognises_git_harness_io() -> None:
    text = "Review https://git.harness.io/acct/org/proj/repo/-/pulls/7"
    assert detect_provider_from_text(text) == RepoProviderName.HARNESS


def test_detect_provider_recognises_app_harness_io_code_path() -> None:
    text = (
        "Scan https://app.harness.io/ng/account/abc/code/orgs/finance/projects/api/repos/svc"
    )
    assert detect_provider_from_text(text) == RepoProviderName.HARNESS


def test_detect_provider_is_case_insensitive() -> None:
    assert (
        detect_provider_from_text("PR at GIT.HARNESS.IO/x/y/z")
        == RepoProviderName.HARNESS
    )
