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
