# Publishing Workflow

Status: Accepted

## Initial Release Publication

源码发布：

```bash
k-dash publish --version "1"
```

带 AOT Build 的源码发布：

```bash
k-dash publish \
  --version "1" \
  --cuda-version 13.2 \
  --cc sm_100a \
  --aot-args aot1.json \
  --aot-args aot2.json
```

Source Release 始终存在。没有 `--aot-args` 时禁止要求或推导 AOT Target；存在任意 `--aot-args` 时 `--cuda-version` 和 `--cc` 必填。

在修改任何 Registry tag 前，命令必须：

1. 验证 Kernel Project Contract 与 Registry 配置，并解析本机凭据；失败时不开始编译。
2. 规范化 Kernel Source Package 并在本地计算 Release Artifact digest。
3. 读取并规范化所有 AOT Args；每个文件必须是单一 JSON object。
4. 使用显式 TargetSpec（重复 `--cuda-version` 时为每个 CUDA 版本生成一个 TargetSpec，共享 `--cc`） 计算 BuildSpec/BuildKey，并去重相同 BuildKey。
5. 在 AOT Builder Container 中完成全部构建。
6. 验证所有 Build Artifact 的 TVM-FFI、ELF、ABI、依赖与 Provenance 契约。
7. 只有全部成功后才上传 blobs、manifests 与 tags。

任一构建或校验失败都不得改变 Registry tag。

## Build Addition

```bash
k-dash publish-build \
  --version "1" \
  --cuda-version 13.2 \
  --cc sm_100a \
  --aot-args aot3.json
```

`publish-build` 从当前 `k-dash.toml` 读取 Kernel identity，但不使用工作区源码：

1. 解析 Version 到 Release digest。
2. 从 Registry 下载并验证该 digest 的 Source Artifact。
3. 以已发布源码和指定 Args/Target 构建。
4. 向所有 Registry 追加确定性 `build-<BuildKey>` tag。
5. 相同 Artifact digest 幂等成功，不同 digest 报告 `NonReproducibleBuild`。

对 Dev Version，构建完成后在提交前再次向 Primary 解析 Version；Release digest 已改变时报告 `DevVersionMoved`，不能把旧 Release 的 Build 发布到新绑定下。

## Multiple CUDA toolkits

`publish --cuda-version 12.8 --cuda-version 13.0 --cc sm_90a --aot-args args.json`
builds the Cartesian product of CUDA targets and AOT args under one Source
Release. Duplicate BuildKeys are deduplicated. All builds and validations
finish before any registry upload; failure in either toolkit publishes nothing.
The Python `publish_release(cuda=...)` accepts either the existing string or
a list of CUDA version strings. `build` and `publish-build` retain one target.

All build commands accept `--tvm-ffi-version` (default `0.1.13.post3` for
compatibility); Python build/publication functions accept `tvm_ffi=...`.
For example, add `--tvm-ffi-version 0.1.9` for a runtime pinned to 0.1.9.
The source package must supply headers and a library for the requested version.
Runtime Target Detection uses the installed `apache-tvm-ffi` version, so builds
for different TVM-FFI versions have different keys; exact runtime validation
remains mandatory. Multi-CUDA publication shares this TVM-FFI version.
