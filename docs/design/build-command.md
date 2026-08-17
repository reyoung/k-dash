# Local Build Command

Status: Accepted

## CLI

```bash
k-dash build \
  --version "dev-local" \
  --cuda-version 13.2 \
  --cc sm_100a \
  [--args args1.json] \
  [--args args2.json] \
  [--builder-image <oci-reference>]
```

- Version、CUDA Toolkit Version 和 CC 必填。
- `--args` 可以重复；省略时使用 `{}`，随后应用 Args Schema defaults。
- 每个 Args object 形成独立 BuildSpec，重复 BuildKey 去重。
- 非 Dev Version 也允许本地使用，但不会在远端占用 Version。

## Identity

命令以与 `publish` 相同的算法：

1. 验证 Kernel Project Contract。
2. 规范化当前 Kernel Source Package。
3. 使用给定 Version 在本地构造 would-be Release Artifact 与 digest。
4. 规范化 Args/Target 并计算 BuildSpec/BuildKey。

因此完全相同的 Local Build cache entry 可以被后续 publish 复用。

## Docker execution

- 所有宿主均通过 Docker-compatible API 执行，不使用宿主 Nix。
- 尊重 Docker Context 与 `DOCKER_HOST`。
- Source 通过 archive stream 输入，结果通过 archive stream 输出，不使用 bind mount。
- Target CPU architecture 决定 `linux/amd64` 或 `linux/arm64` container platform。
- AOT Builder Container 不挂载 GPU、Registry credentials 或用户 home。
- 默认 Builder Image 可以变化，`--builder-image` 可以覆盖；实际 digest 记录在 Build Provenance，不进入 BuildSpec。

## Output

每个通过验证的 Build 原子提交到：

```text
~/.cache/k-dash/builds/<BuildKey>/
├── config.json
└── kernel.so
```

CLI 输出 BuildKey、would-be Release digest、路径、Build Provenance 和 cache hit/rebuilt 状态。命令不访问 Registry，也不生成 `dist/` 目录。
