---
status: accepted
---

# `build.nix` 是 BuildSpec 到 Kernel Module 的纯函数

`build.nix` 使用固定 build API 接收 `kdlib`、锁定的 `pkgs` 与规范化 `buildSpec`，Kernel 自行把 args/target 转成 C++ 静态参数、Triton constexpr 或 CuteDSL 参数，并声明逻辑 Host CUDA Dependency。k-dash 通过生成的 Nix expression 注入 BuildSpec，禁止环境变量传参；求值必须 pure、构建必须 sandboxed，唯一有效输出是只含普通文件 `$out/kernel.so` 的 derivation。
