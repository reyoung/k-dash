"""Kernel project validation and deterministic source packaging."""

from __future__ import annotations

import fnmatch
import io
import os
import re
import tarfile
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

import zstandard

from .canonical import canonical_json, digest_bytes, loads_no_duplicates
from .errors import ContractError
from .model import ProjectManifest

REQUIRED_ROOT_FILES = (
    "k-dash.toml",
    "README.md",
    "build.nix",
    "flake.nix",
    "flake.lock",
    "args.schema.json",
    ".k-dash-ignore",
)
KERNEL_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*/[a-z0-9]+(?:[._-][a-z0-9]+)*$")


def validate_kernel_name(name: str) -> str:
    if not isinstance(name, str) or not KERNEL_RE.fullmatch(name):
        raise ContractError("kernel must be a lowercase owner/kernel path", stage="project", context={"name": name})
    return name


def load_project(root: Path | str = ".") -> tuple[ProjectManifest, dict[str, Any]]:
    path = Path(root).resolve()
    missing = [name for name in REQUIRED_ROOT_FILES if not (path / name).is_file()]
    if missing:
        raise ContractError("required project files are missing", stage="project", context={"files": missing})
    if not (path / "README.md").read_text().strip():
        raise ContractError("README.md must not be empty", stage="project")
    try:
        raw = tomllib.loads((path / "k-dash.toml").read_text())
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ContractError("invalid k-dash.toml", stage="project") from error
    allowed = {"format-version", "name", "build-api", "license"}
    unknown = set(raw) - allowed
    if unknown:
        raise ContractError("unknown manifest fields", stage="project", context={"fields": sorted(unknown)})
    if raw.get("format-version") != 1 or raw.get("build-api") != 1:
        raise ContractError("unsupported project protocol version", stage="project")
    name = validate_kernel_name(raw.get("name"))
    license_value = raw.get("license")
    if license_value is not None and not isinstance(license_value, str):
        raise ContractError("license must be a string", stage="project")
    try:
        schema = loads_no_duplicates((path / "args.schema.json").read_text(), stage="project")
    except (ContractError, UnicodeDecodeError) as error:
        raise ContractError("invalid args.schema.json", stage="project") from error
    if not isinstance(schema, dict):
        raise ContractError("args.schema.json must be an object", stage="project")
    return ProjectManifest(name=name, license=license_value), schema


def _ignore_patterns(root: Path) -> list[str]:
    patterns = [".git", ".git/**", "__pycache__", "**/__pycache__", "*.pyc"]
    for line in (root / ".k-dash-ignore").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line.removeprefix("/"))
    for required in REQUIRED_ROOT_FILES:
        if any(fnmatch.fnmatch(required, pattern) for pattern in patterns):
            raise ContractError(
                "a required root file is excluded by .k-dash-ignore",
                stage="project",
                context={"file": required},
            )
    return patterns


def source_files(root: Path | str = ".") -> list[Path]:
    path = Path(root).resolve()
    load_project(path)
    patterns = _ignore_patterns(path)
    selected: list[Path] = []
    for candidate in path.rglob("*"):
        if not candidate.is_file() or candidate.is_symlink():
            continue
        relative = candidate.relative_to(path).as_posix()
        if any(fnmatch.fnmatch(relative, pattern) for pattern in patterns):
            continue
        selected.append(candidate)
    return sorted(selected, key=lambda item: item.relative_to(path).as_posix().encode())


def source_archive(root: Path | str = ".") -> bytes:
    path = Path(root).resolve()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for candidate in source_files(path):
            relative = candidate.relative_to(path).as_posix()
            info = tarfile.TarInfo(relative)
            payload = candidate.read_bytes()
            info.size = len(payload)
            info.mode = 0o755 if os.access(candidate, os.X_OK) else 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(payload))
    return zstandard.ZstdCompressor(level=19, write_checksum=True).compress(stream.getvalue())


def extract_source_archive(payload: bytes, destination: Path) -> None:
    try:
        raw = zstandard.ZstdDecompressor().decompress(payload)
    except zstandard.ZstdError as error:
        raise ContractError("invalid zstd source archive", stage="source-extract") from error
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive.getmembers():
            pure = PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts or not member.isfile():
                raise ContractError("unsafe source archive member", stage="source-extract", context={"path": member.name})
            target = destination.joinpath(*pure.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ContractError("source archive member has no data", stage="source-extract")
            target.write_bytes(source.read())
            target.chmod(member.mode & 0o777)


def materialize_source_tree(root: Path | str, destination: Path) -> None:
    """Create a clean build tree containing only Kernel Source Package files."""
    if destination.exists() and any(destination.iterdir()):
        raise ContractError("build staging directory must be empty", stage="source-stage")
    extract_source_archive(source_archive(root), destination)


def release_objects(root: Path | str, version: str) -> tuple[dict[str, Any], bytes, bytes, bytes, str]:
    manifest, schema = load_project(root)
    layer = source_archive(root)
    layer_digest = digest_bytes(layer)
    config = {
        "protocol_version": 1,
        "kernel": manifest.name,
        "version": version,
        "args_schema": schema,
        "source": {"digest": layer_digest, "size": len(layer)},
    }
    config_bytes = canonical_json(config)
    config_digest = digest_bytes(config_bytes)
    oci_manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "artifactType": "application/vnd.k-dash.release.v1",
        "config": {
            "mediaType": "application/vnd.k-dash.release.config.v1+json",
            "digest": config_digest,
            "size": len(config_bytes),
        },
        "layers": [{
            "mediaType": "application/vnd.k-dash.source.v1.tar+zstd",
            "digest": layer_digest,
            "size": len(layer),
        }],
    }
    manifest_bytes = canonical_json(oci_manifest)
    return config, config_bytes, layer, manifest_bytes, digest_bytes(manifest_bytes)
