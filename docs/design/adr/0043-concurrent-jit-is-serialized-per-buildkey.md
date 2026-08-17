---
status: accepted
---

# 并发 JIT 按 BuildKey 跨进程序列化

每个 BuildKey 使用跨进程 advisory lock；持锁者再次检查 cache 后负责下载或 Local JIT，等待者取得锁后也必须重新检查，因而同一 BuildKey 不重复编译、不同 BuildKey 仍可并行。所有写入在同一文件系统临时目录完成，验证通过后原子 rename 提交，进程退出自动释放锁，残留临时目录可以安全清理。
