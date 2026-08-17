---
status: accepted
---

# v1 不强制 Artifact Signature

v1 不要求 Cosign 或 Notation 签名，完整性依赖 TLS/Registry auth、OCI digest、Release digest、BuildSpec/BuildKey 重算以及本地 ELF/ABI/依赖校验。签名身份、密钥轮换、Dev Version 签名和多 Registry replication 作为未来可选 trust policy 扩展，不进入 v1 发布与加载协议。
