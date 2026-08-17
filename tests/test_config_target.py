from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from k_dash.config import load_registry_set
from k_dash.errors import ContractError
from k_dash import target
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


def test_target_detection_nvcc_wins_and_uses_logical_gpu_zero(monkeypatch) -> None:
    seen: list[int] = []

    class Cuda:
        @staticmethod
        def is_available():
            return True

        @staticmethod
        def get_device_capability(index):
            seen.append(index)
            return 10, 0

    fake_torch = SimpleNamespace(version=SimpleNamespace(cuda="13.0"), cuda=Cuda())
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(target, "_nvcc_version", lambda: "12.8")
    monkeypatch.setattr(target.platform, "system", lambda: "Linux")
    monkeypatch.setattr(target.platform, "machine", lambda: "x86_64")
    detected = target.detect_target()
    assert detected.cuda == "12.8" and detected.cc == "sm_100a" and seen == [0]


def test_target_detection_falls_back_to_torch_and_uses_sm90a(monkeypatch) -> None:
    fake_torch = SimpleNamespace(
        version=SimpleNamespace(cuda="12.8.1"),
        cuda=SimpleNamespace(is_available=lambda: True, get_device_capability=lambda _: (9, 0)),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(target, "_nvcc_version", lambda: None)
    monkeypatch.setattr(target.platform, "system", lambda: "Linux")
    monkeypatch.setattr(target.platform, "machine", lambda: "aarch64")
    detected = target.detect_target()
    assert detected.cuda == "12.8" and detected.cc == "sm_90a" and detected.arch == "aarch64"
