---
status: accepted
---

# Host CUDA Dependency 使用逻辑声明

Kernel 必须在 `build.nix` 通过 k-dash 维护的逻辑名称显式声明 Host CUDA Dependency，不能自行声明任意 SONAME；发布时声明集合必须与实际 `DT_NEEDED` 完全一致。k-dash 根据 TargetSpec 的 CUDA Toolkit Version 把逻辑名称解析为对应 ABI major，例如 `cublas` 在不同 CUDA 发行版可解析为 `libcublas.so.12` 或 `libcublas.so.13`，并把解析结果写入 Build Artifact config。
