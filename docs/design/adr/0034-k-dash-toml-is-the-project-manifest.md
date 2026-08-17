---
status: superseded by ADR-0039
---

# `k-dash.toml` 是强制 Project Manifest

Kernel Source Package 必须包含 `k-dash.toml`，以版本化强类型格式声明 `name = "owner/kernel"`、license 与 build API version；它是 `init`、校验、OCI Repository 定位和发布 identity 的唯一机器权威。Version 仍由发布命令提供，Args 由 `args.schema.json` 定义，Host CUDA Dependency 由 `build.nix` 声明，README 不参与机器解析。
