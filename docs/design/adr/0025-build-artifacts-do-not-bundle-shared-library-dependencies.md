---
status: accepted
---

# Build Artifact 不打包其他动态库

Binary layer 只包含 `kernel.so`，不携带 `lib/`、Python glue 或私有共享库。除基础 Linux ABI 外，Kernel Module 只能动态依赖 k-dash 认可的宿主 CUDA 生态库，包括 CUDA Driver、CUDA Runtime、cuBLAS 与 NCCL 等；任何其他系统动态依赖、绝对 RPATH、RUNPATH，或以绝对 `/nix/store/...` 形式出现的 `DT_NEEDED` 都必须在发布前和加载前被拒绝。未被 ELF 动态段引用的普通/debug 字符串不属于运行时依赖。
