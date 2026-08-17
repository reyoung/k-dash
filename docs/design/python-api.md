# Python API

Status: Accepted

## Public surface

```python
from collections.abc import Mapping
from typing import Any

import tvm_ffi


def load(
    kernel: str,
    *,
    jit_args: Mapping[str, Any] | None = None,
    version: str,
) -> tvm_ffi.Module:
    ...
```

v1 public Python surface 只有 `load`：

- `kernel` 必须是合法小写 `owner/kernel`。
- `version` 是必填 keyword-only 字符串，不接受整数隐式转换。
- `jit_args` 是 keyword-only，`None` 等价于 `{}`。
- 不接受显式 Target、Registry override 或 `trust_remote_code`。
- 调用同步阻塞，完成 Build download 或 Local JIT、校验和 TVM-FFI load 后返回 Module。
- v1 不提供 `resolve`、Resolution dataclass、独立 diagnostic callable 或稳定的 public exception hierarchy。

## In-process module cache

进程内 cache 以 BuildKey 为键并保证线程安全：

1. 同一 BuildKey 返回同一个 TVM-FFI Module object。
2. 并发线程只执行一次 Registry/cache/JIT/load 流程。
3. Dev Version 每次调用仍解析 Primary；Release 未改变时复用，改变时加载新 BuildKey 与新 Module。
4. 已返回的旧 Dev Module 保持有效，不尝试 unload `.so`。
5. 磁盘 `cache clean` 不影响进程内已加载 Module。

## Operational diagnostics

内部错误仍必须包含 Kernel、Version、Release digest、BuildKey、所处阶段和脱敏 Registry trace 等可操作信息，但这些结构不构成 v1 public Python API 或兼容性承诺，任何 password/token 都不能出现在异常与日志中。
