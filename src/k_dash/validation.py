"""ELF and Build Artifact runtime validation."""

from __future__ import annotations

import io
import ctypes
import importlib.metadata
import re
import warnings
from pathlib import PurePosixPath
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile

from .canonical import build_key, digest_bytes
from .errors import ArtifactIntegrityError

BASE_LIBRARIES = {
    "libc.so.6",
    "libm.so.6",
    "libdl.so.2",
    "libpthread.so.0",
    "librt.so.1",
    "libstdc++.so.6",
    "libgcc_s.so.1",
}

MAX_GLIBC = "GLIBC_2.28"
MAX_GLIBCXX = "GLIBCXX_3.4.30"
MAX_CXXABI = "CXXABI_1.3.13"

CUDA_SONAMES = {
    "libcuda.so.1": "cuda-driver",
    "libcudart.so.12": "cuda-runtime",
    "libcudart.so.13": "cuda-runtime",
    "libcublas.so.12": "cublas",
    "libcublas.so.13": "cublas",
    "libnccl.so.2": "nccl",
    "libcute_dsl_runtime.so": "cutedsl-runtime",
}

DEPENDENCY_MIN_VERSIONS = {
    "cutedsl-runtime": "4.6.1",
}

_HOST_LIBRARY_HANDLES: dict[str, ctypes.CDLL] = {}


def dynamic_dependencies(payload: bytes) -> set[str]:
    try:
        elf = ELFFile(io.BytesIO(payload))
    except Exception as error:
        raise ArtifactIntegrityError("kernel.so is not a readable ELF", stage="elf-validation") from error
    dynamic = elf.get_section_by_name(".dynamic")
    if dynamic is None:
        return set()
    return {tag.needed for tag in dynamic.iter_tags() if tag.entry.d_tag == "DT_NEEDED"}


def infer_host_dependencies(payload: bytes) -> list[dict[str, str]]:
    return [
        {
            "name": CUDA_SONAMES[soname],
            "soname": soname,
            "min_version": DEPENDENCY_MIN_VERSIONS.get(CUDA_SONAMES[soname], "0"),
        }
        for soname in sorted(dynamic_dependencies(payload))
        if soname in CUDA_SONAMES
    ]


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.rsplit("_", 1)[-1].split("."))


def _maximum_version(values: set[str], prefix: str) -> str | None:
    matching = [
        value
        for value in values
        if re.fullmatch(re.escape(prefix) + r"\d+(?:\.\d+)*", value)
    ]
    return max(matching, key=_version_tuple) if matching else None


def elf_required_versions(payload: bytes) -> dict[str, str | None]:
    try:
        elf = ELFFile(io.BytesIO(payload))
    except Exception as error:
        raise ArtifactIntegrityError("kernel.so is not a readable ELF", stage="elf-validation") from error
    section = elf.get_section_by_name(".gnu.version_r")
    names: set[str] = set()
    if section is not None:
        for _, auxiliaries in section.iter_versions():
            names.update(auxiliary.name for auxiliary in auxiliaries)
    return {
        "glibc": _maximum_version(names, "GLIBC_"),
        "glibcxx": _maximum_version(names, "GLIBCXX_"),
        "cxxabi": _maximum_version(names, "CXXABI_"),
    }


def cxx_runtime_requirement(payload: bytes) -> dict[str, Any] | None:
    needed = dynamic_dependencies(payload)
    if "libstdc++.so.6" not in needed and "libgcc_s.so.1" not in needed:
        return None
    versions = elf_required_versions(payload)
    return {
        "soname": "libstdc++.so.6",
        "required_glibcxx": versions["glibcxx"],
        "required_cxxabi": versions["cxxabi"],
        "gcc_cxx11_abi": 1,
        "unwind_soname": "libgcc_s.so.1",
    }


def _check_maximum(actual: str | None, maximum: str, label: str) -> None:
    if actual is not None and _version_tuple(actual) > _version_tuple(maximum):
        raise ArtifactIntegrityError(
            f"{label} requirement exceeds the runtime baseline",
            stage="elf-validation",
            context={"required": actual, "maximum": maximum},
        )


