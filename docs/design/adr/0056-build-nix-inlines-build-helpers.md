---
status: accepted
date: 2026-08-17
---

# `build.nix` 内联构建 helper，不依赖独立 `kdlib`

## Decision

v1 的 `build.nix` 固定接口为 `{ pkgs, buildSpec }:`。`k-dash init` 生成的
`build.nix` 必须自包含 `mkTvmFfiKernel` 及对应 C++/CuteDSL 构建 helper 的实现，
并固定其外部下载 digest。Kernel 的 `flake.nix`/`flake.lock` 只锁定 nixpkgs、
CUDA 和语言工具链，不声明独立 `kdlib` input。

构建 helper 属于 Kernel Source Package，因此随 Release digest 一起冻结。k-dash
升级模板不会隐式改变已经存在项目的构建语义；项目需要显式重新生成或移植模板
才能采用新 helper。

## Consequences

- Source Artifact 可以独立解释完整构建，不会因缺失或移动的 `kdlib` 仓库失效。
- `k-dash` 的 Nix driver 只注入锁定 `pkgs` 和规范化 BuildSpec。
- 模板包含更多 Nix 代码，但这份重复是 Release 可复现性边界的一部分。
- 本决定取代 ADR-0012 中“Kernel 必须锁定独立 kdlib input”的部分，并细化
  ADR-0035 的函数参数契约。
