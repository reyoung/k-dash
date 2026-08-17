---
status: superseded by ADR-0023
---

# `load` 只使用自动 Target Detection

公共 `k_dash.load` 不接受显式 Target 参数。CUDA Toolkit Version 优先从宿主 `nvcc --version` 解析，缺失时使用可导入 CUDA-enabled PyTorch 的 `torch.version.cuda`，两者都无法提供 `major.minor` 时报告 Target Detection 错误；CUDA CC 固定从本机 GPU 0 探测。实际 Local JIT 编译器仍来自 Kernel Release 的 Nix lock，完整 Nix 环境检查仍只在 Binary Miss 后执行。
