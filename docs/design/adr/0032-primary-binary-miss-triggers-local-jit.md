---
status: superseded by ADR-0033
---

# Primary Binary Miss 立即触发 Local JIT

Primary Registry 可达且对精确 `build-<BuildKey>` 明确返回 404 时，该结果就是权威 Binary Miss，`k_dash.load` 立即进入 Local JIT，不再查询 Secondary 是否保存了该 Build Artifact。Secondary 用于 Primary 连接、认证、服务或完整性不可用时的容灾；Registry 不可用不能伪装成 Binary Miss，Dev Version 仍必须由 Primary 完成 Release Resolution。
