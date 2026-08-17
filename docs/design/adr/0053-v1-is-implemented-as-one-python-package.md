---
status: accepted
---

# v1 使用单一 Python Package 实现

v1 使用纯 Python `k_dash` package 实现 public `load`、CLI 与共享 core；OCI Registry 直接使用 Distribution HTTP API，不依赖外部 `oras`，AOT 通过 Docker API/CLI，Local JIT 通过 Nix subprocess，TVM-FFI 是运行时必需依赖。v1 不引入 Rust extension，后续可以替换内部热点实现但不能改变已发布协议。
