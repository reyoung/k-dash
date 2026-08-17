from __future__ import annotations

from pathlib import Path

from k_dash.artifact import build_objects, extract_binary_archive
from k_dash.cache import Cache
from k_dash.canonical import build_key, digest_bytes
from k_dash.model import BuildSpec


def test_binary_artifact_and_atomic_cache(tmp_path: Path) -> None:
    # ELF validation has separate integration coverage; this test focuses on
    # the exact one-file archive and atomic content-addressed commit.
    payload = b"\x7fELFtest-module"
    spec = BuildSpec("sha256:" + "1" * 64, {"block_size": 256}, {"arch": "x86_64"})
    config, _, layer, _, _ = build_objects(spec, payload, provenance={"mode": "test"}, host_dependencies=[])
    assert extract_binary_archive(layer) == payload
    cache = Cache(tmp_path / "cache")
    key = build_key(spec)
    path = cache.commit_build(key, config, payload)
    assert (path / "kernel.so").read_bytes() == payload
    cached = cache.get_build(key)
    assert cached is not None and cached[0]["kernel_so_digest"] == digest_bytes(payload)
