---
status: accepted
---

# Linux Build 使用 manylinux_2_28 并在加载前验证

v1 只分发 `x86_64-linux-gnu` 与 `aarch64-linux-gnu` Build Artifact，glibc baseline 为 `manylinux_2_28`，TVM-FFI ABI、CUDA Toolkit target 与 CC 精确匹配。下载后必须验证 OCI 与文件 digest、BuildSpec/BuildKey、归档路径安全、ELF machine、动态依赖、GLIBC/GLIBCXX/CXXABI 符号上限，以及 RPATH/RUNPATH/绝对 `DT_NEEDED`，全部通过后才允许调用 TVM-FFI 加载模块。其他 section 中未引用的 Nix store 字符串只作诊断。
