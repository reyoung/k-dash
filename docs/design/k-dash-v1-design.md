# k-dash v1 Architecture Design

Status: Accepted and frozen for implementation

Date: 2026-08-17

## Purpose

k-dash 是一个 JIT-first、binary-second 的 CUDA Kernel 分发系统。调用者使用精确 Kernel Version 和 Kernel Args 请求一个 BuildSpec：Registry 中存在对应 Build Artifact 时直接下载，否则下载同一 Release 的源码并在 Local JIT Environment 中通过 Nix 构建。源码与二进制都只使用 OCI/Harbor Registry 分发，不依赖额外 Artifact Storage。

## v1 scope

v1 支持：

- 纯 Python `k_dash` package 与 `k-dash` CLI。
- Linux CUDA runtime，CPU architecture 为 `x86_64` 或 `aarch64`。
- macOS/Linux 上通过 Docker 执行无 GPU AOT build。
- C++ 与 CuteDSL project template。
- 单个 TVM-FFI `kernel.so`，无 Python glue。

CuteDSL template 固定 `nvidia-cutlass-dsl==4.6.1`，通过官方 AOT export 生成单一 TVM-FFI Module；其 `libcute_dsl_runtime.so` 作为受版本约束的 Framework Runtime Dependency 由 loader 在 `dlopen(kernel.so)` 前定位和预加载，不进入 Build Artifact。
- 多 Registry 发布与 Primary-first load failover。
- 不可变 Release、可追加 Materialized Build 和可移动 `dev-*` Version。

v1 明确不支持 Triton template、CPU/ROCm/Metal/Windows、macOS runtime、非 TVM-FFI Module、多 CC fat binary、显式 Target override、自动上传 Local JIT、强制 Artifact signature、自动 Cache eviction、以 OCI Referrers 驱动加载，以及 public Resolution/diagnostic API。

## System shape

```text
Kernel author
  │
  ├─ k-dash init ───────────────> Kernel Project
  │                                  │
  ├─ k-dash build ── Docker/Nix ─────┴─> Local Cache Build
  │
  ├─ k-dash publish ─ Docker/Nix ──────> Release + optional Builds
  └─ k-dash publish-build ─ Docker/Nix ─> append Build to Release
                                                │
                                                v
                                      OCI Registry Set
                                      Primary + Secondaries
                                                │
                                                v
Application ─ k_dash.load ─> cache/Registry ─> TVM-FFI Module
                                  │ Binary Miss
                                  v
                          Source + local Nix JIT
```

主要实现组件：

| Component | Responsibility |
| --- | --- |
| `api` | 同步 `load` 与进程内 Module cache |
| `config` | Global Registry config 与 Kernel Project Manifest |
| `spec` | Args Schema、TargetSpec、BuildSpec、BuildKey |
| `registry` | OCI Distribution push/pull、auth、failover |
| `cache` | Content-addressed disk cache 与跨进程锁 |
| `build` | Nix Build Contract、Local JIT、Docker AOT |
| `publish` | Release Publication 与 Build Addition |
| `cli` | `init`、`build`、`publish`、`publish-build`、`cache` |

OCI 操作直接调用 Distribution HTTP API，不依赖 `oras`。TVM-FFI 是 Python runtime dependency；Local JIT 调用宿主 Nix，Local AOT/Publish 调用 Docker。

## Identity model

### Version and Release

Kernel Version 是不具有 SemVer 语义的字符串。非 `dev-` Version 首次发布后永久绑定一个不可变 Release digest；重复请求只有 digest 相同时才是幂等。`dev-*` 是 Primary Registry 权威维护的可移动绑定：更新 Dev Source 会生成新的不可变 Release，再移动 Version tag，旧 Release 不被修改。

Materialized Build 始终引用具体 Release digest，不引用可变 Version。Dev Version 的新旧 Build 因而不会串包。

### BuildSpec and BuildKey

BuildSpec v1：

```json
{
  "buildspec_version": 1,
  "release_digest": "sha256:<release-manifest-digest>",
  "args": {},
  "target": {}
}
```

Kernel Args 先按 `args.schema.json` 应用 defaults、验证并转成 RFC 8785 JCS/I-JSON。BuildKey 是规范 BuildSpec 的 SHA-256：

```text
BuildKey = sha256(JCS(BuildSpec))
OCI tag  = build-sha256-<64 lowercase hexadecimal characters>
```

Registry、Version alias、时间、Builder Image 与 Provenance 不进入 BuildKey。详见 [BuildSpec and BuildKey](./buildspec-and-buildkey.md)。

## Kernel Project Contract

强制根文件：

```text
k-dash.toml
README.md
build.nix
flake.nix
flake.lock
args.schema.json
.k-dash-ignore
```

