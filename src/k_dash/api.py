"""Synchronous public Python load API."""

from __future__ import annotations

import threading
import json
from collections.abc import Mapping
from typing import Any

from .cache import Cache
from .canonical import normalize_args
from .config import load_registry_set
from .errors import ContractError, OfflineCacheMiss
from .project import validate_kernel_name
from .runtime import materialize, pull_release, resolve_release
from .target import detect_target
from .validation import validate_host_cxx_runtime, validate_host_dependencies, validate_tvm_ffi_runtime

_modules: dict[str, Any] = {}
_module_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def load(kernel: str, *, jit_args: Mapping[str, Any] | None = None, version: str):
    """Resolve, materialize, validate and load one TVM-FFI module."""
    validate_kernel_name(kernel)
    if not isinstance(version, str) or not version:
        raise ContractError("version must be a non-empty string", stage="load")
    if jit_args is not None and not isinstance(jit_args, Mapping):
        raise ContractError("jit_args must be a mapping", stage="load")
    registries = load_registry_set()
    cache = Cache()
    release_digest, authority = resolve_release(registries, kernel, version, cache)
    cached_release = cache.get_release(release_digest)
    if cached_release is None:
        import os

        if os.environ.get("K_DASH_OFFLINE") == "1":
            raise OfflineCacheMiss(
                "release is absent from the offline cache",
                stage="offline",
                context={"release_digest": release_digest},
            )
        release = pull_release(authority, kernel, release_digest)
        cache.commit_release(release_digest, release.config, release.layers[0])
        release_config = release.config
    else:
        release_config = cached_release[0]
    args = normalize_args(dict(jit_args or {}), release_config["args_schema"])
    target = detect_target()
    key, module_path = materialize(registries, authority, kernel, release_digest, args, target, cache)
    with _guard:
        lock = _module_locks.setdefault(key, threading.Lock())
    with lock:
        if key not in _modules:
            import tvm_ffi

            build_config = json.loads(module_path.with_name("config.json").read_text())
            validate_tvm_ffi_runtime(build_config, tvm_ffi.__version__)
            validate_host_dependencies(build_config)
            validate_host_cxx_runtime(build_config)
            _modules[key] = tvm_ffi.load_module(module_path)
        return _modules[key]
