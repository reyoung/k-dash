---
status: accepted
---

# Linux Runtime Dependency 使用严格 Allowlist

Kernel Module 只允许动态依赖 manylinux_2_28 基础 ABI 中的动态加载器、`libc`、`libm`、`libdl`、`libpthread`、`librt`，以及精确 TVM-FFI runtime ABI；`libstdc++` 与 `libgcc_s` 必须静态链接，不得依赖宿主版本。基础 allowlist 之外只允许显式声明且由 k-dash 认可的 Host CUDA Dependency。
