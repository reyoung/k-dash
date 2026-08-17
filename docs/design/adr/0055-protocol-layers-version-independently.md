---
status: accepted
---

# 各协议层独立版本化

Global config schema、Kernel Project format、Kernel Build API、BuildSpec 与 OCI config/media type 各自拥有独立版本；未知版本直接拒绝，不能猜测兼容。规范化或 Hash 输入变化升级 BuildSpec version，构建函数边界变化升级 build API，不兼容 Artifact 变化使用新 media type；既有 Artifact 永不原地迁移或重解释，CLI 可以新增旧版本读取器但新发布默认使用当前协议。
