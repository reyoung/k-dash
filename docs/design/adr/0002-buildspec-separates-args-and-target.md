---
status: accepted
---

# BuildSpec 分离 Kernel Args 与 TargetSpec

BuildSpec 将内核作者声明的 Kernel Args 与系统确定的 TargetSpec 放在不同命名空间，构建过程可以同时使用二者，但用户参数不能覆盖目标属性。TargetSpec 对 OS、CPU 架构、libc ABI 基线、CUDA Toolkit `major.minor`、完整 CUDA 架构名和 TVM-FFI ABI 做精确描述；GPU 型号、主机名和 CUDA Driver 补丁版本不参与构建身份，v1 不进行模糊兼容匹配。
