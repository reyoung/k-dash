---
status: accepted
date: 2026-08-17
---

# Kernel 与 TVM-FFI 共享动态 C++ runtime

## Decision

v1 Kernel Module 动态依赖 `libstdc++.so.6` 与 `libgcc_s.so.1`，并复用当前
进程中 TVM-FFI 已加载的同一份 C++ runtime 和 unwinder。Kernel Artifact 不打包
私有 C++ runtime，不使用 RPATH/RUNPATH，也不静态链接第二份 libstdc++/libgcc。

Builder 使用固定 manylinux_2_28 或更旧的 glibc sysroot。链接后从 ELF
`.gnu.version_r` 提取最高 `GLIBC`、`GLIBCXX` 与 `CXXABI` 要求。默认 policy 为
`GLIBC <= 2.28`、`GLIBCXX <= 3.4.30`、`CXXABI <= 1.3.13`，后两者与
PyTorch 2.7.1 CUDA 12.8 标准镜像中 TVM-FFI 实际解析到的系统
`libstdc++.so.6` 对齐，而不是与镜像中未被 loader 选择的 Conda 副本对齐。

Build config 保存实际 C++ runtime 要求。加载前，k-dash 从 `/proc/self/maps`
定位进程实际映射的 `libstdc++.so.6`，读取其 `.gnu.version_d` 并验证它满足
Build requirement；不满足时在 `dlopen(kernel.so)` 前 fail closed。

Kernel 的公共边界只允许 TVM-FFI/C ABI 类型。STL 类型、allocator ownership、
RTTI object 和 C++ exception 不能跨 DSO；异常必须在 Module wrapper 内转换为
TVM-FFI error。

## Consequences

- 进程只有一份 C++ runtime 和 unwinder，避免静态副本与 TVM-FFI 动态副本冲突。
- 新版本 libstdc++ 通过 versioned symbols 向后兼容；加载器验证的是实际已加载库，
  不是磁盘上任意候选文件。
- Kernel 使用高于默认 baseline 的标准库符号时构建直接失败，而不是把不兼容留到部署。
- 本 ADR 取代 ADR-0027 中要求静态链接 `libstdc++`/`libgcc_s` 的部分。
