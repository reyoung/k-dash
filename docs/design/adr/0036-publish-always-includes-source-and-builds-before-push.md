---
status: accepted
---

# `publish` 始终包含 Source 并在推送前完成 AOT

`k-dash publish --version <version>` 始终创建 Source Release，`--aot-args` 为可选的提前物化集合；没有 AOT 时不要求 CUDA/CC，有 AOT 时 `--cuda-version` 与 `--cc` 必填。命令必须先在本地完成并验证所有 AOT Build，任一失败都不得改变任何 Registry tag，全部成功后才进入多 Registry 推送阶段。
