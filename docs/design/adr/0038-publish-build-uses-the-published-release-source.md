---
status: accepted
---

# `publish-build` 使用已发布 Release Source

`publish-build` 只从当前 `k-dash.toml` 获取 Kernel identity，随后按 Version 解析 Release digest、下载并验证 Registry 中的 Source Artifact，再在 AOT Builder Container 中构建并向所有 Registry 追加 Build Artifact，不能使用当前工作区源码。已存在相同 digest 为幂等成功，不同 digest 为 `NonReproducibleBuild`；对 Dev Version，构建完成后必须重新解析 Primary，指针已移动则报告 `DevVersionMoved` 并拒绝提交。
