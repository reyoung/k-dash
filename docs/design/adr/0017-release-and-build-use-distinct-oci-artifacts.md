---
status: accepted
---

# Release 与 Materialized Build 使用不同 OCI Artifact

Release Artifact 使用独立 config 和源码归档 layer 表达不可变 Kernel Release；Build Artifact 使用独立 config 和二进制归档 layer 表达某个 Release 下的一个 Materialized Build。客户端可以先读取小型 config 完成 Version、Args Schema 和 BuildSpec 处理，只有 Binary Miss 才下载源码 layer。
