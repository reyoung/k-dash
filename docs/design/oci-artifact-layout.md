# OCI Artifact Layout

Status: Accepted

## Repository mapping

每个 Registry 中，一个 Kernel 使用一个 OCI Repository：

```text
<registry-url>/<repository-prefix>/<owner>/<kernel>
```

`owner/kernel` 必须已经是合法的小写 OCI repository path。k-dash 不进行静默转小写或字符替换。

## Tags

```text
release-<version>     # Version 到 Release Artifact 的绑定
build-<build-key>     # BuildSpec 到 Build Artifact 的精确映射
```

Version 必须满足添加 `release-` 前缀后的 OCI tag 字符和长度限制。非 `dev-` Version tag 不可重绑定；`dev-` Version tag 遵循 [ADR-0015](./adr/0015-dev-versions-resolve-through-primary-and-cache-by-digest.md) 的 Primary 权威更新规则。

## Release Artifact

```text
manifest mediaType: application/vnd.oci.image.manifest.v1+json
artifactType:        application/vnd.k-dash.release.v1
config mediaType:    application/vnd.k-dash.release.config.v1+json
source layer:        application/vnd.k-dash.source.v1.tar+zstd
```

Config 至少描述协议版本、Kernel identity、Version、Args Schema 和源码 layer digest。源码 layer 是经过 `.k-dash-ignore` 筛选并规范化打包的 Kernel Source Package，其中包括 `k-dash.toml`、`README.md`、`build.nix`、`flake.nix`、`flake.lock`、`args.schema.json` 和 `.k-dash-ignore`。

## Build Artifact

```text
manifest mediaType: application/vnd.oci.image.manifest.v1+json
artifactType:        application/vnd.k-dash.build.v1
config mediaType:    application/vnd.k-dash.build.config.v1+json
binary layer:        application/vnd.k-dash.binary.v1.tar+zstd
```

Config 至少描述 Release digest、完整 BuildSpec、BuildKey、Build Provenance、Host CUDA Dependency 和二进制 layer digest。v1 二进制 layer 只包含单个 TVM-FFI `kernel.so`，不包含源码、Python glue 或其他动态库。

## Optional Referrers integration

Binary Hit 只通过确定性 `build-<build-key>` tag 完成。支持 OCI Referrers 的 Registry 可以额外发布 Link Artifact，将 Build Artifact 关联到 Release Artifact；Link 只服务于 `list-builds`、Registry UI 和垃圾回收，不参与 `load` 的正确性，也不改变核心 Artifact digest。
