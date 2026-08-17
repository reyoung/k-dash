# k-dash

`k-dash` implements the frozen v1 design in [`docs/design/`](docs/design/README.md):
content-addressed TVM-FFI CUDA kernel builds, direct OCI Distribution API access,
an atomic local cache, Docker/Nix AOT builds, and synchronous Python loading.

The runnable example is [`examples/axpy`](examples/axpy/README.md). It exports an
AXPY CUDA kernel as one TVM-FFI `kernel.so` and includes an AFS/H20 smoke test.

```bash
python -m pip install -e '.[test]'
pytest
k-dash --help
```

The public Python API is intentionally one function:

```python
import k_dash

module = k_dash.load("examples/axpy", version="1", jit_args={"block_size": 256})
```
