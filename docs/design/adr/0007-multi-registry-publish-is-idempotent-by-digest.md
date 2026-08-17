---
status: superseded by ADR-0011
---

# 多 Registry 发布按 Release Digest 幂等

重复发布同一 `(Kernel, Version)` 时，只有待发布 Release Manifest digest 与已有 digest 完全相同才视为幂等成功，不同 digest 必须作为不可覆盖的版本冲突。发布需要核实所有配置的 Registry 都得到同一 digest 才返回整体成功；部分失败保留逐 Registry 结果并允许以相同输入重试，从而在没有跨 Registry 原子事务的条件下安全补齐副本。
