# Build Artifact Runtime Contract

Status: Accepted

## Module contract

`build.nix` 对一个 BuildSpec 产出单个 TVM-FFI `kernel.so`。该模块可以导出多个函数；v1 不生成、分发或执行 Python glue。`k_dash.load` 返回加载后的 TVM-FFI Module。

Binary layer 的内容严格为：

```text
kernel.so
```

Build Artifact config 承载 BuildSpec、BuildKey、Build Provenance、Host CUDA Dependency 和文件 digest 等元数据，不在 layer 内重复生成机器契约。

## Dynamic dependencies

Artifact 不打包其他共享库，也不允许使用相对或绝对 RPATH/RUNPATH 寻找私有依赖。

基础 Linux ABI allowlist 为：

```text
Linux dynamic loader
libc.so.6
libm.so.6
libdl.so.2
libpthread.so.0
librt.so.1
精确 TVM-FFI runtime ABI
```

`libstdc++.so.6` 和 `libgcc_s.so.1` 不属于 allowlist，必须由 `build.nix` 静态链接。基础 ABI 之外，`DT_NEEDED` 只能引用 k-dash 内建清单认可且由 Kernel 显式声明的 Host CUDA Dependency，例如 CUDA Driver、CUDA Runtime、cuBLAS 和 NCCL。

Kernel 在 `build.nix` 声明逻辑依赖名，k-dash 按 TargetSpec 的 CUDA Toolkit Version 解析实际 SONAME ABI major；例如 `cublas` 可以在 CUDA 12 与 CUDA 13 分别解析为 `libcublas.so.12` 与 `libcublas.so.13`。发布时逻辑声明和实际 `DT_NEEDED` 必须完全一致。

Build Artifact config 对每项依赖记录：

```json
{
  "name": "cublas",
  "soname": "libcublas.so.13",
  "min_version": "<minimum-compatible-version>"
}
```

Loader 按 SONAME ABI major 与最低版本验证，不要求精确 patch。Host Dependency Requirement 不进入 BuildKey；缺失或过旧时报告 `MissingHostDependency` 或 `IncompatibleHostDependency`，不进入 Local JIT。

## Platform baseline

- OS: Linux
- architectures: `x86_64`, `aarch64`
- libc baseline: `manylinux_2_28`
- framework ABI: 精确 TVM-FFI ABI
- CUDA target: 精确 CUDA Toolkit `major.minor` 与 CUDA CC

## Validation before load

1. 验证 OCI manifest、config 与 layer digest。
2. 重算并比较 BuildSpec 与 BuildKey。
3. 拒绝归档路径穿越、绝对路径和越界 symlink。
4. 验证 layer 只含 `kernel.so`，且 ELF machine 匹配 TargetSpec。
5. 验证 `DT_NEEDED` 属于基础 Linux ABI或已声明的 Host CUDA Dependency。
6. 验证 GLIBC、GLIBCXX 与 CXXABI symbol version 不超过 baseline。
7. 拒绝 RPATH、RUNPATH 与 `/nix/store` 路径泄漏。
8. 验证 TVM-FFI ABI 与 CUDA Driver/Library 可用性后才调用 TVM-FFI loader。
