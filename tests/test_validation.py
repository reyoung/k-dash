from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from k_dash.canonical import digest_bytes
from k_dash.errors import ArtifactIntegrityError
from k_dash import validation


class _Tag:
    def __init__(self, kind: str, needed: str | None = None):
        self.entry = SimpleNamespace(d_tag=kind)
        if needed is not None:
            self.needed = needed


class _Dynamic:
    def __init__(self, tags: list[_Tag]):
        self._tags = tags

    def iter_tags(self):
        return iter(self._tags)


class _Aux:
    def __init__(self, name: str):
        self.name = name


class _Versions:
    def __init__(self, names: list[str]):
        self._names = names

    def iter_versions(self):
        return iter([(object(), iter([_Aux(name) for name in self._names]))])


class _Elf:
    header = {"e_machine": "EM_X86_64"}

    def __init__(self, tags: list[_Tag], versions: list[str] | None = None):
        self._dynamic = _Dynamic(tags)
        self._versions = _Versions(versions or [])

    def get_section_by_name(self, name: str):
        if name == ".dynamic":
            return self._dynamic
        if name == ".gnu.version_r":
            return self._versions
        return None


def _config(payload: bytes) -> dict:
    return {
        "kernel_so_digest": digest_bytes(payload),
        "buildspec": {"target": {"arch": "x86_64"}},
        "host_dependencies": [],
    }


def test_non_runtime_nix_store_string_only_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"ELF debug __FILE__=/nix/store/source/kernel.cu"
    monkeypatch.setattr(validation, "ELFFile", lambda _: _Elf([_Tag("DT_NEEDED", "libc.so.6")]))
    with pytest.warns(RuntimeWarning, match="non-runtime /nix/store"):
        validation.validate_kernel_so(payload, _config(payload))


def test_rpath_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"ELF"
    monkeypatch.setattr(validation, "ELFFile", lambda _: _Elf([_Tag("DT_RUNPATH")]))
    with pytest.raises(ArtifactIntegrityError, match="RPATH/RUNPATH"):
        validation.validate_kernel_so(payload, _config(payload))


def test_absolute_needed_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"ELF"
    monkeypatch.setattr(
        validation,
        "ELFFile",
        lambda _: _Elf([_Tag("DT_NEEDED", "/nix/store/hash/lib/libbad.so")]),
    )
    with pytest.raises(ArtifactIntegrityError, match="absolute paths"):
        validation.validate_kernel_so(payload, _config(payload))


def test_glibc_above_manylinux_baseline_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"ELF"
    monkeypatch.setattr(
        validation,
        "ELFFile",
        lambda _: _Elf([_Tag("DT_NEEDED", "libc.so.6")], ["GLIBC_2.38"]),
    )
    with pytest.raises(ArtifactIntegrityError, match="GLIBC requirement"):
        validation.validate_kernel_so(payload, _config(payload))


def test_dynamic_cxx_runtime_metadata_matches_elf(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"ELF"
    tags = [
        _Tag("DT_NEEDED", "libc.so.6"),
        _Tag("DT_NEEDED", "libstdc++.so.6"),
        _Tag("DT_NEEDED", "libgcc_s.so.1"),
    ]
    versions = ["GLIBC_2.17", "GLIBCXX_3.4.21", "CXXABI_1.3.9"]
    monkeypatch.setattr(validation, "ELFFile", lambda _: _Elf(tags, versions))
    config = _config(payload)
    config["cxx_runtime"] = {
        "soname": "libstdc++.so.6",
        "required_glibcxx": "GLIBCXX_3.4.21",
        "required_cxxabi": "CXXABI_1.3.9",
        "gcc_cxx11_abi": 1,
        "unwind_soname": "libgcc_s.so.1",
    }
    validation.validate_kernel_so(payload, config)


def test_loaded_libstdcxx_is_checked_before_dlopen(monkeypatch: pytest.MonkeyPatch) -> None:
    requirement = {
        "soname": "libstdc++.so.6",
        "required_glibcxx": "GLIBCXX_3.4.21",
        "required_cxxabi": "CXXABI_1.3.9",
        "gcc_cxx11_abi": 1,
        "unwind_soname": "libgcc_s.so.1",
    }
    monkeypatch.setattr(validation, "_loaded_library_path", lambda _: Path("/runtime/lib.so"))
    monkeypatch.setattr(validation, "_provided_versions", lambda _: {"GLIBCXX_3.4.20", "CXXABI_1.3.9"})
    with pytest.raises(ArtifactIntegrityError, match="does not satisfy"):
        validation.validate_host_cxx_runtime({"cxx_runtime": requirement})


def test_glibcxx_above_pytorch_runtime_policy_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b"ELF"
    tags = [
        _Tag("DT_NEEDED", "libstdc++.so.6"),
        _Tag("DT_NEEDED", "libgcc_s.so.1"),
    ]
    versions = ["GLIBCXX_3.4.31", "CXXABI_1.3.13"]
    monkeypatch.setattr(validation, "ELFFile", lambda _: _Elf(tags, versions))
    config = _config(payload)
    config["cxx_runtime"] = validation.cxx_runtime_requirement(payload)
    with pytest.raises(ArtifactIntegrityError, match="GLIBCXX requirement"):
        validation.validate_kernel_so(payload, config)


def test_non_numeric_cxxabi_feature_tags_are_ignored() -> None:
    assert validation._maximum_version(
        {"CXXABI_FLOAT128", "CXXABI_TM_1", "CXXABI_1.3.13"},
        "CXXABI_",
    ) == "CXXABI_1.3.13"
