from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from k_dash.model import RegistryConfig
from k_dash.oci import OCIClient
from k_dash.errors import RegistryAccessFailure
import requests
import pytest


def test_docker_credential_helper_is_supported(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"credHelpers": {"registry.example": "test"}}))
    registry = RegistryConfig(
        name="primary",
        url="https://registry.example",
        repository_prefix="kernels",
        primary=True,
        verify_tls=True,
        ca_bundle=None,
        auth={"type": "docker", "config_path": str(config_path)},
    )
    monkeypatch.setattr("k_dash.oci.shutil.which", lambda _: "/usr/bin/docker-credential-test")

    def run(command, **kwargs):
        assert command == ["/usr/bin/docker-credential-test", "get"]
        assert kwargs["input"] == "registry.example\n"
        return SimpleNamespace(stdout='{"Username":"robot","Secret":"secret"}')

    monkeypatch.setattr("k_dash.oci.subprocess.run", run)
    assert OCIClient._resolve_basic_auth(registry) == ("robot", "secret")


def test_registry_transport_errors_do_not_leak_secrets(monkeypatch) -> None:
    registry = RegistryConfig(
        name="primary",
        url="https://registry.example",
        repository_prefix="kernels",
        primary=True,
        verify_tls=True,
        ca_bundle=None,
        auth={"type": "basic", "username": "robot", "password": "super-secret"},
    )
    client = OCIClient(registry, "owner/kernel")

    def fail(*_args, **_kwargs):
        raise requests.RequestException("transport included super-secret")

    monkeypatch.setattr(client.session, "request", fail)
    with pytest.raises(RegistryAccessFailure) as caught:
        client._request("GET", "https://registry.example/v2/")
    assert "super-secret" not in str(caught.value)


@pytest.mark.parametrize('setting', ['unset', 'empty', 'custom', 'explicit'])
def test_docker_config_path_precedence(tmp_path, monkeypatch, setting):
    import base64

    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.delenv('DOCKER_CONFIG', raising=False)
    default = tmp_path / '.docker' / 'config.json'
    custom = tmp_path / 'custom' / 'config.json'
    explicit = tmp_path / 'explicit.json'
    for path, username in [(default, 'default'), (custom, 'custom'), (explicit, 'explicit')]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'auths': {'registry.example': {
            'auth': base64.b64encode(f'{username}:secret'.encode()).decode(),
        }}}))
    auth = {'type': 'docker'}
    expected = 'default'
    if setting == 'empty':
        monkeypatch.setenv('DOCKER_CONFIG', '')
    elif setting in {'custom', 'explicit'}:
        monkeypatch.setenv('DOCKER_CONFIG', str(custom.parent))
        expected = 'custom'
    if setting == 'explicit':
        auth['config_path'] = str(explicit)
        expected = 'explicit'
    registry = RegistryConfig('test', 'https://registry.example', 'kernels', True, True, None, auth)
    assert OCIClient._resolve_basic_auth(registry) == (expected, 'secret')


@pytest.mark.parametrize('helper_key', ['credsStore', 'credHelpers'])
def test_docker_helpers_use_docker_config(tmp_path, monkeypatch, helper_key):
    monkeypatch.setenv('DOCKER_CONFIG', str(tmp_path))
    entry = 'test' if helper_key == 'credsStore' else {'registry.example': 'test'}
    (tmp_path / 'config.json').write_text(json.dumps({helper_key: entry}))
    registry = RegistryConfig('test', 'https://registry.example', 'kernels', True, True, None, {'type': 'docker'})
    monkeypatch.setattr('k_dash.oci.shutil.which', lambda _: '/bin/docker-credential-test')
    def run(command, **kwargs):
        assert command == ['/bin/docker-credential-test', 'get']
        assert kwargs['input'] == 'registry.example\n'
        return SimpleNamespace(stdout='{"Username":"robot","Secret":"secret"}')
    monkeypatch.setattr('k_dash.oci.subprocess.run', run)
    assert OCIClient._resolve_basic_auth(registry) == ('robot', 'secret')


def test_missing_docker_login_has_actionable_error(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCKER_CONFIG', str(tmp_path))
    (tmp_path / 'config.json').write_text('{"auths": {}}')
    registry = RegistryConfig('test', 'https://registry.example', 'kernels', True, True, None, {'type': 'docker'})
    with pytest.raises(RegistryAccessFailure, match='docker login'):
        OCIClient._resolve_basic_auth(registry)
