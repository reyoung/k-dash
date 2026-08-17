---
status: accepted
---

# Version 是字符串且 `dev-` 绑定可更新

Kernel Version 改为不具有 SemVer 语义的字符串；非 `dev-` Version 首次发布后永久绑定同一 Release digest，重复发布只允许相同 digest 的幂等补齐。以 `dev-` 开头的 Version 是可更新的开发绑定，允许发布新源码时改指向新的不可变 Release digest；“覆盖源码”不修改已有 OCI blob，Materialized Build 也始终引用具体 Release digest 而不是可变 Version 字符串。