def validate_build_config(config: dict[str, Any], expected_key: str, expected_release: str) -> None:
    spec = config.get("buildspec")
    if not isinstance(spec, dict) or build_key(spec) != expected_key or config.get("build_key") != expected_key:
        raise ArtifactIntegrityError("BuildSpec/BuildKey mismatch", stage="build-validation")
    if spec.get("release_digest") != expected_release or config.get("release_digest") != expected_release:
        raise ArtifactIntegrityError("Release digest mismatch", stage="build-validation")


def validate_kernel_so(payload: bytes, config: dict[str, Any]) -> None:
    if digest_bytes(payload) != config.get("kernel_so_digest"):
        raise ArtifactIntegrityError("kernel.so digest mismatch", stage="elf-validation")
    try:
        elf = ELFFile(io.BytesIO(payload))
    except Exception as error:
        raise ArtifactIntegrityError("kernel.so is not a readable ELF", stage="elf-validation") from error
    expected_arch = config.get("buildspec", {}).get("target", {}).get("arch")
    expected_machine = {"x86_64": "EM_X86_64", "aarch64": "EM_AARCH64"}.get(expected_arch)
    if expected_machine and elf.header["e_machine"] != expected_machine:
        raise ArtifactIntegrityError("ELF machine does not match TargetSpec", stage="elf-validation")
    dynamic = elf.get_section_by_name(".dynamic")
    needed: set[str] = set()
    if dynamic is not None:
        for tag in dynamic.iter_tags():
            if tag.entry.d_tag == "DT_NEEDED":
                needed.add(tag.needed)
            elif tag.entry.d_tag in {"DT_RPATH", "DT_RUNPATH"}:
                raise ArtifactIntegrityError("RPATH/RUNPATH is forbidden", stage="elf-validation")
    declared = {entry.get("soname") for entry in config.get("host_dependencies", [])}
    absolute_needed = {item for item in needed if PurePosixPath(item).is_absolute()}
    if absolute_needed:
        raise ArtifactIntegrityError(
            "DT_NEEDED must contain SONAMEs, not absolute paths",
            stage="elf-validation",
            context={"needed": sorted(absolute_needed)},
        )
    allowed = BASE_LIBRARIES | declared
    unexpected = {
        item for item in needed if item not in allowed and not item.startswith("libtvm_ffi.so") and not item.startswith("ld-linux")
    }
    if unexpected:
        raise ArtifactIntegrityError("undeclared dynamic dependencies", stage="elf-validation", context={"needed": sorted(unexpected)})
    versions = elf_required_versions(payload)
    _check_maximum(versions["glibc"], MAX_GLIBC, "GLIBC")
    _check_maximum(versions["glibcxx"], MAX_GLIBCXX, "GLIBCXX")
    _check_maximum(versions["cxxabi"], MAX_CXXABI, "CXXABI")
    inferred_cxx = cxx_runtime_requirement(payload)
    recorded_cxx = config.get("cxx_runtime")
    if inferred_cxx != recorded_cxx:
        raise ArtifactIntegrityError(
            "C++ runtime requirement metadata mismatch",
            stage="elf-validation",
            context={"recorded": recorded_cxx, "inferred": inferred_cxx},
        )
    if b"/nix/store" in payload:
        warnings.warn(
            "kernel.so contains non-runtime /nix/store strings; dynamic dependencies are clean",
            RuntimeWarning,
            stacklevel=2,
        )


def _loaded_library_path(soname: str) -> Path | None:
    maps = Path("/proc/self/maps")
    if not maps.is_file():
        return None
    for line in maps.read_text().splitlines():
        fields = line.split()
        if len(fields) >= 6 and soname in fields[-1]:
            path = Path(fields[-1].removesuffix(" (deleted)"))
            if path.is_file():
                return path
    return None


def _provided_versions(path: Path) -> set[str]:
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        section = elf.get_section_by_name(".gnu.version_d")
        names: set[str] = set()
        if section is not None:
            for _, auxiliaries in section.iter_versions():
                names.update(auxiliary.name for auxiliary in auxiliaries)
        return names


