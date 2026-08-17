# k-dash 内核分发领域

k-dash 描述如何把同一个内核构建需求按需或提前转化为可加载的构建结果。

## Language

**BuildSpec（构建规格）**：
一个内核构建需求的完整、规范化描述。运行期请求与发布期预编译若具有相同的 BuildSpec，就表示同一个构建需求。
_Avoid_: JIT 参数、AOT 参数（当它们被用来指代完整构建身份时）

**BuildKey（构建键）**：
对规范化 BuildSpec 计算出的稳定内容摘要，用于跨本地缓存和 Registry 精确寻址同一个构建需求。
_Avoid_: Binary digest、OCI tag

**Kernel Args（内核参数）**：
由内核作者定义、由使用者提供的静态特化参数，是 BuildSpec 的一部分，但不包含目标环境属性。
_Avoid_: 系统注入参数、目标参数

**TargetSpec（目标规格）**：
BuildSpec 中描述目标平台、加速器编译目标和运行时 ABI 的部分，与 Kernel Args 分离。
_Avoid_: JIT 参数、用户参数

**Target Detection（目标探测）**：
从本地工具链、框架和 GPU 0 按固定优先级生成 TargetSpec 的过程，公共加载 API 不允许调用者显式覆盖结果。
_Avoid_: 兼容性搜索、Kernel Args 默认值

**Args Schema（参数模式）**：
由内核声明的 Kernel Args 契约，定义可接受的字段、类型、默认值和约束；发布期与运行期共享同一份契约。
_Avoid_: 参数示例、README 参数表

**Kernel Source Package（内核源码包）**：
从 Kernel 项目中筛选出的、足以解释并物化 BuildSpec 的源码与作者文档集合。
_Avoid_: 整个 Git 仓库、工作目录快照

**Kernel Project Manifest（内核项目清单）**：
Kernel 项目的机器可读 identity 与构建协议声明，是 `init`、校验和发布定位 Kernel 的唯一权威。
_Avoid_: README metadata、`build.nix` identity

**Kernel Build Contract（内核构建契约）**：
`build.nix` 接收规范化 BuildSpec 并产生单个 Kernel Module 的纯函数边界，与具体 C++ 或 Python DSL 的参数转换方式无关。
_Avoid_: Flake input lock、项目元数据

**Nix Build Lock（Nix 构建锁）**：
由 Kernel 自己维护、随 Kernel Release 冻结的 Nix 输入集合，使 AOT 与 Local JIT 使用相同依赖图。
_Avoid_: Builder Image tag、宿主 Nix channel

**Build Provenance（构建来源）**：
描述一次物化实际使用的执行环境和 Nix 输出身份的审计记录，不参与替代 BuildSpec。
_Avoid_: BuildSpec、兼容性声明

**Kernel Version（内核版本）**：
用户用于选择 Kernel Release 的字符串。非 `dev-` Version 一经发布即永久绑定同一 Release，`dev-` Version 可以重新绑定到新的 Release。
_Avoid_: SemVer、Release Digest

**Dev Version（开发版本）**：
以 `dev-` 开头、允许随开发进展重新绑定 Release 的 Kernel Version，不提供不可变引用保证。
_Avoid_: 不可变 Release、Release Digest

**Kernel Release（内核发布）**：
由 digest 标识的不可变源码与发布契约；Version 可以指向它，物化构建也可以追加引用它，但这些操作不会改变 Release 本身。
_Avoid_: Kernel Version、Materialized Build

**Release Publication（Release 发布）**：
把一个 Kernel Source Package 固化为 Release Artifact，并可同时提前物化一组 BuildSpec 的事务。
_Avoid_: Build Addition、Local JIT

**Build Addition（二进制追加）**：
在不修改既有 Kernel Release 的前提下，基于其精确源码为新的 BuildSpec 发布 Materialized Build。
_Avoid_: Release 重发、工作区构建上传

**Local AOT Build（本地 AOT 构建）**：
从当前 Kernel Project 构造 would-be Release digest，并通过 Docker 提前物化 BuildSpec 到 Local Cache，但不修改任何 Registry。
_Avoid_: Local JIT、Release Publication

