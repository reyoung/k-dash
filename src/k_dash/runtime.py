"""Release/build resolution and local materialization helpers."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .artifact import BUILD_TYPE, RELEASE_TYPE, extract_binary_archive
from .builder import local_jit
from .cache import Cache
from .canonical import build_key, build_tag, digest_bytes
from .errors import ArtifactIntegrityError, ArtifactNotFound, OfflineCacheMiss, RegistryAccessFailure
from .model import BuildSpec, RegistryConfig, RegistrySet, TargetSpec
from .oci import OCIClient, PulledArtifact
from .project import extract_source_archive
from .validation import cxx_runtime_requirement, validate_build_config, validate_kernel_so


def _client(registry: RegistryConfig, kernel: str) -> OCIClient:
    return OCIClient(registry, kernel)


def resolve_release(
    registries: RegistrySet, kernel: str, version: str, cache: Cache
) -> tuple[str, RegistryConfig]:
    primary = registries.primary
    offline = os.environ.get("K_DASH_OFFLINE") == "1"
    cached = cache.get_resolution(primary.name, kernel, version)
    if offline:
        if cached is None:
            raise OfflineCacheMiss("release resolution is absent", stage="offline", context={"kernel": kernel, "version": version})
        return cached, primary
    if cached is not None and not version.startswith("dev-"):
        return cached, primary
    try:
        digest, _, _ = _client(primary, kernel).get_manifest(f"release-{version}")
        cache.put_resolution(primary.name, kernel, version, digest)
        return digest, primary
    except RegistryAccessFailure:
        if version.startswith("dev-"):
            raise
    for secondary in registries.secondaries:
        try:
            digest, _, _ = _client(secondary, kernel).get_manifest(f"release-{version}")
            cache.put_resolution(primary.name, kernel, version, digest)
            return digest, secondary
        except RegistryAccessFailure:
            continue
    raise RegistryAccessFailure("no registry can resolve the release", stage="release-resolution", context={"kernel": kernel})


def pull_release(registry: RegistryConfig, kernel: str, digest: str) -> PulledArtifact:
    artifact = _client(registry, kernel).pull(digest, artifact_type=RELEASE_TYPE)
    if artifact.digest != digest or artifact.config.get("kernel") != kernel:
        raise ArtifactIntegrityError("release identity mismatch", stage="release-artifact")
    if artifact.config.get("source", {}).get("digest") != digest_bytes(artifact.layers[0]):
        raise ArtifactIntegrityError("release source digest mismatch", stage="release-artifact")
    return artifact


def _binary_registry(
    registries: RegistrySet, authority: RegistryConfig, kernel: str, tag: str
) -> tuple[PulledArtifact | None, RegistryConfig]:
    order = [authority] + [item for item in registries.registries if item.name != authority.name]
    for index, registry in enumerate(order):
        try:
            return _client(registry, kernel).pull(tag, artifact_type=BUILD_TYPE), registry
        except ArtifactNotFound:
            return None, registry
        except RegistryAccessFailure:
            if index == len(order) - 1:
                raise
            continue
    raise AssertionError("unreachable")


def materialize(
    registries: RegistrySet,
    authority: RegistryConfig,
    kernel: str,
    release_digest: str,
    args: dict[str, Any],
    target: TargetSpec,
    cache: Cache,
) -> tuple[str, Path]:
    spec = BuildSpec(release_digest=release_digest, args=args, target=target.as_dict())
    key = build_key(spec)
    cached = cache.get_build(key)
    if cached:
        return key, cached[1]
    with cache.build_lock(key):
        cached = cache.get_build(key)
        if cached:
            return key, cached[1]
        offline = os.environ.get("K_DASH_OFFLINE") == "1"
        if offline:
            cached_release = cache.get_release(release_digest)
            if cached_release is None:
                raise OfflineCacheMiss(
                    "source is absent from the offline cache",
                    stage="offline",
                    context={"build_key": key, "release_digest": release_digest},
                )
            kernel_so, provenance = local_jit(cached_release[2], spec)
            config = {
                "protocol_version": 1,
                "release_digest": release_digest,
                "buildspec": spec.as_dict(),
                "build_key": key,
                "provenance": provenance,
                "host_dependencies": [],
                "cxx_runtime": cxx_runtime_requirement(kernel_so),
                "kernel_so_digest": digest_bytes(kernel_so),
            }
            validate_kernel_so(kernel_so, config)
            destination = cache.commit_build(key, config, kernel_so)
            return key, destination / "kernel.so"
        artifact, binary_authority = _binary_registry(registries, authority, kernel, build_tag(key))
        if artifact is not None:
            config = artifact.config
            validate_build_config(config, key, release_digest)
            kernel_so = extract_binary_archive(artifact.layers[0])
            validate_kernel_so(kernel_so, config)
        else:
            release = pull_release(binary_authority, kernel, release_digest)
            with tempfile.TemporaryDirectory(prefix="k-dash-source-") as temporary:
                source = Path(temporary) / "source"
                extract_source_archive(release.layers[0], source)
                kernel_so, provenance = local_jit(source, spec)
            config = {
                "protocol_version": 1,
                "release_digest": release_digest,
                "buildspec": spec.as_dict(),
                "build_key": key,
                "provenance": provenance,
                "host_dependencies": [],
                "cxx_runtime": cxx_runtime_requirement(kernel_so),
                "kernel_so_digest": digest_bytes(kernel_so),
            }
            validate_kernel_so(kernel_so, config)
        destination = cache.commit_build(key, config, kernel_so)
        return key, destination / "kernel.so"
