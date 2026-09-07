from types import SimpleNamespace
import sys

import pytest

from k_dash.builder import docker_aot
from k_dash.model import BuildSpec, TargetSpec
from k_dash.templates import init_project


def test_docker_builder_bounds_nofile_before_start(tmp_path, monkeypatch):
    root = tmp_path / 'kernel'
    init_project('owner/kernel', root, 'cpp', None)
    class ContainerCreated(Exception): pass
    def create(*args, **kwargs):
        limits = kwargs['ulimits']
        assert len(limits) == 1
        assert (limits[0].name, limits[0].soft, limits[0].hard) == ('nofile', 65536, 65536)
        assert kwargs['volumes'] == {'k-dash-nix-store': {'bind': '/nix', 'mode': 'rw'}}
        raise ContainerCreated
    client = SimpleNamespace(volumes=SimpleNamespace(get=lambda _: None),
                             containers=SimpleNamespace(create=create))
    monkeypatch.setitem(sys.modules, 'docker', SimpleNamespace(
        from_env=lambda: client, types=SimpleNamespace(Ulimit=lambda **kwargs: SimpleNamespace(**kwargs))))
    spec = BuildSpec('sha256:' + '0' * 64, {}, TargetSpec('linux', 'x86_64', '13.0', 'sm_90a').as_dict())
    with pytest.raises(ContainerCreated):
        docker_aot(root, spec)


def test_nix_aot_does_not_forward_registry_credentials(tmp_path, monkeypatch):
    from k_dash.builder import nix_aot
    import subprocess
    monkeypatch.setenv("REGISTRY_PASSWORD", "secret")
    monkeypatch.setenv("DOCKER_CONFIG", "/private/docker")
    monkeypatch.setattr("k_dash.builder.shutil.which", lambda _: "/usr/bin/nix")
    output = tmp_path / "output"
    output.mkdir()
    (output / "kernel.so").write_bytes(b"ELF")
    def run(command, **kwargs):
        assert "REGISTRY_PASSWORD" not in kwargs["env"]
        assert "DOCKER_CONFIG" not in kwargs["env"]
        assert "sandbox = false" in kwargs["env"]["NIX_CONFIG"]
        return subprocess.CompletedProcess(command, 0, str(output) + "\n")
    monkeypatch.setattr("k_dash.builder.subprocess.run", run)
    spec = BuildSpec('sha256:' + '0' * 64, {}, TargetSpec('linux', 'x86_64', '13.0', 'sm_90a').as_dict())
    data, provenance = nix_aot(tmp_path, spec)
    assert data == b"ELF"
    assert provenance["mode"] == "nix-aot"
