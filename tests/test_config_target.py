from __future__ import annotations

from pathlib import Path

import pytest

from k_dash.config import load_registry_set
from k_dash.errors import ContractError
from k_dash.target import normalize_cc, normalize_cuda_version


def test_registry_order_and_primary(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """schema_version: 1
registries:
  - name: primary
    url: https://registry.example
    repository_prefix: k-dash
    primary: true
    auth: {type: anonymous}
  - name: secondary
    url: https://mirror.example
    repository_prefix: k-dash
    primary: false
    auth: {type: anonymous}
"""
    )
    registries = load_registry_set(path)
    assert registries.primary.name == "primary"
    assert [item.name for item in registries.secondaries] == ["secondary"]


def test_registry_unknown_field_fails(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("schema_version: 1\nregistries: []\nextra: true\n")
    with pytest.raises(ContractError):
        load_registry_set(path)


def test_registry_auth_unknown_field_fails(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """schema_version: 1
registries:
  - name: primary
    url: https://registry.example
    repository_prefix: k-dash
    primary: true
    auth: {type: anonymous, password: forbidden}
"""
    )
    with pytest.raises(ContractError, match="unknown registry auth fields"):
        load_registry_set(path)


def test_target_normalization() -> None:
    assert normalize_cuda_version("12.8.1") == "12.8"
    assert normalize_cc("sm_90a") == "sm_90a"
    with pytest.raises(ContractError):
        normalize_cc("sm_90")
