"""Strict global registry configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from .errors import ContractError, RegistryConfigNotFound
from .model import RegistryConfig, RegistrySet


def default_config_path() -> Path:
    return Path(os.environ.get("K_DASH_CONFIG", "~/.config/k-dash.yaml")).expanduser()


def _expect_keys(value: dict[str, Any], allowed: set[str], stage: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ContractError("unknown configuration fields", stage=stage, context={"fields": sorted(unknown)})


def load_registry_set(path: Path | None = None) -> RegistrySet:
    config_path = path or default_config_path()
    if not config_path.is_file():
        raise RegistryConfigNotFound(
            "registry configuration does not exist",
            stage="registry-config",
            context={"path": str(config_path)},
        )
    raw = yaml.safe_load(config_path.read_text())
    if not isinstance(raw, dict):
        raise ContractError("configuration must be a mapping", stage="registry-config")
    _expect_keys(raw, {"schema_version", "registries"}, "registry-config")
    if raw.get("schema_version") != 1:
        raise ContractError("unsupported schema_version", stage="registry-config")
    entries = raw.get("registries")
    if not isinstance(entries, list) or not entries:
        raise ContractError("registries must be a non-empty list", stage="registry-config")

    registries: list[RegistryConfig] = []
    names: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ContractError("registry entry must be a mapping", stage="registry-config")
        _expect_keys(
            entry,
            {"name", "url", "repository_prefix", "primary", "verify_tls", "ca_bundle", "auth"},
            f"registry-config[{index}]",
        )
        name = entry.get("name")
        url = entry.get("url")
        prefix = entry.get("repository_prefix")
        if not all(isinstance(item, str) and item for item in (name, url, prefix)):
            raise ContractError("name, url and repository_prefix are required", stage="registry-config")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
            raise ContractError("registry url must contain only scheme and host", stage="registry-config")
        if name in names:
            raise ContractError("registry names must be unique", stage="registry-config", context={"name": name})
        names.add(name)
        auth = entry.get("auth", {"type": "anonymous"})
        if not isinstance(auth, dict) or auth.get("type") not in {"anonymous", "basic", "docker"}:
            raise ContractError("unsupported registry auth", stage="registry-config", context={"name": name})
        auth_fields = {
            "anonymous": {"type"},
            "basic": {"type", "username", "password", "username_env", "password_env"},
            "docker": {"type", "config_path"},
        }[auth["type"]]
        auth_unknown = set(auth) - auth_fields
        if auth_unknown:
            raise ContractError(
                "unknown registry auth fields",
                stage="registry-config",
                context={"name": name, "fields": sorted(auth_unknown)},
            )
        registries.append(
            RegistryConfig(
                name=name,
                url=url.rstrip("/"),
                repository_prefix=prefix.strip("/"),
                primary=entry.get("primary") is True,
                verify_tls=entry.get("verify_tls", True) is not False,
                ca_bundle=entry.get("ca_bundle"),
                auth=auth,
            )
        )
    if sum(registry.primary for registry in registries) != 1:
        raise ContractError("exactly one primary registry is required", stage="registry-config")
    return RegistrySet(tuple(registries))
