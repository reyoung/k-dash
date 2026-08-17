# Registry Configuration and Selection

Status: Accepted

## Configuration

默认配置路径为 `~/.config/k-dash.yaml`：

```yaml
schema_version: 1

registries:
  - name: primary-harbor
    url: https://harbor-a.example.com
    repository_prefix: k-dash
    primary: true
    verify_tls: true
    auth:
      type: basic
      username: robot$k-dash
      password: plaintext-is-supported

  - name: mirror-harbor
    url: https://harbor-b.example.com
    repository_prefix: mirrors/k-dash
    primary: false
    verify_tls: true
    auth:
      type: docker
```

Registry `name` 必须唯一，必须且只能有一个 Primary。`url` 只包含 scheme、host 和可选 port；`repository_prefix` 必须是合法小写 OCI path。未知字段直接报错。

配置缺失不影响 `k-dash init` 与本地 `k-dash build`；需要远端状态的命令报告 `RegistryConfigNotFound`。

## Authentication and TLS

支持以下 auth 类型：

- `anonymous`
- `docker`，可选 `config_path`，支持 Docker credential helper
- `basic`，可直接使用 `username`/`password`，也可使用环境变量引用

YAML 允许保存明文 secret。`verify_tls` 默认为 `true`；`ca_bundle` 用于内部 CA；显式 `verify_tls: false` 时每次远端操作产生安全警告。

## Binary selection

1. 完成 Release Resolution 和 Target Detection。
2. 形成完整 BuildSpec 与 BuildKey。
3. 向 Primary 请求精确 `build-<BuildKey>`。
4. Primary 返回有效 Build Artifact 时验证并加载。
5. Primary 明确返回 404 时立即判定 Binary Miss 并进入 Local JIT，不搜索 Secondary Build Artifact。
6. Primary 发生 Access Failure 时，才按配置顺序进入 Secondary failover。
7. 第一个能返回有效 Artifact 或明确 404 的 Secondary 成为本次加载的权威 Registry；Secondary 404 立即触发 Local JIT，不继续搜索后续 Secondary。

Access Failure 包括连接、超时、TLS、认证、限流和服务可用性失败。Registry 一旦成功返回 Artifact，任何 digest、Artifact type、BuildKey、Release digest、归档或 ELF 校验失败都立即报告错误，不 failover，也不进入 JIT。

Dev Version 的 Release Resolution 不允许绕过 Primary。进入 Local JIT 后，Source Artifact 优先从作出 Binary Miss 判断的权威 Registry 按 Release digest 下载；该下载发生 Access Failure 时可以按同一 digest failover，内容校验失败则直接报错。
