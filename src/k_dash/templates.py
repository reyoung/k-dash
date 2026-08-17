"""Safe project initialization templates."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from .errors import ContractError
from .project import validate_kernel_name


def _shared(name: str, license_value: str | None) -> dict[str, str]:
    manifest = f'format-version = 1\nname = "{name}"\nbuild-api = 1\n'
    if license_value:
        manifest += f'license = "{license_value}"\n'
    return {
        "k-dash.toml": manifest,
        "README.md": f"# {name}\n\nA TVM-FFI CUDA kernel managed by k-dash.\n",
        ".k-dash-ignore": ".git\nresult\n*.pyc\n__pycache__\n",
        ".gitignore": "result\n.direnv\n",
        "args.schema.json": json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {"block_size": {"type": "integer", "enum": [128, 256, 512], "default": 256}},
                "additionalProperties": False,
            },
            indent=2,
        ) + "\n",
        "flake.nix": '''{
  description = "k-dash kernel build lock";
  inputs.nixpkgs = {
    url = "tarball+https://codeload.github.com/NixOS/nixpkgs/tar.gz/75f4ba05c63be3f147bcc2f7bd4ba1f029cedcb1";
    flake = false;
  };
  inputs.cuda-nixpkgs = {
    url = "tarball+https://codeload.github.com/NixOS/nixpkgs/tar.gz/b6018f87da91d19d0ab4cf979885689b469cdd41";
    flake = false;
  };
  outputs = { self, nixpkgs, cuda-nixpkgs }: {};
}
''',
        "flake.lock": resources.files("k_dash").joinpath("template_data/flake.lock").read_text(),
    }


CPP_SOURCE = r'''#include <tvm/ffi/tvm_ffi.h>

using namespace tvm;

__global__ void kernel(float* out, const float* x, int64_t n) {
  for (int64_t i = blockIdx.x * blockDim.x + threadIdx.x; i < n; i += blockDim.x * gridDim.x)
    out[i] = x[i];
}

void copy_cuda(ffi::TensorView out, ffi::TensorView x) {
  TVM_FFI_CHECK(out.numel() == x.numel(), ValueError) << "size mismatch";
  kernel<<<(x.numel() + 255) / 256, 256>>>(static_cast<float*>(out.data_ptr()),
                                           static_cast<const float*>(x.data_ptr()), x.numel());
}
TVM_FFI_DLL_EXPORT_TYPED_FUNC(copy_cuda, copy_cuda);
'''

CUTEDSL_SOURCE = r'''from __future__ import annotations

import sys

import cutlass
import cutlass.cute as cute
from cutlass.cute.runtime import make_fake_compact_tensor


@cute.kernel
def copy_kernel(x: cute.Tensor, out: cute.Tensor):
    for index in range(x.shape[0]):
        out[index] = x[index]


@cute.jit
def copy_cuda(x: cute.Tensor, out: cute.Tensor):
    copy_kernel(x, out).launch(grid=(1, 1, 1), block=(1, 1, 1))


def main() -> None:
    object_path, arch, elements = sys.argv[1], sys.argv[2], int(sys.argv[3])
    x = make_fake_compact_tensor(cutlass.Float32, (elements,))
    out = make_fake_compact_tensor(cutlass.Float32, (elements,))
    compiled = cute.compile(
        copy_cuda,
        x,
        out,
        options=f"--enable-tvm-ffi --gpu-arch={arch}",
    )
    compiled.export_to_c(object_path, function_name="copy_cuda")


if __name__ == "__main__":
    main()
'''

def init_project(name: str, destination: Path, template: str, license_value: str | None) -> Path:
    validate_kernel_name(name)
    if template not in {"cpp", "cutedsl"}:
        raise ContractError("template must be cpp or cutedsl", stage="init")
    if destination.exists() and any(destination.iterdir()):
        conflicts = sorted(path.name for path in destination.iterdir())
        raise ContractError("destination is not empty", stage="init", context={"files": conflicts})
    destination.mkdir(parents=True, exist_ok=True)
    files = _shared(name, license_value)
    if template == "cpp":
        files["build.nix"] = resources.files("k_dash").joinpath("template_data/cpp-build.nix").read_text()
        files["src/kernel.cu"] = CPP_SOURCE
    else:
        files["build.nix"] = resources.files("k_dash").joinpath("template_data/cutedsl-build.nix").read_text()
        files["flake.nix"] = resources.files("k_dash").joinpath("template_data/cutedsl-flake.nix").read_text()
        files["flake.lock"] = resources.files("k_dash").joinpath("template_data/cutedsl-flake.lock").read_text()
        files["src/kernel.py"] = CUTEDSL_SOURCE
    for relative, content in files.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return destination
