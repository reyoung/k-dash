---
status: accepted
---

# Local Build 在所有宿主上都通过 Docker

`k-dash build` 在 macOS 与 Linux 上始终使用 Docker-compatible API，宿主不要求 Nix、Linux 或 GPU；它尊重 Docker Context/`DOCKER_HOST`，按 TargetSpec 选择 Linux container platform，并以 archive stream 传入源码、取回结果而不依赖 bind mount。默认 Builder Image 可浮动且允许覆盖，实际 image digest 只进入 Build Provenance，Registry credentials、用户 home 和 GPU 不挂入容器。
