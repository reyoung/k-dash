# examples/axpy

This is the end-to-end k-dash example. It implements

```text
out[i] = alpha * x[i] + y[i]
```

as a CUDA kernel exported from one TVM-FFI `kernel.so` using
`apache-tvm-ffi==0.1.13.post3`. `block_size` is the static Kernel Arg. The test
image contains a prevalidated `sm_90a`/CUDA 12.8 cache entry and all Python and
native dependencies, so its GPU smoke test requires no package download.

Build the test image from the repository root after the test harness exports a
minimal k-dash cache into the Git-ignored `.cache-seed/` directory:

```bash
docker build \
  -f examples/axpy/Dockerfile.test \
  -t <registry>/<namespace>/k-dash-axpy:<tag> .
```

Run it on one CUDA GPU:

```bash
docker run --rm --gpus all <registry>/<namespace>/k-dash-axpy:<tag>
```

Success is the combination of `K_DASH_LOAD_OK`, `GPU_NAME=...`,
`MAX_ERROR=...`, and `AXPY_OK`; the script exits non-zero if load or numerical
comparison fails.
