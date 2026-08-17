---
status: accepted
---

# v1 只加载一个 TVM-FFI Module

Build Artifact v1 只分发一个可以导出多个函数的 TVM-FFI `kernel.so`，不分发或执行 Python glue；`k_dash.load` 验证后通过 TVM-FFI 加载该共享库并返回 TVM-FFI Module。v1 C++/CuteDSL 模板以及未来 Triton 模板都必须在 `build.nix` 输出侧收敛到这一入口契约。