def validate_host_cxx_runtime(config: dict[str, Any]) -> None:
    requirement = config.get("cxx_runtime")
    if requirement is None:
        return
    for soname in (requirement["soname"], requirement["unwind_soname"]):
        if _loaded_library_path(soname) is None:
            try:
                ctypes.CDLL(soname, mode=ctypes.RTLD_GLOBAL)
            except OSError as error:
                raise ArtifactIntegrityError(
                    "required C++ runtime library is unavailable",
                    stage="runtime-dependencies",
                    context={"soname": soname},
                ) from error
    library = _loaded_library_path(requirement["soname"])
    if library is None:
        raise ArtifactIntegrityError(
            "loaded libstdc++ path cannot be identified",
            stage="runtime-dependencies",
        )
    provided = _provided_versions(library)
    for field, prefix in (("required_glibcxx", "GLIBCXX_"), ("required_cxxabi", "CXXABI_")):
        required = requirement.get(field)
        available = _maximum_version(provided, prefix)
        if required is not None and (available is None or _version_tuple(available) < _version_tuple(required)):
            raise ArtifactIntegrityError(
                "loaded libstdc++ does not satisfy the Build requirement",
                stage="runtime-dependencies",
                context={"required": required, "available": available, "path": str(library)},
            )


def _package_version_tuple(value: str) -> tuple[int, ...]:
    match = re.match(r"\d+(?:\.\d+)*", value)
    return tuple(int(part) for part in match.group(0).split(".")) if match else ()


def validate_host_dependencies(config: dict[str, Any]) -> None:
    for requirement in config.get("host_dependencies", []):
        name = requirement.get("name")
        soname = requirement.get("soname")
        if name == "cutedsl-runtime":
            try:
                installed = importlib.metadata.version("nvidia-cutlass-dsl")
            except importlib.metadata.PackageNotFoundError as error:
                raise ArtifactIntegrityError(
                    "CuteDSL runtime package is unavailable",
                    stage="runtime-dependencies",
                    context={"package": "nvidia-cutlass-dsl"},
                ) from error
            minimum = requirement.get("min_version", "0")
            if _package_version_tuple(installed) < _package_version_tuple(minimum):
                raise ArtifactIntegrityError(
                    "CuteDSL runtime package is too old",
                    stage="runtime-dependencies",
                    context={"required": minimum, "installed": installed},
                )
            try:
                import cutlass.runtime

                candidates = cutlass.runtime.find_runtime_libraries(enable_tvm_ffi=False)
                runtime = next(path for path in candidates if Path(path).name == soname)
                if runtime not in _HOST_LIBRARY_HANDLES:
                    _HOST_LIBRARY_HANDLES[runtime] = ctypes.CDLL(
                        runtime,
                        mode=ctypes.RTLD_GLOBAL,
                    )
            except (ImportError, OSError, StopIteration) as error:
                raise ArtifactIntegrityError(
                    "CuteDSL native runtime library is unavailable",
                    stage="runtime-dependencies",
                    context={"soname": soname},
                ) from error
        elif isinstance(soname, str):
            try:
                if soname not in _HOST_LIBRARY_HANDLES:
                    _HOST_LIBRARY_HANDLES[soname] = ctypes.CDLL(
                        soname,
                        mode=ctypes.RTLD_GLOBAL,
                    )
            except OSError as error:
                raise ArtifactIntegrityError(
                    "required host dependency is unavailable",
                    stage="runtime-dependencies",
                    context={"name": name, "soname": soname},
                ) from error


def validate_tvm_ffi_runtime(config: dict[str, Any], installed_version: str) -> None:
    required = config.get("buildspec", {}).get("target", {}).get("tvm_ffi")
    if required != installed_version:
        raise ArtifactIntegrityError(
            "TVM-FFI runtime version does not match TargetSpec",
            stage="runtime-dependencies",
            context={"required": required, "installed": installed_version},
        )
