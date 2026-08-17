# Trust and Sandbox

Status: Accepted

## Native code trust

Kernel Binary 与 JIT Source 最终都会产生在调用进程内执行的原生代码。Nix sandbox 只限制构建过程，不能限制已加载 Kernel Module 的行为。

Registry Set 中每个 Registry 都是 Trusted Registry：将 Registry 写入配置，即授权其向当前用户提供可执行 Kernel。v1 不提供 per-load `trust_remote_code`、publisher allowlist 或未配置的默认公共 Registry。

## Integrity without mandatory signatures

v1 不强制 Cosign/Notation，完整性链为：

1. TLS 与 Registry auth。
2. OCI manifest/config/layer digest。
3. Version 到 Release digest 的绑定规则。
4. BuildSpec 与 BuildKey 重算。
5. Source archive、ELF、ABI 与 Host Dependency 本地校验。

Artifact signature 与 signer identity policy 作为未来扩展，不属于 v1。

## Local JIT isolation

- Nix evaluation 必须 pure。
- 普通 build sandbox 禁止网络。
- `flake.lock` 固定且带 hash 的 fetcher 可以由 Nix 在受控阶段获取依赖。
- Registry credentials、环境变量 secret 和用户 home 不传入 build sandbox。
- `load` 同步等待 JIT。
- 默认 JIT timeout 为 30 分钟，`K_DASH_JIT_TIMEOUT` 可覆盖。
- `K_DASH_NIX_MAX_JOBS` 可限制 Nix 并行度。
- 超时或取消终止本次 Nix build，不提交 Build cache entry；Nix store 已完成对象可以保留。
- 等待同一 BuildKey 的进程接收同一次失败；新的调用可以重新尝试。
