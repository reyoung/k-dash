from __future__ import annotations

import os

import torch
import tvm_ffi
import k_dash


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")

    properties = torch.cuda.get_device_properties(0)
    print(f"GPU_NAME={properties.name}")
    print(f"GPU_CC={properties.major}.{properties.minor}")
    print(f"GPU_SM_COUNT={properties.multi_processor_count}")
    print(f"TORCH_CUDA={torch.version.cuda}")

    module = k_dash.load(
        "examples/axpy",
        version=os.environ.get("K_DASH_AXPY_VERSION", "1"),
        jit_args={"block_size": 256},
    )
    print("K_DASH_LOAD_OK")
    count = 1_000_003
    alpha = 1.75
    generator = torch.Generator(device="cuda").manual_seed(20260817)
    x = torch.randn(count, device="cuda", dtype=torch.float32, generator=generator)
    y = torch.randn(count, device="cuda", dtype=torch.float32, generator=generator)
    out = torch.empty_like(x)
    with tvm_ffi.use_torch_stream():
        module.axpy(out, x, y, alpha)
    torch.cuda.synchronize()
    expected = alpha * x + y
    maximum_error = (out - expected).abs().max().item()
    torch.testing.assert_close(out, expected, rtol=1e-6, atol=1e-6)
    print(f"ELEMENTS={count}")
    print(f"ALPHA={alpha}")
    print(f"MAX_ERROR={maximum_error:.9g}")
    print(f"SAMPLE={out[:4].cpu().tolist()}")
    print("AXPY_OK")


if __name__ == "__main__":
    main()
