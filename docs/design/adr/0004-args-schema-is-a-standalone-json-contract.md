---
status: accepted
---

# Args Schema 是独立 JSON 契约

Kernel 在根目录使用独立的 `args.schema.json` 声明 Args Schema，而不是把契约藏在 `build.nix` 中。该文件采用 k-dash 支持的 JSON Schema 子集，是发布工具、加载客户端和 Nix 构建共同消费的唯一权威定义；`build.nix` 可以读取它，但不能维护另一份副本，发布时还会把规范化后的 schema 写入 Release 元数据，使客户端无需下载源码或求值 Nix 即可验证参数。
