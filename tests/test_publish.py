from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from k_dash.errors import ArtifactIntegrityError, ArtifactNotFound, RegistryAccessFailure
from k_dash.model import ProjectManifest, RegistryConfig, RegistrySet
from k_dash.publish import _check_release_binding, publish_build, publish_release


def _registry(name: str, primary: bool) -> RegistryConfig:
    return RegistryConfig(name, f"https://{name}.example", "kernels", primary, True, None, {"type": "anonymous"})


class _Client:
    def __init__(self, digest: str):
        self.digest = digest

    def get_manifest(self, _reference):
        return self.digest, b"{}", {}


def test_immutable_version_conflicts_but_dev_can_move() -> None:
    old = "sha256:" + "1" * 64
    new = "sha256:" + "2" * 64
    with pytest.raises(ArtifactIntegrityError, match="immutable Version"):
        _check_release_binding(_Client(old), "1", new)
    _check_release_binding(_Client(old), "dev-main", new)


def test_publish_build_detects_dev_version_move(tmp_path: Path, monkeypatch) -> None:
    args = tmp_path / "args.json"
    args.write_text("{}")
    old = "sha256:" + "1" * 64
    new = "sha256:" + "2" * 64
    resolutions = iter([(old, _registry("primary", True)), (new, _registry("primary", True))])
    monkeypatch.setattr("k_dash.publish.load_project", lambda _: (ProjectManifest("owner/kernel"), {}))
    monkeypatch.setattr("k_dash.publish.load_registry_set", lambda: RegistrySet((_registry("primary", True),)))
    monkeypatch.setattr("k_dash.publish.Cache", lambda: object())
    monkeypatch.setattr("k_dash.publish.resolve_release", lambda *_: next(resolutions))
    monkeypatch.setattr(
        "k_dash.publish.pull_release",
        lambda *_: SimpleNamespace(
            config={"args_schema": {"type": "object", "additionalProperties": False}},
            layers=(b"source",),
        ),
    )
    monkeypatch.setattr("k_dash.publish.extract_source_archive", lambda _, path: path.mkdir(parents=True))
    monkeypatch.setattr("k_dash.publish.docker_aot", lambda *_args, **_kwargs: (b"ELF", {"mode": "test"}))
    monkeypatch.setattr(
        "k_dash.publish.build_objects",
        lambda *_args, **_kwargs: ({}, b"{}", b"layer", b"manifest", "sha256:" + "3" * 64),
    )
    monkeypatch.setattr("k_dash.publish.validate_kernel_so", lambda *_: None)
    monkeypatch.setattr("k_dash.publish.infer_host_dependencies", lambda *_: [])
    monkeypatch.setattr("k_dash.publish.cxx_runtime_requirement", lambda *_: None)
    with pytest.raises(ArtifactIntegrityError, match="DevVersionMoved"):
        publish_build(
            tmp_path,
            version="dev-main",
            cuda="12.8",
            cc="sm_90a",
            args_file=args,
        )


def test_multi_registry_partial_publish_is_idempotently_retryable(tmp_path: Path, monkeypatch) -> None:
    primary, secondary = _registry("primary", True), _registry("secondary", False)
    expected = "sha256:" + "4" * 64
    stored: dict[str, str] = {}
    pushes: dict[str, int] = {"primary": 0, "secondary": 0}
    fail_secondary = [True]

    class Client:
        def __init__(self, registry, _kernel):
            self.config = registry

        def get_manifest(self, reference):
            key = f"{self.config.name}:{reference}"
            if key not in stored:
                raise ArtifactNotFound("missing", stage="test")
            return stored[key], b"manifest", {}

        def push(self, reference, *_args):
            pushes[self.config.name] += 1
            if self.config.name == "secondary" and fail_secondary[0]:
                fail_secondary[0] = False
                raise RegistryAccessFailure("temporary", stage="test")
            stored[f"{self.config.name}:{reference}"] = expected
            return expected

    class DummyCache:
        def commit_release(self, *_args):
            return None

        def put_resolution(self, *_args):
            return None

    monkeypatch.setattr("k_dash.publish.load_project", lambda _: (ProjectManifest("owner/kernel"), {}))
    monkeypatch.setattr(
        "k_dash.publish._release_payloads",
        lambda *_: ({"source": {"digest": "sha256:x"}}, b"config", b"source", b"manifest", expected),
    )
    monkeypatch.setattr("k_dash.publish.load_registry_set", lambda: RegistrySet((primary, secondary)))
    monkeypatch.setattr("k_dash.publish.OCIClient", Client)
    monkeypatch.setattr("k_dash.publish.Cache", DummyCache)
    with pytest.raises(RegistryAccessFailure):
        publish_release(tmp_path, version="1")
    result = publish_release(tmp_path, version="1")
    assert result["registries"] == {"primary": expected, "secondary": expected}
    assert pushes == {"primary": 2, "secondary": 2}
