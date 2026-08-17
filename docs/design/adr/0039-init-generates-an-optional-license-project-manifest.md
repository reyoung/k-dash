---
status: accepted
---

# `init` 生成 License 可选的 Project Manifest

`k-dash init owner/kernel [PATH]` 生成强制 `k-dash.toml`，其中 format version、Kernel name 与 build API version 必填，license 可选；未提供 `--license` 时不写 license key，也不选择默认许可证。未指定 PATH 时创建以 Kernel basename 命名的子目录，默认模板为 `cpp`。
