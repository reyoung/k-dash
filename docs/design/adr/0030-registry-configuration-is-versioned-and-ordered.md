---
status: accepted
---

# Registry 配置版本化且具有顺序

`~/.config/k-dash.yaml` 使用拒绝未知字段的版本化 schema，Registry `name` 唯一、必须且只能有一个 `primary: true`，其余 Registry 按 YAML 顺序组成 Secondary failover 链。配置缺失不影响 `init` 和本地 `build`，但所有远端 `load`、`publish` 操作必须失败而不能使用隐式公共 Registry。
