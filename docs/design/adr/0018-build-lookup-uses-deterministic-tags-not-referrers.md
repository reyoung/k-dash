---
status: accepted
---

# Build 查找使用确定性 Tag 而不依赖 Referrers

Release 通过 `release-<version>` tag 解析，Build 通过完整 BuildSpec 推导的 `build-<build-key>` tag 精确查找，因此加载正确性不依赖 OCI Referrers API，也不维护有并发覆盖风险的全量 Build Index。支持 Referrers 的 Registry 可以额外保存 Link Artifact 用于列表、UI 和垃圾回收，但 Registry 能力差异不能改变核心 Release 或 Build digest。
