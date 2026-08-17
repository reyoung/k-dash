---
status: superseded by ADR-0010
---

# 构建在 Linux Builder Container 中执行

`k-dash build` 的宿主前置条件是可用的 Docker 兼容引擎，而不是 Linux 或宿主 Nix；`build.nix` 在标准 Linux Builder Container 内求值和执行，因此 macOS 与 Linux 宿主共享同一构建路径。`k-dash init` 默认生成 `.devcontainer` 供内核开发使用，但该目录不是发布时强制存在的 Kernel Source Package 根文件。
