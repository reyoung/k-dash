# Kernel Project Contract

Status: Accepted

## Required root files

```text
k-dash.toml
README.md
build.nix
flake.nix
flake.lock
args.schema.json
.k-dash-ignore
```

所有强制文件必须进入 Kernel Source Package，不能被 `.k-dash-ignore` 排除。README 必须非空，但不作为机器契约读取。

## `k-dash.toml`

```toml
format-version = 1
name = "owner/kernel"
build-api = 1
# license = "Apache-2.0"  # optional
```

`name` 必须是合法小写 OCI repository path，并决定每个 Registry 中 `${repository_prefix}/${owner}/${kernel}` 的目标 Repository。`license` 可选且没有默认值。Manifest 不保存 Kernel Version、Args Schema 或 Host CUDA Dependency。

## `build.nix`

固定接口的概念形式为：

```nix
{
  pkgs,
  buildSpec,
}:
let
  # `k-dash init` 在这里内联并冻结构建 helper 及其依赖 hash。
  mkTvmFfiKernel = /* self-contained helper */;
in mkTvmFfiKernel {
  hostCudaDependencies = [ ];
  build = /* kernel-specific derivation from buildSpec */;
}
```

约束：

- `build.nix` 是唯一 Kernel 构建逻辑入口。
- `flake.nix` 与 `flake.lock` 声明并锁定 nixpkgs、CUDA 与 DSL inputs；v1 不存在独立 `kdlib` input。
- `k-dash init` 把构建 helper 的实现和固定依赖 digest 直接写入 `build.nix`。这些 helper 随 Kernel Release 冻结，旧项目不会因 k-dash package 升级而改变构建语义。
- k-dash 以生成的 Nix expression 传入 BuildSpec，不使用环境变量。
- Nix evaluation 必须 pure，build 必须 sandboxed。
- Kernel 自行决定 Args/Target 到语言静态参数的安全转换，禁止未经转义拼接 shell。
- 唯一合法输出为包含单个普通文件 `$out/kernel.so` 的 derivation。
- 输出不能包含 Python、其他 `.so`、symlink、设备文件或额外产物。
- 发布前必须验证 `DT_NEEDED` 与声明的 `hostCudaDependencies` 完全一致。
