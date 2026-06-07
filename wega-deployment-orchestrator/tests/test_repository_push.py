import asyncio
import subprocess

from app.tools.repository_lookup import RepositoryLookupClient


def _run_git(args: list[str], cwd: str) -> str:
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def test_push_file_with_git_commits_and_skips_unchanged_content(tmp_path, monkeypatch):
    remote_path = tmp_path / 'remote.git'
    seed_path = tmp_path / 'seed'
    inspect_path = tmp_path / 'inspect'

    _run_git(['init', '--bare', str(remote_path)], cwd=str(tmp_path))
    _run_git(['init', str(seed_path)], cwd=str(tmp_path))
    _run_git(['checkout', '-b', 'main'], cwd=str(seed_path))
    _run_git(['config', 'user.name', 'Seed User'], cwd=str(seed_path))
    _run_git(['config', 'user.email', 'seed@example.com'], cwd=str(seed_path))
    (seed_path / 'README.md').write_text('# demo\n', encoding='utf-8')
    _run_git(['add', 'README.md'], cwd=str(seed_path))
    _run_git(['commit', '-m', 'Initial commit'], cwd=str(seed_path))
    _run_git(['remote', 'add', 'origin', str(remote_path)], cwd=str(seed_path))
    _run_git(['push', '-u', 'origin', 'main'], cwd=str(seed_path))

    monkeypatch.setattr('app.tools.repository_lookup.settings.repository_push_author_name', 'WEGA Build AI')
    monkeypatch.setattr('app.tools.repository_lookup.settings.repository_push_author_email', 'wega-build-ai@local')
    client = RepositoryLookupClient()

    first_result = client._push_file_with_git(
        str(remote_path),
        'main',
        'harness/pipeline.yaml',
        'pipeline:\n  name: demo\n',
        'Add generated Harness pipeline',
        {},
    )
    second_result = client._push_file_with_git(
        str(remote_path),
        'main',
        'harness/pipeline.yaml',
        'pipeline:\n  name: demo\n',
        'Add generated Harness pipeline',
        {},
    )

    assert first_result.status == 'committed'
    assert first_result.commit_sha
    assert second_result.status == 'noop'
    assert second_result.commit_sha == first_result.commit_sha

    _run_git(['clone', '--branch', 'main', str(remote_path), str(inspect_path)], cwd=str(tmp_path))
    assert (inspect_path / 'harness' / 'pipeline.yaml').read_text(encoding='utf-8') == 'pipeline:\n  name: demo\n'
    assert _run_git(['log', '-1', '--pretty=%s'], cwd=str(inspect_path)) == 'Add generated Harness pipeline'

    asyncio.run(client.close())