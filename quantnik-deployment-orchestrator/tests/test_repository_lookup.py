import asyncio

import pytest
import httpx

import app.tools.repository_lookup as repository_lookup_module
from app.tools.repository_lookup import RepositoryLookupClient, RepositoryLookupError, RepositoryOption


def test_harness_repository_lookup_returns_project_repositories(monkeypatch):
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_base_url', 'https://app.harness.io')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_account_identifier', '2KolbecvR0aAcgQ5uXBObA')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_org_identifier', 'default')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_project_identifier', 'QUANTNIK_Build_AI')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_secret_name', 'harness_secret')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_pat_token', '')
    monkeypatch.setattr(repository_lookup_module, 'resolve_optional_secret', lambda _: 'test-token')
    client = RepositoryLookupClient()

    async def fake_fetch_json(url, headers, provider):
        assert provider == 'harness'
        assert url == (
            'https://app.harness.io/gateway/code/api/v1/repos?'
            'accountIdentifier=2KolbecvR0aAcgQ5uXBObA&orgIdentifier=default&projectIdentifier=QUANTNIK_Build_AI&page=1&limit=100'
        )
        assert headers == {'Accept': 'application/json', 'x-api-key': 'test-token'}
        return [
            {
                'identifier': 'bdd-agent',
                'git_url': 'https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/bdd-agent.git',
            },
            {
                'identifier': 'quantnik-api',
                'git_url': 'https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/quantnik-api.git',
            },
        ]

    monkeypatch.setattr(client, '_fetch_json', fake_fetch_json)

    repositories = asyncio.run(client.list_repositories('harness'))

    assert repositories == [
        RepositoryOption(
            id='bdd-agent',
            label='bdd-agent',
            url='https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/bdd-agent.git',
        ),
        RepositoryOption(
            id='quantnik-api',
            label='quantnik-api',
            url='https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/quantnik-api.git',
        ),
    ]

    asyncio.run(client.close())


def test_harness_repository_lookup_paginates_beyond_default_first_page(monkeypatch):
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_base_url', 'https://app.harness.io')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_account_identifier', '2KolbecvR0aAcgQ5uXBObA')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_org_identifier', 'default')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_project_identifier', 'QUANTNIK_Build_AI')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_secret_name', 'harness_secret')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_pat_token', '')
    monkeypatch.setattr(repository_lookup_module, 'resolve_optional_secret', lambda _: 'test-token')
    client = RepositoryLookupClient()
    observed_urls: list[str] = []

    async def fake_fetch_json(url, headers, provider):
        assert provider == 'harness'
        assert headers == {'Accept': 'application/json', 'x-api-key': 'test-token'}
        observed_urls.append(url)
        if url.endswith('&page=1&limit=100'):
            return [
                {
                    'identifier': f'repo-{index:03d}',
                    'git_url': f'https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/repo-{index:03d}.git',
                }
                for index in range(100)
            ]
        if url.endswith('&page=2&limit=100'):
            return [
                {
                    'identifier': 'quantnik-userstory-estimator',
                    'git_url': 'https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/quantnik-userstory-estimator.git',
                }
            ]
        raise AssertionError(f'Unexpected URL: {url}')

    monkeypatch.setattr(client, '_fetch_json', fake_fetch_json)

    repositories = asyncio.run(client.list_repositories('harness'))

    assert observed_urls == [
        'https://app.harness.io/gateway/code/api/v1/repos?accountIdentifier=2KolbecvR0aAcgQ5uXBObA&orgIdentifier=default&projectIdentifier=QUANTNIK_Build_AI&page=1&limit=100',
        'https://app.harness.io/gateway/code/api/v1/repos?accountIdentifier=2KolbecvR0aAcgQ5uXBObA&orgIdentifier=default&projectIdentifier=QUANTNIK_Build_AI&page=2&limit=100',
    ]
    assert any(repository.label == 'quantnik-userstory-estimator' for repository in repositories)

    asyncio.run(client.close())


def test_harness_branch_lookup_uses_selected_repository_git_url(monkeypatch):
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_base_url', 'https://app.harness.io')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_account_identifier', '2KolbecvR0aAcgQ5uXBObA')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_org_identifier', 'default')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_project_identifier', 'QUANTNIK_Build_AI')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_secret_name', 'harness_secret')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_pat_token', '')
    monkeypatch.setattr(repository_lookup_module, 'resolve_optional_secret', lambda _: 'test-token')
    client = RepositoryLookupClient()

    async def fake_fetch_json(url, headers, provider):
        assert provider == 'harness'
        assert url == (
            'https://app.harness.io/gateway/code/api/v1/repos/bdd-agent/branches?'
            'accountIdentifier=2KolbecvR0aAcgQ5uXBObA&orgIdentifier=default&projectIdentifier=QUANTNIK_Build_AI&page=1&limit=100'
        )
        assert headers == {'Accept': 'application/json', 'x-api-key': 'test-token'}
        return [
            {'name': 'main'},
            {'name': 'release/1.0'},
        ]

    monkeypatch.setattr(client, '_fetch_json', fake_fetch_json)

    branches = asyncio.run(
        client.list_branches(
            'harness',
            'https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/bdd-agent.git',
        )
    )

    assert branches == ['main', 'release/1.0']

    asyncio.run(client.close())


