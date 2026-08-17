---
status: superseded by ADR-0022
---

# Local CUDA Toolkit Version 来自 `nvcc`

Local JIT 构造 TargetSpec 时，从宿主 `nvcc --version` 解析 CUDA Toolkit `major.minor`，而不是使用 Driver 宣称的最大 CUDA 能力；`nvcc` 只提供目标版本信号，实际编译器和依赖仍来自 Kernel Release 锁定的 Nix 输入。TargetSpec 必须在 Binary lookup 前形成，因此 `nvcc` 探测先于 Binary Hit/Miss；完整 Nix 环境检查仍只在 Binary Miss 后发生。
