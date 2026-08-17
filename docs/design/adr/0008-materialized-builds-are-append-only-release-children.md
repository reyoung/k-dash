---
status: accepted
---

# Materialized Build 是 Release 的可追加子产物

Kernel Release 发布后仍可通过独立命令追加新的 Materialized Build，但不能修改 Release 的源码或元数据。每个追加二进制必须引用原 Release 和自身 BuildSpec；运行时加载产生的本地构建不会隐式上传，只有显式且具有发布权限的命令才能把二进制追加到 Registry。
