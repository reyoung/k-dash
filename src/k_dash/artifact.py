"""OCI release/build artifact construction and verification."""

from __future__ import annotations

import io
import tarfile
from pathlib import PurePosixPath
from typing import Any

import zstandard

from .canonical import build_key, canonical_json, digest_bytes, loads_no_duplicates
from .errors import ArtifactIntegrityError
from .model import BuildSpec

OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
RELEASE_TYPE = "application/vnd.k-dash.release.v1"
BUILD_TYPE = "application/vnd.k-dash.build.v1"


def binary_archive(kernel_so: bytes) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        info = tarfile.TarInfo("kernel.so")
        info.size = len(kernel_so)
        info.mode = 0o755
        info.mtime = 0
        info.uid = info.gid = 0
        archive.addfile(info, io.BytesIO(kernel_so))
    return zstandard.ZstdCompressor(level=19, write_checksum=True).compress(stream.getvalue())


def extract_binary_archive(payload: bytes) -> bytes:
    try:
        raw = zstandard.ZstdDecompressor().decompress(payload)
    except zstandard.ZstdError as error:
        raise ArtifactIntegrityError("invalid binary compression", stage="build-artifact") from error
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        members = archive.getmembers()
        if len(members) != 1 or members[0].name != "kernel.so" or not members[0].isfile():
            raise ArtifactIntegrityError("binary layer must contain only kernel.so", stage="build-artifact")
        if PurePosixPath(members[0].name).is_absolute():
            raise ArtifactIntegrityError("absolute archive path", stage="build-artifact")
        source = archive.extractfile(members[0])
        assert source is not None
        return source.read()


def build_objects(
    spec: BuildSpec,
    kernel_so: bytes,
    *,
    provenance: dict[str, Any],
    host_dependencies: list[dict[str, str]],
    cxx_runtime: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bytes, bytes, bytes, str]:
    key = build_key(spec)
    layer = binary_archive(kernel_so)
    config = {
        "protocol_version": 1,
        "release_digest": spec.release_digest,
        "buildspec": spec.as_dict(),
        "build_key": key,
        "provenance": provenance,
        "host_dependencies": host_dependencies,
        "cxx_runtime": cxx_runtime,
        "kernel_so_digest": digest_bytes(kernel_so),
        "binary": {"digest": digest_bytes(layer), "size": len(layer)},
    }
    config_bytes = canonical_json(config)
    manifest = {
        "schemaVersion": 2,
        "mediaType": OCI_MANIFEST,
        "artifactType": BUILD_TYPE,
        "config": {
            "mediaType": "application/vnd.k-dash.build.config.v1+json",
            "digest": digest_bytes(config_bytes),
            "size": len(config_bytes),
        },
        "layers": [{
            "mediaType": "application/vnd.k-dash.binary.v1.tar+zstd",
            "digest": digest_bytes(layer),
            "size": len(layer),
        }],
    }
    manifest_bytes = canonical_json(manifest)
    return config, config_bytes, layer, manifest_bytes, digest_bytes(manifest_bytes)


def parse_json_blob(data: bytes, *, stage: str) -> dict[str, Any]:
    try:
        value = loads_no_duplicates(data, stage=stage)
    except (ContractError, UnicodeDecodeError) as error:
        raise ArtifactIntegrityError("artifact JSON is invalid", stage=stage) from error
    if not isinstance(value, dict):
        raise ArtifactIntegrityError("artifact JSON must be an object", stage=stage)
    return value


def verify_descriptor(descriptor: dict[str, Any], payload: bytes, *, stage: str) -> None:
    expected_digest = descriptor.get("digest")
    expected_size = descriptor.get("size")
    if digest_bytes(payload) != expected_digest or len(payload) != expected_size:
        raise ArtifactIntegrityError("descriptor digest or size mismatch", stage=stage)
