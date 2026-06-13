from pathlib import Path

import pytest

from cara.core.config import Settings
from cara.core.errors import NotFoundError
from cara.services.github_service import (
    EXCLUDED_DIRECTORIES,
    GitHubService,
)


def _make_service(tmp_path: Path) -> GitHubService:
    settings = Settings(_env_file=None)
    return GitHubService(client=None, token_provider=lambda: "token", settings=settings)


def test_collect_context_files_skips_excluded_directories(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "main.py").write_text("print('hi')\n")
    (repo / "node_modules" / "left-pad").mkdir(parents=True)
    (repo / "node_modules" / "left-pad" / "index.js").write_text("module.exports = 1\n")
    (repo / ".git" / "objects").mkdir(parents=True)
    (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "x.cpython-311.pyc").write_text("noise")

    service = _make_service(tmp_path)
    files = service.collect_context_files(
        repository_root=repo,
        max_files=100,
        max_file_bytes=128_000,
    )
    rels = [p.relative_to(repo).as_posix() for p in files]

    assert rels == ["src/main.py"]
    assert all(part not in EXCLUDED_DIRECTORIES for f in files for part in f.parts)


def test_collect_context_files_prioritizes_source_over_docs_when_truncating(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "docs").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "core.py").write_text("def f(): pass\n")
    (repo / "src" / "api.ts").write_text("export const a = 1\n")
    (repo / "docs" / "readme.md").write_text("# readme\n")
    (repo / "docs" / "guide.md").write_text("guide\n")
    (repo / "tests" / "test_core.py").write_text("def test(): pass\n")

    service = _make_service(tmp_path)
    files = service.collect_context_files(
        repository_root=repo,
        max_files=2,
        max_file_bytes=128_000,
    )
    rels = [p.relative_to(repo).as_posix() for p in files]

    assert len(rels) == 2
    assert all(r.startswith("src/") for r in rels), rels


def test_collect_context_files_demotes_test_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "core.py").write_text("def f(): pass\n")
    (repo / "tests" / "test_core.py").write_text("def t(): pass\n")

    service = _make_service(tmp_path)
    files = service.collect_context_files(
        repository_root=repo,
        max_files=1,
        max_file_bytes=128_000,
    )
    assert [p.relative_to(repo).as_posix() for p in files] == ["src/core.py"]


def test_collect_context_files_respects_size_limit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    big = repo / "huge.py"
    big.write_text("x = 1\n" * 5000)
    small = repo / "small.py"
    small.write_text("y = 2\n")

    service = _make_service(tmp_path)
    files = service.collect_context_files(
        repository_root=repo,
        max_files=10,
        max_file_bytes=200,
    )
    rels = [p.relative_to(repo).as_posix() for p in files]
    assert "small.py" in rels
    assert "huge.py" not in rels


def test_collect_context_files_unknown_folder_raises(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "x.py").write_text("pass\n")

    service = _make_service(tmp_path)
    with pytest.raises(NotFoundError):
        service.collect_context_files(
            repository_root=repo,
            max_files=10,
            max_file_bytes=128_000,
            folder="missing",
        )


def test_is_text_file_streams_only_first_2k(tmp_path: Path) -> None:
    target = tmp_path / "big.py"
    target.write_text("# header\n" + ("x = 1\n" * 100_000))

    service = _make_service(tmp_path)
    # Should return True without reading the entire file.
    assert service._is_text_file(target) is True


def test_is_text_file_detects_binary(tmp_path: Path) -> None:
    target = tmp_path / "bin"
    target.write_bytes(b"\x00\x01\x02 binary stuff")
    service = _make_service(tmp_path)
    assert service._is_text_file(target) is False
