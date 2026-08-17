---
status: accepted
---

# Kernel 自己声明并锁定 Nix 输入

Kernel Source Package 在既有 `build.nix` 之外必须包含 `flake.nix` 和 `flake.lock`，由 Kernel 自己选择并锁定 nixpkgs、CUDA、Triton、CuteDSL 等构建输入；`k-dash init` 为各模板生成这两个文件。AOT 和 Local JIT 都使用 Release 中同一份 lock，不能回退到宿主 Nix channel 或 k-dash 全局浮动 package set，`build.nix` 仍是接收 BuildSpec 并产生物化结果的标准构建入口。
