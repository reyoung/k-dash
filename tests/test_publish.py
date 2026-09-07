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


@pytest.mark.parametrize('failure_stage', ['config', 'credentials', 'build'])
def test_publish_failure_prevents_upload(tmp_path, monkeypatch, failure_stage):
    from k_dash.errors import KDashError
    from k_dash.templates import init_project

    root = tmp_path / 'kernel'
    init_project('owner/kernel', root, 'cpp', None)
    args = tmp_path / 'args.json'
    args.write_text('{}')
    calls = []
    def load_config():
        calls.append('config')
        if failure_stage == 'config':
            raise RegistryAccessFailure('missing config', stage='registry-config')
        return RegistrySet((_registry('test', True),))
    class Client:
        def __init__(self, *_):
            calls.append('credentials')
            if failure_stage == 'credentials':
                raise RegistryAccessFailure('missing login', stage='registry-auth')
        def push(self, *_):
            pytest.fail('must not upload')
    def build(*_, **kwargs):
        calls.append('build')
        raise KDashError('compile failed', stage='docker-aot')
    monkeypatch.setattr('k_dash.publish.load_registry_set', load_config)
    monkeypatch.setattr('k_dash.publish.OCIClient', Client)
    monkeypatch.setattr('k_dash.publish.docker_aot', build)
    with pytest.raises(KDashError):
        publish_release(root, version='v0.1.0', cuda='13.0', cc='sm_90a', args_files=[args])
    expected = ['config', 'credentials', 'build']
    assert calls == expected[:expected.index(failure_stage) + 1]


@pytest.mark.parametrize("backend", ["docker", "nix"])
def test_multiple_cuda_targets_deduplicate_and_build_before_upload(tmp_path, monkeypatch, backend):
    from k_dash.templates import init_project
    from k_dash.errors import KDashError

    root = tmp_path / 'kernel'
    init_project('owner/kernel', root, 'cpp', None)
    args = tmp_path / 'args.json'
    args.write_text('{}')
    seen = []
    monkeypatch.setattr('k_dash.publish.load_registry_set', lambda: RegistrySet((_registry('test', True),)))
    class Client:
        def __init__(self, *_): pass
        def push(self, *_): pytest.fail('must finish both builds before uploading')
        def get_manifest(self, *_): pytest.fail('must finish builds first')
    monkeypatch.setattr('k_dash.publish.OCIClient', Client)
    def build(_, spec, **kwargs):
        seen.append((spec.release_digest, spec.target['cuda']))
        if spec.target['cuda'] == '13.0':
            raise KDashError('second build failed', stage='docker-aot')
        return b'ELF', {}
    monkeypatch.setattr('k_dash.publish.' + ('docker_aot' if backend == 'docker' else 'nix_aot'), build)
    monkeypatch.setattr('k_dash.publish.build_objects', lambda *_, **kw: ({}, b'{}', b'layer', b'{}', 'sha256:x'))
    monkeypatch.setattr('k_dash.publish.infer_host_dependencies', lambda _: [])
    monkeypatch.setattr('k_dash.publish.cxx_runtime_requirement', lambda _: None)
    monkeypatch.setattr('k_dash.publish.validate_kernel_so', lambda *_: None)
    with pytest.raises(KDashError, match='second build failed'):
        publish_release(root, version='v0.1.0', cuda=['12.8', '12.8', '13.0'], cc='sm_90a', args_files=[args, args], backend=backend)
    assert [cuda for _, cuda in seen] == ['12.8', '13.0']
    assert len({release for release, _ in seen}) == 1


def test_publish_cli_accepts_repeated_cuda_versions():
    from k_dash.cli import _parser
    args = _parser().parse_args(['publish', '--version', 'v1', '--cuda-version', '12.8', '--cuda-version', '13.0'])
    assert args.cuda_version == ['12.8', '13.0']


def test_multiple_cuda_targets_publish_two_binaries_and_one_release(tmp_path, monkeypatch):
    from k_dash.canonical import digest_bytes
    from k_dash.templates import init_project

    root = tmp_path / 'kernel'
    init_project('owner/kernel', root, 'cpp', None)
    args = tmp_path / 'args.json'
    args.write_text('{}')
    events = []
    original_source = (root / 'src/kernel.cu').read_text()
    monkeypatch.setenv('K_DASH_CACHE_DIR', str(tmp_path / 'cache'))
    registry = _registry('test', True)
    monkeypatch.setattr('k_dash.publish.load_registry_set', lambda: RegistrySet((registry,)))
    class Client:
        def __init__(self, config, _): self.config = config
        def get_manifest(self, *_): raise ArtifactNotFound('missing', stage='test')
        def push(self, reference, config, layers, manifest):
            events.append(('push', reference))
            return digest_bytes(manifest)
    monkeypatch.setattr('k_dash.publish.OCIClient', Client)
    def build(source, spec, **kwargs):
        events.append(('build', spec.target['cuda']))
        assert (source / 'src/kernel.cu').read_text() == original_source
        (root / 'src/kernel.cu').write_text('// changed during first build')
        assert spec.target['tvm_ffi'] == '0.1.9'
        return b'ELF' + spec.target['cuda'].encode(), {'mode': 'test'}
    monkeypatch.setattr('k_dash.publish.docker_aot', build)
    monkeypatch.setattr('k_dash.publish.infer_host_dependencies', lambda _: [])
    monkeypatch.setattr('k_dash.publish.cxx_runtime_requirement', lambda _: None)
    monkeypatch.setattr('k_dash.publish.validate_kernel_so', lambda *_: None)
    result = publish_release(root, version='v0.1.0', cuda=['12.8', '13.0'], cc='sm_90a',
                             tvm_ffi='0.1.9', args_files=[args])
    assert len(result['builds']) == 2
    assert events[:2] == [('build', '12.8'), ('build', '13.0')]
    assert len(events) == 5
    assert all(tag.startswith('build-') for _, tag in events[2:4])
    assert events[-1] == ('push', 'release-v0.1.0')
