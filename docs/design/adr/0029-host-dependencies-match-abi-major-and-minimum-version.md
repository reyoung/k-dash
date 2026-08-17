---
status: accepted
---

# Host Dependency 按 ABI Major 与最低版本匹配

每项 Host Dependency Requirement 记录逻辑名称、按 CUDA Target 解析出的 SONAME ABI major 与最低运行版本，不要求宿主精确匹配构建时 patch；更新且 ABI 兼容的库可以复用同一 Build Artifact。依赖条件不进入 BuildKey，加载前通过库存在性和供应商版本 API 验证，缺失或过旧时直接报告依赖错误而不进入 Local JIT。
