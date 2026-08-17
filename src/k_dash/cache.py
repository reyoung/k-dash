"""Content-addressed cache with per-BuildKey advisory locking."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .canonical import canonical_json
from .errors import ArtifactIntegrityError
from .project import extract_source_archive


class Cache:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(os.environ.get("K_DASH_CACHE_DIR", "~/.cache/k-dash")).expanduser()
        for child in ("releases", "builds", "resolutions", "locks", "tmp"):
            (self.root / child).mkdir(parents=True, exist_ok=True)

    def build_dir(self, build_key: str) -> Path:
        return self.root / "builds" / build_key.removeprefix("sha256:")

    def release_dir(self, digest: str) -> Path:
        return self.root / "releases" / digest.removeprefix("sha256:")

    def get_release(self, digest: str) -> tuple[dict[str, Any], bytes, Path] | None:
        path = self.release_dir(digest)
        config_path = path / "config.json"
        archive_path = path / "source.tar.zst"
        source_path = path / "source"
        if not config_path.is_file() or not archive_path.is_file() or not source_path.is_dir():
            return None
        config = json.loads(config_path.read_text())
        if config.get("source", {}).get("digest") is None:
            raise ArtifactIntegrityError("cached Release config is incomplete", stage="cache")
        return config, archive_path.read_bytes(), source_path

    def commit_release(self, digest: str, config: dict[str, Any], source_archive: bytes) -> Path:
        destination = self.release_dir(digest)
        if destination.exists():
            return destination
        temporary = Path(tempfile.mkdtemp(prefix="release-", dir=self.root / "tmp"))
        try:
            (temporary / "config.json").write_bytes(canonical_json(config))
            (temporary / "source.tar.zst").write_bytes(source_archive)
            extract_source_archive(source_archive, temporary / "source")
            try:
                temporary.replace(destination)
            except FileExistsError:
                pass
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return destination

    def get_build(self, build_key: str) -> tuple[dict[str, Any], Path] | None:
        path = self.build_dir(build_key)
        config_path = path / "config.json"
        module_path = path / "kernel.so"
        if not config_path.is_file() or not module_path.is_file():
            return None
        config = json.loads(config_path.read_text())
        if config.get("build_key") != build_key:
            raise ArtifactIntegrityError("cached BuildKey mismatch", stage="cache", context={"path": str(path)})
        return config, module_path

    def commit_build(self, build_key: str, config: dict[str, Any], kernel_so: bytes) -> Path:
        destination = self.build_dir(build_key)
        if destination.exists():
            return destination
        temporary = Path(tempfile.mkdtemp(prefix="build-", dir=self.root / "tmp"))
        try:
            (temporary / "config.json").write_bytes(canonical_json(config))
            (temporary / "kernel.so").write_bytes(kernel_so)
            (temporary / "kernel.so").chmod(0o755)
            try:
                temporary.replace(destination)
            except FileExistsError:
                pass
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return destination

    @contextlib.contextmanager
    def build_lock(self, build_key: str) -> Iterator[None]:
        path = self.root / "locks" / (build_key.removeprefix("sha256:") + ".lock")
        with path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def resolution_path(self, registry: str, kernel: str, version: str) -> Path:
        safe_version = version.replace("/", "%2F")
        return self.root / "resolutions" / registry / kernel / f"{safe_version}.json"

    def put_resolution(self, registry: str, kernel: str, version: str, digest: str) -> None:
        path = self.resolution_path(registry, kernel, version)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(canonical_json({"release_digest": digest}))
        temporary.replace(path)

    def get_resolution(self, registry: str, kernel: str, version: str) -> str | None:
        path = self.resolution_path(registry, kernel, version)
        if not path.is_file():
            return None
        return json.loads(path.read_text()).get("release_digest")

    def size(self) -> int:
        return sum(path.stat().st_size for path in self.root.rglob("*") if path.is_file())

    def clean(self) -> None:
        for child in ("releases", "builds", "resolutions", "tmp"):
            path = self.root / child
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)
