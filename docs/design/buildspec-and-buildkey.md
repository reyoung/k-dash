# BuildSpec and BuildKey

Status: Accepted

## BuildSpec v1

```json
{
  "buildspec_version": 1,
  "release_digest": "sha256:<release-manifest-digest>",
  "args": {},
  "target": {}
}
```

BuildSpec 不包含 Version、Registry URL、构建时间、Builder Image 或 Build Provenance。Version 必须先解析为 Release digest，Dev Version 因而不会让旧源码与新 Build Artifact 共用身份。

## Kernel Args normalization

1. 解析输入并拒绝重复对象 key。
2. 按 `args.schema.json` 递归填充缺失的 `default`。
3. 验证必填字段、类型、范围和 `additionalProperties: false`。
4. 整数限制在 `[-(2^53-1), 2^53-1]`；浮点只允许有限 IEEE-754 double，禁止 `NaN`、Infinity 和负零歧义。
5. 超范围整数和精确十进制使用 Schema 约束的字符串。
6. 使用 RFC 8785 JCS 生成规范 JSON；字符串保持原 Unicode code point 序列。

## BuildKey

```text
canonical = JCS(BuildSpec)
BuildKey  = sha256(canonical)
OCI tag   = build-sha256-<64 lowercase hexadecimal characters>
```

Release config、Build Artifact config 与本地缓存元数据都保存完整 BuildSpec 和 BuildKey，读取时必须重新计算并校验二者一致。

## Local CUDA Toolkit detection

公共 `k_dash.load` 不接受显式 Target。Local TargetSpec 按以下顺序探测 CUDA Toolkit Version，并规范化为 `major.minor`：

1. 宿主 `nvcc --version`。
2. CUDA-enabled PyTorch 的 `torch.version.cuda`。
3. 两者都不可用时报告 Target Detection 错误。

CUDA CC 固定从 `CUDA_VISIBLE_DEVICES` 重映射后的逻辑 GPU 0 探测，BuildSpec 只描述一个 CC。CC 低于 9.0 时使用普通 `sm_<xy>`；CC 9.0 及以上默认使用精确 architecture-specific `sm_<xy>a`，不自动选择 family-specific `f`。Release lock 不支持探测结果时报告 `UnsupportedTarget`，不降级到普通 CC。

探测值选择 Release lock 中对应的 Nix CUDA toolchain，宿主 `nvcc` 本身不直接参与编译；完整 Nix preflight 仍只在 Binary Miss 后执行。`nvcc` 与 `torch.version.cuda` 不一致时，`nvcc` 严格胜出，PyTorch 值只用于诊断。
