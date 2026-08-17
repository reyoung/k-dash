---
status: accepted
---

# Configured Registry 是原生代码 Trust Boundary

出现在 `~/.config/k-dash.yaml` 中的 Primary 与 Secondary Registry 都被视为 Trusted Registry，可以提供最终在训练或推理进程内执行的 `kernel.so`，也可以提供被 Nix 构建后加载的 JIT Source。v1 不增加每次加载的 `trust_remote_code` 开关或 publisher allowlist；配置 Registry 本身就是执行信任授权，文档必须明确说明这一后果。