`k-dash.toml` 提供 Kernel identity 与 build API version，license 可选。`build.nix` 是 pure、sandboxed 的自包含固定函数，只接收锁定的 `pkgs` 与 BuildSpec；`k-dash init` 把 `mkTvmFfiKernel` 等构建 helper 的实现直接冻结进该文件，不依赖额外 `kdlib` input。唯一有效输出是普通文件 `$out/kernel.so`。Kernel 自行把结构化 Args/Target 转成 C++ template、CuteDSL 参数或编译设置。详见 [Kernel Project Contract](./kernel-project-contract.md)。

## Python load flow

Public API：

```python
module = k_dash.load(
    "owner/kernel",
    version="1",
    jit_args={"block_m": 128},
)
```

端到端顺序：

1. 读取并验证 `~/.config/k-dash.yaml`；其中每个 Registry 都是可执行代码 trust boundary。
2. Primary-first 解析 `release-<version>`。Dev Version 每次必须由 Primary 解析；Offline 使用上次缓存并警告可能过期。
3. 读取 Release config 和 Args Schema，规范化 Kernel Args。
4. Target Detection 获取 CUDA Toolkit Version 与逻辑 GPU 0 的 CC：`nvcc --version` 优先，缺失时使用 `torch.version.cuda`；两者都不可用则失败。CC 低于 9.0 使用普通 `sm_<xy>`，9.0 及以上使用精确 `sm_<xy>a`。
5. 计算 BuildSpec 与 BuildKey，先检查进程内 Loaded Module cache，再检查 Local Cache。
6. 请求权威 Registry 的 `build-<BuildKey>`。Primary 明确 404 立即 Binary Miss 并进入 JIT，不搜索 Secondary；只有 Registry Access Failure 才进入 Secondary failover。Registry 返回内容后任何完整性或语义错误都直接失败。
7. Binary Hit 时下载并完整验证 Build Artifact；Binary Miss 时下载同一 Release digest 的 Source Artifact，检查 Nix 环境并 Local JIT。
8. 验证 `kernel.so` 的 digest、BuildKey、ELF、ABI、Host Dependency 与 TargetSpec，之后调用 TVM-FFI loader。
9. 同一 BuildKey 在进程内返回同一 Module object；Dev Version 移动后新调用加载新 Module，旧对象继续有效。

详细规则见 [Python API](./python-api.md)、[Registry Configuration](./registry-configuration.md)、[Local Cache](./local-cache.md) 和 [Build Artifact Runtime Contract](./build-artifact-runtime.md)。

## Target and runtime compatibility

TargetSpec 与 Kernel Args 分离。公共 `load` 不接受显式 Target。

- CUDA Toolkit Version：宿主 `nvcc` 优先，PyTorch build CUDA version 只作 fallback；冲突时 `nvcc` 胜出。
- CUDA CC：`CUDA_VISIBLE_DEVICES` 重映射后的逻辑 GPU 0，一个 BuildSpec 只描述一个 CC。
- Platform：Linux `x86_64`/`aarch64`，manylinux_2_28 baseline，精确 TVM-FFI ABI。
- CC 9.0 及以上默认使用 architecture-specific `a` target，不自动使用 `f` 或普通 CC fallback。

Build Artifact 只包含 `kernel.so`，不包含 Python 或其他动态库。基础 Linux ABI 使用严格 allowlist；Kernel 与 TVM-FFI 共享进程中同一份动态 `libstdc++.so.6`/`libgcc_s.so.1`，Build config 记录并在加载前验证 `GLIBCXX`/`CXXABI` 要求。Kernel 在 `build.nix` 声明逻辑 Host CUDA Dependency，k-dash 按 CUDA Target 解析 SONAME ABI major，例如 CUDA 12/13 的 cuBLAS 可以分别解析为 `.12`/`.13`；加载按 ABI major 与最低版本验证，不要求精确 patch。

## OCI distribution

每个 Kernel 在每个 Registry 中占一个 Repository：

```text
<registry>/<repository-prefix>/<owner>/<kernel>
```

Tag：

```text
release-<version>
build-<build-key>
```

Release Artifact 的 config 保存协议、identity、Version 与 Args Schema，layer 保存规范 Source Package。Build Artifact 的 config 保存 Release digest、BuildSpec、BuildKey、Provenance 与 Host Dependencies，layer 只保存 `kernel.so`。

Binary lookup 使用确定性 Build tag，不依赖 Referrers。支持 OCI 1.1 Referrers 的 Registry 可以额外保存 Link Artifact，只用于 listing、UI 与垃圾回收。详见 [OCI Artifact Layout](./oci-artifact-layout.md)。

## Registry Set

`~/.config/k-dash.yaml` 是拒绝未知字段的版本化配置，必须且只能有一个 Primary。Auth 支持 anonymous、Docker credentials/helper、环境变量引用和 YAML 明文 basic credentials；TLS 默认验证，可设置 CA bundle 或显式关闭并警告。

Load 语义：

