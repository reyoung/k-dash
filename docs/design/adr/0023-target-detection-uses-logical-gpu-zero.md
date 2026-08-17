---
status: accepted
---

# Target Detection 使用逻辑 GPU 0

`k_dash.load` 从 `CUDA_VISIBLE_DEVICES` 重映射后的逻辑 GPU 0 探测单一 CUDA CC；CC 低于 9.0 时使用普通 `sm_<xy>`，CC 9.0 及以上默认使用精确 architecture-specific `sm_<xy>a`，不选择 family-specific `f`，Release lock 不支持时直接报告 `UnsupportedTarget`。CUDA Toolkit Version 仍按 `nvcc --version`、`torch.version.cuda` 的顺序探测；两者不一致时 `nvcc` 严格胜出，PyTorch 值只进入诊断而不产生候选 BuildKey，也不触发版本降级。
