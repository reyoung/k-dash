---
status: accepted
---

# Local Build 只提交到 Local Cache

验证成功的 `k-dash build` 直接原子提交到 `~/.cache/k-dash/builds/<BuildKey>/`，输出 BuildKey、would-be Release digest、`kernel.so` 路径、Build Provenance 和 cache hit 状态；v1 不生成独立 `dist/`。Build 不访问 Registry，后续 publish 只有在 Source/Version/Args/Target 与验证元数据完全一致时才能复用该 cache entry。