def test_harness_branch_lookup_requires_repository_selection(monkeypatch):
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_base_url', 'https://app.harness.io')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_account_identifier', '2KolbecvR0aAcgQ5uXBObA')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_org_identifier', 'default')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_project_identifier', 'QUANTNIK_Build_AI')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_secret_name', 'harness_secret')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_pat_token', '')
    monkeypatch.setattr(repository_lookup_module, 'resolve_optional_secret', lambda _: 'test-token')
    client = RepositoryLookupClient()

    with pytest.raises(RepositoryLookupError, match='Select a repository from the loaded list first'):
        asyncio.run(
            client.list_branches(
                'harness',
                'https://app.harness.io/ng/account/2KolbecvR0aAcgQ5uXBObA/module/code/orgs/default/projects/QUANTNIK_Build_AI',
            )
        )

    asyncio.run(client.close())


def test_github_lookup_rejects_disallowed_hosts(monkeypatch):
    monkeypatch.setattr(repository_lookup_module.settings, 'github_allowed_hosts', 'github.com,api.github.com')
    client = RepositoryLookupClient()

    with pytest.raises(RepositoryLookupError, match='GitHub repository URL host is not allowed'):
        asyncio.run(client.list_branches('github-actions', 'https://malicious.example.com/org/repository'))

    asyncio.run(client.close())


def test_fetch_json_sanitizes_upstream_error(monkeypatch):
    client = RepositoryLookupClient()

    async def fake_get(url, headers):
        request = httpx.Request('GET', url)
        return httpx.Response(403, request=request, text='raw upstream provider detail')

    monkeypatch.setattr(client._client, 'get', fake_get)

    with pytest.raises(RepositoryLookupError) as exc_info:
        asyncio.run(client._fetch_json('https://github.com/example/repo', {}, 'github-actions'))

    assert exc_info.value.user_message == 'Repository lookup failed at the provider. Verify repository access and provider configuration.'
    assert 'raw upstream provider detail' not in exc_info.value.user_message

    asyncio.run(client.close())


def test_github_repository_lookup_falls_back_to_harness_when_no_github_url(monkeypatch):
    monkeypatch.setattr(repository_lookup_module.settings, 'github_repository_url', '')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_base_url', 'https://app.harness.io')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_account_identifier', '2KolbecvR0aAcgQ5uXBObA')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_org_identifier', 'default')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_project_identifier', 'QUANTNIK_Build_AI')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_secret_name', 'harness_secret')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_pat_token', '')
    monkeypatch.setattr(repository_lookup_module, 'resolve_optional_secret', lambda _: 'test-token')
    client = RepositoryLookupClient()

    async def fake_fetch_json(url, headers, provider):
        assert provider == 'harness'
        assert url == (
            'https://app.harness.io/gateway/code/api/v1/repos?'
            'accountIdentifier=2KolbecvR0aAcgQ5uXBObA&orgIdentifier=default&projectIdentifier=QUANTNIK_Build_AI&page=1&limit=100'
        )
        assert headers == {'Accept': 'application/json', 'x-api-key': 'test-token'}
        return [
            {
                'identifier': 'bdd-agent',
                'git_url': 'https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/bdd-agent.git',
            }
        ]

    monkeypatch.setattr(client, '_fetch_json', fake_fetch_json)

    repositories = asyncio.run(client.list_repositories('github-actions'))

    assert repositories == [
        RepositoryOption(
            id='bdd-agent',
            label='bdd-agent',
            url='https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/bdd-agent.git',
        )
    ]

    asyncio.run(client.close())


def test_github_branch_lookup_uses_harness_when_pasted_harness_url(monkeypatch):
    monkeypatch.setattr(repository_lookup_module.settings, 'github_repository_url', '')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_base_url', 'https://app.harness.io')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_account_identifier', '2KolbecvR0aAcgQ5uXBObA')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_org_identifier', 'default')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_project_identifier', 'QUANTNIK_Build_AI')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_secret_name', 'harness_secret')
    monkeypatch.setattr(repository_lookup_module.settings, 'harness_pat_token', '')
    monkeypatch.setattr(repository_lookup_module, 'resolve_optional_secret', lambda _: 'test-token')
    client = RepositoryLookupClient()

    async def fake_fetch_json(url, headers, provider):
        assert provider == 'harness'
        assert url == (
            'https://app.harness.io/gateway/code/api/v1/repos/bdd-agent/branches?'
            'accountIdentifier=2KolbecvR0aAcgQ5uXBObA&orgIdentifier=default&projectIdentifier=QUANTNIK_Build_AI&page=1&limit=100'
        )
        assert headers == {'Accept': 'application/json', 'x-api-key': 'test-token'}
        return [
            {'name': 'main'},
            {'name': 'release/1.0'},
        ]

    monkeypatch.setattr(client, '_fetch_json', fake_fetch_json)

    branches = asyncio.run(
        client.list_branches(
            'github-actions',
            'https://git.harness.io/2KolbecvR0aAcgQ5uXBObA/default/QUANTNIK_Build_AI/bdd-agent.git',
        )
    )

    assert branches == ['main', 'release/1.0']

    asyncio.run(client.close())