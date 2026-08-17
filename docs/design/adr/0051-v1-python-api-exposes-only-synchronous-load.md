---
status: accepted
---

# v1 Python API 只暴露同步 `load`

v1 唯一 public callable 是同步 `k_dash.load(kernel, *, jit_args=None, version=<str>) -> tvm_ffi.Module`；Kernel name 必须是小写 `owner/kernel`，Version 必填且严格为字符串，`jit_args=None` 等价于空对象。API 不接受 Target、Registry 或 trust override，也不提供 public Resolution/diagnostic API 或稳定的类型化错误层级，直到 Registry download 或 Local JIT 完成后才返回。
