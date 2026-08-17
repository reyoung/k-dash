---
status: accepted
---

# Init 拒绝非空目录且不初始化 Git

`k-dash init` 只创建不存在的目标或写入空目录，目录中存在任何文件时列出冲突并失败；v1 不提供 `--force`。命令不执行 `git init`，可以生成非强制 `.gitignore`，结束前只做 manifest、schema、ignore、flake lock 和模板结构的静态校验，不自动执行完整 CUDA build。
