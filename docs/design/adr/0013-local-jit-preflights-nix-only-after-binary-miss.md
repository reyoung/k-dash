---
status: superseded by ADR-0021
---

# Local JIT 只在 Binary Miss 后检查 Nix

`k_dash.load` 先完成 Version 解析和二进制查找，只有 Binary Miss 才检查 Local JIT Environment。v1 Local JIT 要求 Linux、宿主架构与 TargetSpec 一致、满足最低版本并启用 flakes 的 Nix、可用的 Nix store 或 daemon 以及启用的 sandbox；k-dash 不自动安装 Nix，也不降级到无 sandbox 构建，CUDA Toolkit、编译器和 DSL 由 Nix 提供，宿主 CUDA Driver/GPU 只负责 TargetSpec 探测与产物加载。
