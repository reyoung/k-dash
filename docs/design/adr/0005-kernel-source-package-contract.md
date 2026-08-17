---
status: accepted
---

# Kernel Source Package 具有强制根文件契约

Kernel Source Package 根目录必须包含非空 `README.md`、`build.nix`、`args.schema.json` 和 `.k-dash-ignore`。README 只承载公开 API、参数、示例和限制等人类文档，机器不能从中推导契约；源码包使用项目根相对的 ignore 规则筛选文件，并内建排除 `.git/`、本地构建产物和越界 symlink，任何强制文件缺失或被 ignore 都必须使发布失败，`.k-dash-ignore` 本身进入源码包以保证边界可审计和重现。
