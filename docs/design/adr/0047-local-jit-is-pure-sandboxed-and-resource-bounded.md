---
status: accepted
---

# Local JIT Pure、Sandboxed 且有资源边界

Local JIT 使用 pure Nix evaluation，普通 build sandbox 禁止网络，只有 `flake.lock` 固定且带 hash 的 fetcher 可由 Nix 受控获取依赖；Registry credentials、用户 secrets 与 home 不传入 sandbox。`load` 同步等待 JIT，默认超时 30 分钟并可由 `K_DASH_JIT_TIMEOUT` 调整，Nix 并行度可由 `K_DASH_NIX_MAX_JOBS` 限制；超时或取消不提交 k-dash Build cache entry，等待同一 BuildKey 的调用者收到同一次失败，后续新调用可以重试。
