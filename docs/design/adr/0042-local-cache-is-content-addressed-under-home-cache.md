---
status: accepted
---

# Local Cache 在 `~/.cache/k-dash/` 按内容寻址

k-dash 默认使用 `~/.cache/k-dash/`，允许通过 `K_DASH_CACHE_DIR` 覆盖；Release 内容按 Release digest 保存，Build 内容按 BuildKey 保存，Version 只缓存 Resolution 结果。Dev Version 移动只新增新的 digest 绑定，不覆盖旧 Source 或 Build cache entry。
