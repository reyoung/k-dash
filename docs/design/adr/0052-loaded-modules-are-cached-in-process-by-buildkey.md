---
status: accepted
---

# Loaded Module 在进程内按 BuildKey 复用

Python runtime 使用线程安全的 BuildKey cache，同一 BuildKey 的重复或并发 `load` 返回同一个 TVM-FFI Module object，并只执行一次 Registry/cache/JIT/load 流程。Dev Version 每次调用仍向 Primary 解析，未移动则复用，移动后加载新 BuildKey；既有 Module 不卸载，磁盘 cache 清理也不影响已经加载的对象。
