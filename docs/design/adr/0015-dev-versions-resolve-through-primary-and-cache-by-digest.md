---
status: accepted
---

# Dev Version 由 Primary 解析并按 Digest 缓存

公共 API 严格使用字符串 Version，不把整数隐式转换为字符串；每次在线加载 `dev-*` 都向 Primary Registry 解析当前 Release digest，而非开发 Version 的解析结果可永久缓存。源码、Materialized Build 和本地模块缓存均以 Release digest 与 BuildSpec 为身份，Dev Version 改指后新调用可加载新模块而既有对象继续使用旧模块；只有显式离线模式才能使用上次解析结果并必须警告可能过期。

发布新的 Dev Version 时，先向所有 Registry 上传按 digest 寻址的 Release 和 AOT blobs，成功后最后更新 Primary 上的 `dev-*` 绑定。加载端从 Primary 获得 digest 后可从任意 Registry 下载对应内容；Primary 不可用时不能从 Secondary 猜测 Dev Version 的当前指向。
