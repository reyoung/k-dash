---
status: superseded by ADR-0011
---

# 整数 Version 精确标识不可变 Release

Kernel Version 是 Kernel 内唯一的整数，每个 `(Kernel, Version)` 精确标识一个不可变 Release。Version 不具有 SemVer、版本范围或“同一主版本取最新”的语义，也不提供 `latest` 等浮动引用；它标识源码包和 Release 元数据，而不是某一个 BuildSpec 或二进制。
