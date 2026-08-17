# Init Templates

Status: Accepted

## CLI

```bash
k-dash init owner/kernel \
  --template cpp \
  [--license Apache-2.0] \
  [PATH]
```

- `owner/kernel` 必填并写入 `k-dash.toml`。
- v1 template 枚举为 `cpp`、`cutedsl`，默认 `cpp`。
- Triton template 延后支持。
- `--license` 可选且没有默认值；未提供时 manifest 不含 license key。
- 未指定 PATH 时在当前目录创建 `<kernel>` 子目录。
- PATH 指向不存在目录时创建，指向空目录时直接写入。

## Shared output

所有模板生成：

```text
k-dash.toml
README.md
build.nix
flake.nix
flake.lock
args.schema.json
.k-dash-ignore
.gitignore               # 非发布强制文件
src/                     # 模板源码
```

Template 随 k-dash 版本携带固定的 `flake.lock`，初始化不要求 GPU，也不现场选择浮动依赖版本。

## Template-specific content

### `cpp`

生成最小 CUDA C++ kernel、TVM-FFI export 和把 Args/Target 转换为安全 C++ 静态参数的 `build.nix`。

### `cutedsl`

生成最小 CuteDSL kernel、AOT TVM-FFI export 和固定 CuteDSL 工具链的 Nix inputs，最终仍输出单个 `kernel.so`。

### Future `triton`

Triton 将作为后续 template 加入，不能改变 Project 或 Build API。

## Filesystem safety

- 目标非空时列出冲突并失败。
- v1 不提供 `--force`，不覆盖文件。
- 不自动执行 `git init`。
- 初始化完成后只运行静态项目校验，不执行完整 CUDA build。
