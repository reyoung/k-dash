"""Protocol dataclasses shared by build, registry and load paths."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_TVM_FFI_VERSION = "0.1.13.post3"


@dataclass(frozen=True)
class TargetSpec:
    os: str
    arch: str
    cuda: str
    cc: str
    libc: str = "manylinux_2_28"
    tvm_ffi: str = DEFAULT_TVM_FFI_VERSION

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class BuildSpec:
    release_digest: str
    args: dict[str, Any]
    target: dict[str, Any]
    buildspec_version: int = 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "buildspec_version": self.buildspec_version,
            "release_digest": self.release_digest,
            "args": self.args,
            "target": self.target,
        }


@dataclass(frozen=True)
class ProjectManifest:
    name: str
    format_version: int = 1
    build_api: int = 1
    license: str | None = None


@dataclass(frozen=True)
class RegistryConfig:
    name: str
    url: str
    repository_prefix: str
    primary: bool
    verify_tls: bool
    ca_bundle: str | None
    auth: dict[str, Any]


@dataclass(frozen=True)
class RegistrySet:
    registries: tuple[RegistryConfig, ...]

    @property
    def primary(self) -> RegistryConfig:
        return next(registry for registry in self.registries if registry.primary)

    @property
    def secondaries(self) -> tuple[RegistryConfig, ...]:
        return tuple(registry for registry in self.registries if not registry.primary)
