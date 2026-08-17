"""Automatic and explicit TargetSpec construction."""

from __future__ import annotations

import platform
import os
import re
import subprocess

from .errors import ContractError, TargetDetectionError
from .model import TargetSpec


def normalize_cuda_version(value: str) -> str:
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.\d+)?", value.strip())
    if not match:
        raise ContractError("CUDA version must be major.minor", stage="target", context={"cuda": value})
    return f"{int(match.group(1))}.{int(match.group(2))}"


def normalize_cc(value: str) -> str:
    match = re.fullmatch(r"sm_(\d)(\d)([a-z]?)", value)
    if not match:
        raise ContractError("CC must look like sm_90a", stage="target", context={"cc": value})
    major, minor, suffix = int(match.group(1)), int(match.group(2)), match.group(3)
    if major >= 9 and suffix != "a":
        raise ContractError("CC 9.0 and newer require architecture-specific a target", stage="target", context={"cc": value})
    if major < 9 and suffix:
        raise ContractError("pre-9.0 CC must not use an architecture suffix", stage="target", context={"cc": value})
    return f"sm_{major}{minor}{suffix}"


def explicit_target(cuda: str, cc: str) -> TargetSpec:
    machine = os.environ.get("K_DASH_TARGET_ARCH")
    if machine is None:
        # AOT builds on macOS target the Linux x86_64 CUDA fleet by default;
        # Linux builds retain the host CPU architecture.
        machine = "x86_64" if platform.system() == "Darwin" else platform.machine()
    arch = {"x86_64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}.get(machine)
    if arch is None:
        raise ContractError("unsupported CPU architecture", stage="target", context={"arch": platform.machine()})
    return TargetSpec(os="linux", arch=arch, cuda=normalize_cuda_version(cuda), cc=normalize_cc(cc))


def _nvcc_version() -> str | None:
    try:
        result = subprocess.run(["nvcc", "--version"], check=True, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"release\s+(\d+\.\d+)", result.stdout + result.stderr)
    return normalize_cuda_version(match.group(1)) if match else None


def detect_target() -> TargetSpec:
    cuda = _nvcc_version()
    try:
        import torch

        torch_cuda = torch.version.cuda
        if cuda is None and torch_cuda:
            cuda = normalize_cuda_version(torch_cuda)
        if not torch.cuda.is_available():
            raise TargetDetectionError("logical GPU 0 is not available", stage="target-detection")
        major, minor = torch.cuda.get_device_capability(0)
    except ImportError as error:
        raise TargetDetectionError("PyTorch is required to inspect logical GPU 0", stage="target-detection") from error
    if cuda is None:
        raise TargetDetectionError("neither nvcc nor PyTorch reports a CUDA toolkit", stage="target-detection")
    cc = f"sm_{major}{minor}{'a' if major >= 9 else ''}"
    arch = {"x86_64": "x86_64", "aarch64": "aarch64"}.get(platform.machine())
    if arch is None or platform.system() != "Linux":
        raise TargetDetectionError("runtime loading supports Linux x86_64/aarch64 only", stage="target-detection")
    return TargetSpec(os="linux", arch=arch, cuda=cuda, cc=cc)
