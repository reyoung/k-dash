---
status: accepted
---

# AOT Builder Image 可替换且构建必须携带 Provenance

AOT 提供默认 Builder Image 并允许覆盖，Image digest 不进入 BuildSpec，AOT 也不需要挂载 GPU，CUDA Toolkit 与 CC 来自显式 TargetSpec。每次物化记录实际 image digest、Nix 版本、derivation path 和输出 NAR hash；相同 BuildSpec 若得到不同二进制 digest，必须报告 `NonReproducibleBuild` 而不能覆盖或任选一个发布。
