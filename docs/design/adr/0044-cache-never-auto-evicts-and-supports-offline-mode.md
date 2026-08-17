---
status: accepted
---

# Cache 不自动淘汰并支持 Offline Mode

v1 `load` 永不自动淘汰 Local Cache，只通过显式 cache 管理命令查看、裁剪或清空。`K_DASH_OFFLINE=1` 禁止 Registry 请求：已缓存 Build 直接加载，已缓存 Source 可配合 Nix offline mode 尝试 Local JIT，Dev Version 使用最后解析 digest 并警告可能过期，缺失 Resolution、Source 或 Nix closure 时报告 `OfflineCacheMiss` 而不联网补齐。
