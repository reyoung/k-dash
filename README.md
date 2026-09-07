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

Source ignore patterns are relative to the project root. Directory patterns such
as `build`, `build/`, and `build/**` exclude the whole subtree without walking
it. Existing file globs remain supported; required source files cannot be
excluded. Symbolic links are not packaged or traversed.

In an already isolated CI container without a Docker daemon, `k-dash publish
--backend nix ...` builds AOT artifacts directly with installed Nix. This explicit
backend disables Nix's nested sandbox and build-user group; the CI container must
provide isolation. It uses the same frozen release source, locked dependencies,
BuildSpec and binary validation as Docker AOT. Docker remains the default.
Registry credentials are not forwarded to the Nix build subprocess environment.
