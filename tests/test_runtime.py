from __future__ import annotations

from pathlib import Path

import pytest

from k_dash.cache import Cache
from k_dash.errors import ArtifactIntegrityError, ArtifactNotFound, OfflineCacheMiss, RegistryAccessFailure
from k_dash.model import RegistryConfig, RegistrySet, TargetSpec
from k_dash.project import source_archive
from k_dash.templates import init_project
from k_dash import runtime


def _registry(name: str, primary: bool) -> RegistryConfig:
    return RegistryConfig(name, f"https://{name}.example", "kernels", primary, True, None, {"type": "anonymous"})


def test_release_access_failure_fails_over_but_dev_does_not(tmp_path: Path, monkeypatch) -> None:
    primary, secondary = _registry("primary", True), _registry("secondary", False)
    registries = RegistrySet((primary, secondary))

    class Client:
        def __init__(self, registry):
            self.registry = registry

        def get_manifest(self, reference):
            if self.registry.primary:
                raise RegistryAccessFailure("down", stage="test")
            return "sha256:" + "1" * 64, b"{}", {}

    monkeypatch.setattr(runtime, "_client", lambda registry, _: Client(registry))
    digest, authority = runtime.resolve_release(registries, "owner/kernel", "1", Cache(tmp_path / "cache"))
    assert digest == "sha256:" + "1" * 64 and authority == secondary
    with pytest.raises(RegistryAccessFailure):
        runtime.resolve_release(registries, "owner/kernel", "dev-main", Cache(tmp_path / "dev-cache"))


def test_primary_404_is_authoritative_and_content_errors_fail_closed(monkeypatch) -> None:
    primary, secondary = _registry("primary", True), _registry("secondary", False)
    registries = RegistrySet((primary, secondary))
    calls: list[str] = []

    class Missing:
        def pull(self, *_args, **_kwargs):
            calls.append("primary")
            raise ArtifactNotFound("missing", stage="test")

    monkeypatch.setattr(runtime, "_client", lambda *_: Missing())
    artifact, authority = runtime._binary_registry(registries, primary, "owner/kernel", "build-key")
    assert artifact is None and authority == primary and calls == ["primary"]

    class Corrupt:
        def pull(self, *_args, **_kwargs):
            raise ArtifactIntegrityError("corrupt", stage="test")

    monkeypatch.setattr(runtime, "_client", lambda *_: Corrupt())
    with pytest.raises(ArtifactIntegrityError):
        runtime._binary_registry(registries, primary, "owner/kernel", "build-key")


def test_offline_source_jit_and_offline_miss(tmp_path: Path, monkeypatch) -> None:
    cache = Cache(tmp_path / "cache")
    release = "sha256:" + "2" * 64
    root = tmp_path / "project"
    init_project("owner/kernel", root, "cpp", None)
    archive = source_archive(root)
    cache.commit_release(release, {"source": {"digest": "sha256:x"}}, archive)
    monkeypatch.setenv("K_DASH_OFFLINE", "1")
    monkeypatch.setattr(runtime, "local_jit", lambda *_: (b"ELF", {"mode": "local-jit"}))
    monkeypatch.setattr(runtime, "validate_kernel_so", lambda *_: None)
    monkeypatch.setattr(runtime, "cxx_runtime_requirement", lambda *_: None)
    key, path = runtime.materialize(
        RegistrySet((_registry("primary", True),)),
        _registry("primary", True),
        "owner/kernel",
        release,
        {"block_size": 256},
        TargetSpec("linux", "x86_64", "12.8", "sm_90a"),
        cache,
    )
    assert path.read_bytes() == b"ELF" and cache.get_build(key) is not None
    with pytest.raises(OfflineCacheMiss):
        runtime.materialize(
            RegistrySet((_registry("primary", True),)),
            _registry("primary", True),
            "owner/kernel",
            "sha256:" + "3" * 64,
            {},
            TargetSpec("linux", "x86_64", "12.8", "sm_90a"),
            Cache(tmp_path / "empty"),
        )
