---
status: accepted
---

# 每个 AOT Args 文件定义一个 BuildSpec

每个重复的 `--aot-args <file>` 只包含一个 Kernel Args JSON object，不能包含 Version 或 Target 字段；同一次命令的所有文件共享 `--cuda-version` 与 `--cc` 形成的 TargetSpec。每个对象独立应用 Args Schema 与规范化，重复 BuildKey 只构建一次并报告 deduplication，不同 Target 使用后续 `publish-build` 追加。