- Primary 返回有效 Build：验证并加载。
- Primary 404：立即 JIT。
- Primary Access Failure：按 YAML 顺序切换 Secondary。
- 第一个返回有效 Build 或明确 404 的 Secondary 成为本次权威。
- Registry 已返回内容后的任何校验失败：直接报错，不 failover、不 JIT。
- Dev Version Resolution 不能绕过 Primary。

Publish 对所有 Registry 执行，整体成功要求所有目标得到预期 digest；相同 digest 可以幂等重试。Dev Version 在全部 content 上传完成后最后更新 Primary binding。

## Build and publication

### Local AOT build

`k-dash build` 要求 Version、CUDA Toolkit Version 与 CC，所有宿主都通过 Docker 执行，无需宿主 Nix/Linux/GPU。Source/Result 通过 archive stream 传输，支持远程 Docker daemon，不使用 bind mount。结果只进入 `~/.cache/k-dash/builds/<BuildKey>/`，不访问 Registry或创建 `dist/`。

### Release Publication

`k-dash publish` 始终发布 Source Release；AOT Args 可选。有 AOT 时 Target 必须显式给出，并在修改任何 Registry tag 前完成所有 build/validation。每个 `--aot-args` 文件是一个 Args object，同一命令共享一个 Target，重复 BuildKey 去重。

### Build Addition

`k-dash publish-build` 只从当前 manifest 获取 Kernel identity，实际下载 Registry 中精确 Release Source 后构建。Dev Version 在提交前重新解析，移动则报告 `DevVersionMoved`。详见 [Local Build Command](./build-command.md) 与 [Publishing Workflow](./publishing-workflow.md)。

## Cache and concurrency

默认 cache 根为 `~/.cache/k-dash/`，可由 `K_DASH_CACHE_DIR` 覆盖。Release 与 Build 按 digest/BuildKey 保存，Version 只保存 Resolution。每个 BuildKey 使用跨进程 advisory lock，临时目录通过同文件系统 atomic rename 提交；同一 BuildKey 不重复编译，不同 BuildKey 可以并行。

v1 不自动淘汰。`K_DASH_OFFLINE=1` 禁止 Registry 请求；缓存 Build 可以加载，缓存 Source 可以在 Nix offline mode 下尝试 JIT，缺少 Resolution/Source/Nix closure 时报告 Offline Cache Miss。

## Trust and sandbox

配置 Registry 等价于授权其原生代码进入进程。v1 不强制 Artifact signature，也不提供 per-load trust override。

Local JIT 使用 pure Nix evaluation 与无网络普通 build sandbox；带 hash 的 locked fetcher 可由 Nix 受控获取依赖。Secrets 和用户 home 不进入 sandbox。JIT 默认同步等待 30 分钟，`K_DASH_JIT_TIMEOUT` 与 `K_DASH_NIX_MAX_JOBS` 可以调整资源边界。详见 [Trust and Sandbox](./trust-and-sandbox.md)。

## Protocol evolution

以下版本独立演进：

| Layer | Version field |
| --- | --- |
| Global Registry config | `schema_version` |
| Kernel Project Manifest | `format-version` |
| `build.nix` function contract | `build-api` |
| BuildSpec canonical form | `buildspec_version` |
| OCI Release/Build config | versioned media type |

未知版本直接拒绝。BuildSpec Hash 输入变化必须生成新 BuildSpec version，旧 BuildKey 永不重解释；build function 变化升级 build API；不兼容 Artifact 变化使用新 media type。已发布 Artifact 不原地迁移，CLI 可以新增旧协议 reader。

## Implementation-owned details

以下细节可以在不改变已接受架构的前提下由实现确定：

- Python 内部 package/file 名称与第三方 HTTP/Docker 库。
- 默认 AOT Builder Image 的具体 OCI reference。
- v1 认可的完整 Host CUDA Dependency 逻辑名与 SONAME 映射表。
- Registry retry/backoff 常量和日志格式。
- JSON/TOML schema 的代码生成方式与内部 error class 组织。

它们不得改变 public API、BuildSpec/BuildKey、Artifact media type、Kernel Build Contract 或已记录 failover/trust 语义。

## Verification requirements

实现至少需要覆盖：

- Args/JCS/BuildKey cross-language golden vectors。
- Dev Version move、immutable Version conflict 与多 Registry partial retry。
- Primary 404 JIT、Access Failure failover 和 content error fail-closed。
- 同 BuildKey 多线程/多进程单次构建与 atomic cache commit。
- C++/CuteDSL template 的 Docker AOT 与 Linux Local JIT 等价 BuildKey。
- x86_64/aarch64 manylinux_2_28、TVM-FFI、ELF dependency allowlist 校验。
- `nvcc`/PyTorch Target Detection、逻辑 GPU 0 和 `sm_90a`/`sm_100a` golden cases。
- Offline cache hit、cached-source JIT 与 Offline Cache Miss。
- 异常、日志和 Provenance 不泄漏 Registry credentials。
