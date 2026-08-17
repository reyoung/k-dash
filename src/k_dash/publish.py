"""Release publication and deterministic Build Addition."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .artifact import BUILD_TYPE, RELEASE_TYPE, build_objects, extract_binary_archive, parse_json_blob
from .builder import DEFAULT_BUILDER_IMAGE, docker_aot
from .cache import Cache
from .canonical import build_key, build_tag, canonical_json, loads_no_duplicates, normalize_args
from .config import load_registry_set
from .errors import ArtifactIntegrityError, ArtifactNotFound, ContractError
from .model import BuildSpec, RegistryConfig, TargetSpec
from .oci import OCIClient
from .project import extract_source_archive, load_project, release_objects
from .runtime import pull_release, resolve_release
from .target import explicit_target
from .validation import cxx_runtime_requirement, infer_host_dependencies, validate_kernel_so

VERSION_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,119}$")


def validate_version(version: str) -> str:
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version) or len("release-" + version) > 128:
        raise ContractError("version cannot form a valid OCI tag", stage="publish", context={"version": version})
    return version


def _release_payloads(root: Path, version: str):
    config, config_bytes, layer, manifest_bytes, digest = release_objects(root, version)
    return config, config_bytes, layer, manifest_bytes, digest


def _check_release_binding(client: OCIClient, version: str, expected_digest: str) -> None:
    try:
        current, _, _ = client.get_manifest(f"release-{version}")
    except ArtifactNotFound:
        return
    if current != expected_digest and not version.startswith("dev-"):
        raise ArtifactIntegrityError(
            "immutable Version is already bound to a different Release",
            stage="publish",
            context={"version": version, "existing": current, "new": expected_digest},
        )


def _load_args_files(paths: list[Path], schema: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for path in paths:
        try:
            raw = loads_no_duplicates(path.read_text(), stage="publish")
        except (OSError, ContractError) as error:
            raise ContractError("AOT args file is invalid", stage="publish", context={"path": str(path)}) from error
        output.append(normalize_args(raw, schema))
    return output


def local_build(
    root: Path,
    *,
    version: str,
    cuda: str,
    cc: str,
    args_files: list[Path],
    builder_image: str = DEFAULT_BUILDER_IMAGE,
) -> list[tuple[str, Path, bool, str, dict[str, Any]]]:
    version = validate_version(version)
    _, schema = load_project(root)
    _, _, _, _, release_digest = _release_payloads(root, version)
    target = explicit_target(cuda, cc)
    args_values = _load_args_files(args_files, schema) if args_files else [normalize_args({}, schema)]
    cache = Cache()
    results: list[tuple[str, Path, bool, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for args in args_values:
        spec = BuildSpec(release_digest=release_digest, args=args, target=target.as_dict())
        key = build_key(spec)
        if key in seen:
            continue
        seen.add(key)
        cached = cache.get_build(key)
        if cached:
            results.append((key, cached[1], True, release_digest, cached[0].get("provenance", {})))
            continue
        kernel_so, provenance = docker_aot(root, spec, builder_image=builder_image)
        config, _, _, _, _ = build_objects(
            spec,
            kernel_so,
            provenance=provenance,
            host_dependencies=infer_host_dependencies(kernel_so),
            cxx_runtime=cxx_runtime_requirement(kernel_so),
        )
        validate_kernel_so(kernel_so, config)
        destination = cache.commit_build(key, config, kernel_so)
        results.append((key, destination / "kernel.so", False, release_digest, provenance))
    return results


def publish_release(
    root: Path,
    *,
    version: str,
    cuda: str | None = None,
    cc: str | None = None,
    args_files: list[Path] | None = None,
    builder_image: str = DEFAULT_BUILDER_IMAGE,
) -> dict[str, Any]:
    version = validate_version(version)
    manifest, schema = load_project(root)
    args_files = args_files or []
    if args_files and (cuda is None or cc is None):
        raise ContractError("AOT args require --cuda-version and --cc", stage="publish")
    if not args_files and (cuda is not None or cc is not None):
        raise ContractError("AOT target is invalid without --aot-args", stage="publish")
    release_config, release_config_bytes, source_layer, release_manifest_bytes, release_digest = _release_payloads(root, version)

    materialized: list[tuple[str, bytes, bytes, bytes, str]] = []
    if args_files:
        target = explicit_target(cuda or "", cc or "")
        seen: set[str] = set()
        for args in _load_args_files(args_files, schema):
            spec = BuildSpec(release_digest=release_digest, args=args, target=target.as_dict())
            key = build_key(spec)
            if key in seen:
                continue
            seen.add(key)
            kernel_so, provenance = docker_aot(root, spec, builder_image=builder_image)
            config, config_bytes, layer, manifest_bytes, digest = build_objects(
                spec,
                kernel_so,
                provenance=provenance,
                host_dependencies=infer_host_dependencies(kernel_so),
                cxx_runtime=cxx_runtime_requirement(kernel_so),
            )
            validate_kernel_so(kernel_so, config)
            materialized.append((key, config_bytes, layer, manifest_bytes, digest))

    registry_set = load_registry_set()
    clients = [OCIClient(registry, manifest.name) for registry in registry_set.registries]
    for client in clients:
        _check_release_binding(client, version, release_digest)
        for key, _, _, build_manifest, expected in materialized:
            try:
                actual, _, _ = client.get_manifest(build_tag(key))
            except ArtifactNotFound:
                continue
            if actual != expected:
                raise ArtifactIntegrityError("BuildKey is bound to a non-reproducible artifact", stage="publish", context={"build_key": key})

    results: dict[str, Any] = {"release_digest": release_digest, "builds": {}, "registries": {}}
    for client in clients:
        for key, config_bytes, layer, manifest_bytes, expected in materialized:
            actual = client.push(build_tag(key), config_bytes, [layer], manifest_bytes)
            if actual != expected:
                raise ArtifactIntegrityError("registry changed Build manifest digest", stage="publish")
            results["builds"][key] = actual
        actual_release = client.push(f"release-{version}", release_config_bytes, [source_layer], release_manifest_bytes)
        if actual_release != release_digest:
            raise ArtifactIntegrityError("registry changed Release manifest digest", stage="publish")
        results["registries"][client.config.name] = actual_release
    cache = Cache()
    for key, config_bytes, layer, _, _ in materialized:
        cache.commit_build(
            key,
            parse_json_blob(config_bytes, stage="publish-cache"),
            extract_binary_archive(layer),
        )
    cache.commit_release(release_digest, release_config, source_layer)
    cache.put_resolution(registry_set.primary.name, manifest.name, version, release_digest)
    return results


def publish_build(
    root: Path,
    *,
    version: str,
    cuda: str,
    cc: str,
    args_file: Path,
    builder_image: str = DEFAULT_BUILDER_IMAGE,
) -> dict[str, Any]:
    version = validate_version(version)
    project, _ = load_project(root)
    registries = load_registry_set()
    cache = Cache()
    release_digest, authority = resolve_release(registries, project.name, version, cache)
    release = pull_release(authority, project.name, release_digest)
    args = _load_args_files([args_file], release.config["args_schema"])[0]
    target = explicit_target(cuda, cc)
    spec = BuildSpec(release_digest=release_digest, args=args, target=target.as_dict())
    key = build_key(spec)
    import tempfile

    with tempfile.TemporaryDirectory(prefix="k-dash-publish-build-") as temporary:
        source = Path(temporary) / "source"
        extract_source_archive(release.layers[0], source)
        kernel_so, provenance = docker_aot(source, spec, builder_image=builder_image)
    config, config_bytes, layer, manifest_bytes, expected = build_objects(
        spec,
        kernel_so,
        provenance=provenance,
        host_dependencies=infer_host_dependencies(kernel_so),
        cxx_runtime=cxx_runtime_requirement(kernel_so),
    )
    validate_kernel_so(kernel_so, config)
    if version.startswith("dev-"):
        current, _ = resolve_release(registries, project.name, version, Cache())
        if current != release_digest:
            raise ArtifactIntegrityError("DevVersionMoved", stage="publish-build", context={"before": release_digest, "after": current})
    results: dict[str, str] = {}
    for registry in registries.registries:
        client = OCIClient(registry, project.name)
        try:
            existing, _, _ = client.get_manifest(build_tag(key))
        except ArtifactNotFound:
            existing = None
        if existing is not None and existing != expected:
            raise ArtifactIntegrityError("NonReproducibleBuild", stage="publish-build", context={"build_key": key})
        actual = client.push(build_tag(key), config_bytes, [layer], manifest_bytes)
        if actual != expected:
            raise ArtifactIntegrityError("registry changed Build manifest digest", stage="publish-build")
        results[registry.name] = actual
    return {"release_digest": release_digest, "build_key": key, "registries": results}
