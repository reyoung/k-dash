from __future__ import annotations

import json
from pathlib import Path

import pytest

from k_dash.errors import ContractError
from k_dash.project import load_project, materialize_source_tree, source_archive
from k_dash.templates import init_project


def test_init_and_source_archive_are_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "kernel"
    init_project("owner/kernel", root, "cpp", None)
    manifest, schema = load_project(root)
    assert manifest.name == "owner/kernel"
    assert manifest.license is None
    assert schema["properties"]["block_size"]["default"] == 256
    build_nix = (root / "build.nix").read_text()
    assert "mkTvmFfiKernel =" in build_nix
    assert "kdlib" not in build_nix
    assert source_archive(root) == source_archive(root)


def test_build_tree_contains_only_nonignored_files(tmp_path: Path) -> None:
    root = tmp_path / "kernel"
    init_project("owner/kernel", root, "cpp", None)
    (root / "ignored.bin").write_bytes(b"not a build input")
    (root / ".k-dash-ignore").write_text((root / ".k-dash-ignore").read_text() + "ignored.bin\n")
    destination = tmp_path / "stage"
    materialize_source_tree(root, destination)
    assert not (destination / "ignored.bin").exists()
    assert (destination / "build.nix").is_file()


def test_init_refuses_nonempty_directory(tmp_path: Path) -> None:
    root = tmp_path / "kernel"
    root.mkdir()
    (root / "mine.txt").write_text("preserve")
    with pytest.raises(ContractError):
        init_project("owner/kernel", root, "cpp", None)
    assert (root / "mine.txt").read_text() == "preserve"


def test_cutedsl_init_is_a_real_locked_aot_project(tmp_path: Path) -> None:
    root = tmp_path / "cutedsl"
    init_project("owner/cutedsl", root, "cutedsl", None)
    build_nix = (root / "build.nix").read_text()
    source = (root / "src/kernel.py").read_text()
    flake = (root / "flake.nix").read_text()
    assert "cutedslModule" in build_nix
    assert '"cutedsl-runtime"' in build_nix
    assert "not yet implemented" not in build_nix
    assert "@cute.kernel" in source and "export_to_c" in source
    assert "cutedsl-toolchain" in flake


def test_required_file_cannot_be_ignored(tmp_path: Path) -> None:
    root = tmp_path / "kernel"
    init_project("owner/kernel", root, "cpp", None)
    (root / ".k-dash-ignore").write_text("README.md\n")
    with pytest.raises(ContractError):
        source_archive(root)


@pytest.mark.parametrize('pattern', ['build', 'build/', 'build/**', '/build/'])
def test_ignored_directory_does_not_change_source_digest(tmp_path, pattern):
    from k_dash.project import source_files

    root = tmp_path / 'kernel'
    init_project('owner/kernel', root, 'cpp', None)
    (root / '.k-dash-ignore').write_text(pattern + '\n*.log\n')
    before = source_archive(root)
    nested = root / 'build' / 'nested'
    nested.mkdir(parents=True)
    (nested / 'kernel.so').write_bytes(b'local build')
    (root / 'debug.log').write_text('log')
    assert source_archive(root) == before
    assert not any(p.relative_to(root).parts[0] == 'build' for p in source_files(root))
    (root / 'src' / 'build_helpers.cu').write_text('// included')
    assert source_archive(root) != before


def test_directory_exclusion_prunes_walk_and_does_not_follow_symlinks(tmp_path, monkeypatch):
    import os
    from k_dash.project import source_files

    root = tmp_path / 'kernel'
    init_project('owner/kernel', root, 'cpp', None)
    (root / '.k-dash-ignore').write_text('build/**\n')
    (root / 'build').mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret').write_text('excluded')
    (root / 'link').symlink_to(outside, target_is_directory=True)
    walk = os.walk
    visited = []
    def observing_walk(*args, **kwargs):
        for entry in walk(*args, **kwargs):
            visited.append(Path(entry[0]))
            yield entry
    monkeypatch.setattr('k_dash.project.os.walk', observing_walk)
    files = source_files(root)
    assert root / 'build' not in visited
    assert not any('link' in p.relative_to(root).parts for p in files)
