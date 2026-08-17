---
status: accepted
---

# v1 Init 支持 C++ 与 CuteDSL Template

v1 `--template` 只接受 `cpp` 和 `cutedsl`，默认 `cpp`；Triton template 延后实现。两种模板共享相同七个强制根文件、Project Manifest、Args Schema、BuildSpec/BuildKey 与纯 `build.nix` API，差异只在示例源码、静态参数转换和被 `flake.lock` 固定的语言工具链，最终都只输出 TVM-FFI `kernel.so`。
