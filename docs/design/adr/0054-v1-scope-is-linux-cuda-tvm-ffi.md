---
status: accepted
---

# v1 Scope 是 Linux CUDA TVM-FFI

v1 runtime 只支持 Linux CUDA 的 `x86_64` 与 `aarch64`，macOS 只作为 Docker AOT 宿主，Init 只支持 C++ 与 CuteDSL，Kernel Module 只使用 TVM-FFI ABI。Triton、CPU/ROCm/Metal/Windows、macOS runtime、Python glue、多 CC fat binary、显式 Target、自动上传 JIT、Referrers 加载依赖、强制签名、自动 cache 淘汰和 public Resolution API 都明确不属于 v1。
