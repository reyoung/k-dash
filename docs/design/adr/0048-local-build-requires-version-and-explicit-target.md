---
status: accepted
---

# Local Build 要求 Version 与显式 Target

`k-dash build` 必须指定字符串 Version、CUDA Toolkit Version 与 CC，可以重复 `--args`，省略 Args 文件时使用空对象并应用 Schema defaults。命令按发布规则规范化当前 Source Package 并构造 would-be Release digest，因此相同源码、Version、Args 与 Target 的 Local Build 和后续 Release Publication 具有相同 BuildSpec/BuildKey；只有 publish 才在 Registry 占用 Version。