**Release Resolution（发布解析）**：
把 Kernel Version 解析为具体 Release digest 的过程；非开发版本可以永久缓存结果，Dev Version 的在线结果由 Primary Registry 决定。
_Avoid_: Artifact 下载、BuildSpec 解析

**OCI Kernel Repository（OCI Kernel 仓库）**：
某个 Registry 中只属于一个 Kernel 的 OCI Repository，承载该 Kernel 的 Release Artifact 与 Build Artifact。
_Avoid_: Registry、跨 Kernel Artifact 仓库

**Registry Set（Registry 集合）**：
配置中一个 Primary Registry 与若干有序 Secondary Registry 的整体，Primary 正常时对 Binary Hit 或 Binary Miss 具有权威性，Secondary 主要提供不可用容灾。
_Avoid_: 无序镜像池、全量 Build 搜索集合

**Trusted Registry（可信 Registry）**：
被用户写入 Registry Set、因而获准向训练或推理进程提供可执行 Kernel Module 或 JIT Source 的 Registry。
_Avoid_: 仅通过 TLS 的匿名内容源、签名 identity

**Binary Miss（二进制未命中）**：
当前权威 Registry 对精确 BuildKey 明确返回不存在；它触发 Local JIT，而不是继续搜索 Secondary 是否有同名 Build。
_Avoid_: Registry 不可用、Artifact 校验失败

**Registry Access Failure（Registry 访问失败）**：
Registry 无法给出可用于内容判断的响应，例如连接、TLS、认证、限流或服务可用性失败；只有这类失败允许切换到下一个 Registry。
_Avoid_: Binary Miss、Artifact 完整性错误

**Release Artifact（发布产物）**：
承载一个 Kernel Release 的 OCI Artifact，包含发布元数据与 Kernel Source Package。
_Avoid_: Build Artifact、Version tag

**Build Artifact（构建产物）**：
承载一个 Materialized Build 的 OCI Artifact，包含 BuildSpec、Build Provenance 与可加载二进制包。
_Avoid_: Release Artifact、AOT 专用产物

**Kernel Module（内核模块）**：
Build Artifact 中唯一的 TVM-FFI 共享库入口，可以导出多个函数，但不附带或执行 Python glue。
_Avoid_: Python package、私有动态库 bundle

**Loaded Module（已加载模块）**：
当前 Python 进程中针对一个 BuildKey 完成验证并由 TVM-FFI 加载的 Module object，同一 BuildKey 在进程内共享同一对象。
_Avoid_: Build cache entry、Version alias

**Host CUDA Dependency（宿主 CUDA 依赖）**：
由 Local JIT Environment 提供、属于 k-dash 认可 CUDA 生态清单的动态库依赖，例如 CUDA Driver、cuBLAS 或 NCCL。
_Avoid_: 任意系统动态库、Artifact 私有依赖

**Host Dependency Requirement（宿主依赖条件）**：
由逻辑 Host CUDA Dependency、针对 CUDA Target 解析出的 SONAME ABI major 和最低兼容版本组成的加载条件。
_Avoid_: 精确 patch 锁定、BuildKey 输入

**Local JIT Environment（本地 JIT 环境）**：
训练或推理进程所在、直接通过 Nix 物化 BuildSpec 的运行环境，不要求能够启动 Docker。
_Avoid_: AOT Builder Container、Docker-in-Docker

**AOT Builder Container（AOT 构建容器）**：
发布者在无 GPU Linux 或 macOS 宿主上提前物化 BuildSpec 的 Linux Docker 环境，其职责是承载 Nix 构建而不是定义二进制身份。
_Avoid_: Local JIT Environment、固定工具链身份

**Materialized Build（物化构建）**：
属于一个 Kernel Release、针对一个 BuildSpec 已经生成的可加载构建结果；它既可以在发布时提前产生，也可以在首次加载时按需产生。
_Avoid_: AOT 构建、JIT 构建（当差异仅是结果的产生时机时）

**Local Cache（本地缓存）**：
按 Release digest 与 BuildKey 保存已验证 Source/Build 内容的持久存储，Version 只作为到 digest 的解析记录而不拥有内容。
_Avoid_: Registry mirror、Nix store
