---
status: accepted
---

# 只有 Registry Access Failure 触发 Failover

Primary 发生连接、超时、TLS、认证、限流或服务失败等 Access Failure 时，加载才按配置顺序切换 Secondary；Primary 明确 404 仍直接触发 Local JIT。Registry 一旦成功返回 Artifact，digest、类型、BuildKey、Release、归档或 ELF 等任何内容校验失败都立即报错，不切换 Secondary，也不进入 JIT；Primary 不可访问时，第一个能返回有效 Artifact 或明确 404 的 Secondary 成为本次加载的权威 Registry。
