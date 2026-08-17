---
status: accepted
---

# BuildKey 是规范化 BuildSpec 的 SHA-256

BuildSpec v1 只包含 `buildspec_version`、`release_digest`、规范化 `args` 与精确 `target`，使用 RFC 8785 JCS 序列化后计算 SHA-256，并以 `sha256:<hex>` 表达 BuildKey、以 `build-sha256-<hex>` 表达 OCI tag。Version、Registry、时间、Builder Image 和 Build Provenance 不进入 BuildKey；Release digest 已覆盖源码、Schema、构建入口与 Nix lock。
