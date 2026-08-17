---
status: accepted
---

# 每个 Kernel 使用独立 OCI Repository

每个 Registry 中，一个逻辑 Kernel 映射到 `${repository_prefix}/${owner}/${kernel}`，该 Repository 同时保存该 Kernel 的所有 Release Artifact 与 Build Artifact。`owner/kernel` 必须已经满足小写 OCI repository path 规则，k-dash 对非法名称直接拒绝而不做可能产生碰撞的静默规范化。
