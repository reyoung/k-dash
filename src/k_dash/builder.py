"""Nix Local JIT and archive-stream Docker AOT execution."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .canonical import canonical_json
from .errors import ContractError, KDashError
from .model import BuildSpec
from .project import materialize_source_tree

DEFAULT_BUILDER_IMAGE = "nixos/nix:2.24.9"


def _driver_expression(source: Path, spec: BuildSpec, system: str) -> str:
    # Kernel flakes own and lock nixpkgs. build.nix owns its build helpers, so
    # the Release remains self-contained and has no separate kdlib dependency.
    return f'''let
  source = builtins.path {{ path = {json.dumps(str(source))}; name = "kernel-source"; }};
  flake = builtins.getFlake (
    builtins.unsafeDiscardStringContext ("path:" + toString source)
  );
  system = {json.dumps(system)};
  hasCuteDsl = builtins.hasAttr "cutedsl-toolchain" flake.inputs;
  hasCompatNixpkgs = builtins.hasAttr "compat-nixpkgs" flake.inputs;
  cuteDslOverlays =
    if hasCuteDsl then [
      (import ((builtins.getAttr "cutedsl-toolchain" flake.inputs) + "/nix-builder/overlay.nix") {{
        builderProvenance = null;
      }})
    ] else [ ];
  basePkgs = import flake.inputs.nixpkgs {{
    inherit system;
    config.allowUnfree = true;
  }};
  cudaPkgs = import flake.inputs.cuda-nixpkgs {{
    inherit system;
    config.allowUnfree = true;
    overlays = cuteDslOverlays;
  }};
  compatPkgs = if hasCompatNixpkgs then
    import flake.inputs.compat-nixpkgs {{
      inherit system;
      config.allowUnfree = true;
    }}
  else basePkgs;
  manylinuxHostCc = if hasCompatNixpkgs then
    basePkgs.wrapCCWith {{
      cc = compatPkgs.gcc11.cc;
      bintools = basePkgs.stdenv.cc.bintools;
      libc = basePkgs.glibc;
    }}
  else basePkgs.stdenv.cc;
  pkgs = basePkgs // {{
    cudaPackages_12_8 = cudaPkgs.cudaPackages_12_8;
    # GCC 11 supplies the compiler and C++ headers.  The wrapper supplies the
    # base pin's glibc 2.27 headers, CRT and linker paths; kernel build.nix can
    # then select a compatible dynamic libstdc++/libgcc at final link time.
    manylinuxHostStdenv = basePkgs.overrideCC basePkgs.stdenv manylinuxHostCc;
  }} // (if builtins.hasAttr "cudaPackages_13" cudaPkgs then {{
    cudaPackages_13 = cudaPkgs.cudaPackages_13;
  }} else {{ }}) // (if hasCuteDsl then {{
    cutePythonEnv = cudaPkgs.python313.withPackages (ps: [ ps.nvidia-cutlass-dsl ]);
  }} else {{ }});
  buildSpec = builtins.fromJSON {json.dumps(canonical_json(spec.as_dict()).decode())};
in import (source + "/build.nix") {{ inherit pkgs buildSpec; }}
'''


def _nix_system(spec: BuildSpec) -> str:
    return {"x86_64": "x86_64-linux", "aarch64": "aarch64-linux"}[spec.target["arch"]]


def local_jit(source: Path, spec: BuildSpec) -> tuple[bytes, dict[str, Any]]:
    if shutil.which("nix") is None:
        raise KDashError("Nix is unavailable after Binary Miss", stage="local-jit")
    with tempfile.TemporaryDirectory(prefix="k-dash-jit-") as temporary:
        temporary_path = Path(temporary)
        expression = _driver_expression(source.resolve(), spec, _nix_system(spec))
        expression_path = temporary_path / "driver.nix"
        expression_path.write_text(expression)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "NIX_CONFIG": "experimental-features = nix-command flakes\nsandbox = true\npure-eval = true",
        }
        timeout = int(os.environ.get("K_DASH_JIT_TIMEOUT", "1800"))
        jobs = os.environ.get("K_DASH_NIX_MAX_JOBS", "auto")
        try:
            command = [
                "nix", "build", "--no-link", "--print-out-paths", "--max-jobs", jobs,
                "--file", str(expression_path),
            ]
            if os.environ.get("K_DASH_OFFLINE") == "1":
                command.insert(2, "--offline")
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                env=environment,
                timeout=timeout,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            stderr = getattr(error, "stderr", None)
            context = {"stderr": stderr[-4000:]} if stderr else None
            raise KDashError(
                "Nix Local JIT failed", stage="local-jit", context=context
            ) from error
        output = Path(result.stdout.strip().splitlines()[-1])
        module = output / "kernel.so"
        if not module.is_file() or any(path.name != "kernel.so" for path in output.iterdir()):
            raise ContractError("build output must contain only kernel.so", stage="local-jit")
        return module.read_bytes(), {"mode": "local-jit", "nix_output": output.name}


def docker_aot(
    source: Path,
    spec: BuildSpec,
    *,
    builder_image: str = DEFAULT_BUILDER_IMAGE,
) -> tuple[bytes, dict[str, Any]]:
    try:
        import docker
    except ImportError as error:
        raise KDashError("install k-dash[build] for Docker AOT", stage="docker-aot") from error
    client = docker.from_env()
    try:
        client.volumes.get("k-dash-nix-store")
    except docker.errors.NotFound:
        client.volumes.create(name="k-dash-nix-store", labels={"org.k-dash.cache": "nix-store"})
    with tempfile.TemporaryDirectory(prefix="k-dash-aot-") as temporary:
        temporary_path = Path(temporary)
        stage = temporary_path / "work"
        materialize_source_tree(source, stage / "source")
        expression = _driver_expression(Path("/tmp/source"), spec, _nix_system(spec))
        (stage / "driver.nix").write_text(expression)
        archive = shutil.make_archive(str(temporary_path / "context"), "tar", root_dir=stage, base_dir=".")
        container = client.containers.create(
            builder_image,
            command=[
                "sh", "-lc",
                "nix --extra-experimental-features 'nix-command flakes' build "
                "--option sandbox true --option filter-syscalls false "
                "--no-link --print-out-paths --file /tmp/driver.nix > /tmp/output && "
                "cp $(tail -n1 /tmp/output)/kernel.so /tmp/kernel.so",
            ],
            platform="linux/amd64" if spec.target["arch"] == "x86_64" else "linux/arm64",
            network_disabled=False,
            user="0:0",
            security_opt=["seccomp=unconfined"],
            volumes={"k-dash-nix-store": {"bind": "/nix", "mode": "rw"}},
        )
        try:
            with open(archive, "rb") as stream:
                if not container.put_archive("/tmp", stream):
                    raise KDashError("failed to stream source into builder", stage="docker-aot")
            container.start()
            # A cold /nix volume has to fetch and unpack the whole CUDA
            # toolchain before it ever reaches nvcc, which outlasts any timeout
            # that is reasonable once the store is warm.
            status = container.wait(timeout=int(os.environ.get("K_DASH_AOT_TIMEOUT", "1800")))
            if status.get("StatusCode") != 0:
                log = container.logs(stdout=True, stderr=True, tail=80).decode(errors="replace")
                raise KDashError("Docker AOT failed", stage="docker-aot", context={"log": log})
            bits, _ = container.get_archive("/tmp/kernel.so")
            import io
            import tarfile

            with tarfile.open(fileobj=io.BytesIO(b"".join(bits)), mode="r:") as tar:
                extracted = tar.extractfile("kernel.so")
                if extracted is None:
                    raise KDashError("builder returned no kernel.so", stage="docker-aot")
                payload = extracted.read()
            image = client.images.get(builder_image)
            return payload, {"mode": "docker-aot", "builder_image": builder_image, "builder_digest": image.id}
        finally:
            container.remove(force=True)
