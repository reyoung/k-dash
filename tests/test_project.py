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


def test_required_file_cannot_be_ignored(tmp_path: Path) -> None:
    root = tmp_path / "kernel"
    init_project("owner/kernel", root, "cpp", None)
    (root / ".k-dash-ignore").write_text("README.md\n")
    with pytest.raises(ContractError):
        source_archive(root)
