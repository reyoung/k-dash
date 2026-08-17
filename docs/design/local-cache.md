# Local Cache and Concurrent JIT

Status: Accepted

## Location and layout

默认根目录为 `~/.cache/k-dash/`，环境变量 `K_DASH_CACHE_DIR` 可以覆盖：

```text
k-dash/
├── releases/<release-digest>/
│   ├── config.json
│   ├── source.tar.zst
│   └── source/
├── builds/<build-key>/
│   ├── config.json
│   └── kernel.so
├── resolutions/<registry>/<kernel>/<version>.json
├── locks/
└── tmp/
```

Release 与 Build entry 在进入 cache 前完成全部完整性、ABI 与安全校验。Version resolution 可以更新，但不会覆盖 content-addressed entry。

## Concurrent materialization

每个 BuildKey 使用跨进程 advisory lock：

1. 调用者先检查已验证 Build cache。
2. Miss 后获取 BuildKey lock。
3. 持锁后重新检查 cache，避免等待期间重复工作。
4. 负责者下载 Build，或在权威 Binary Miss 后下载 Source 并 Local JIT。
5. 输出写入 cache 根目录下的临时目录。
6. 全部验证成功后通过同文件系统原子 rename 提交。
7. 等待者获得锁后重新检查并加载结果。

进程崩溃由 OS 释放 advisory lock；启动或显式维护命令可以删除没有对应活跃锁的残留临时目录。不同 BuildKey 使用不同锁，可以并行物化。

持锁者构建失败时，当前所有等待同一 BuildKey 的调用者接收同一次失败结果；失败不形成持久 negative cache，后续新调用可以重试。

## Eviction

`load` 不执行自动淘汰。v1 提供显式管理命令：

```bash
k-dash cache info
k-dash cache prune --max-size 100GiB
k-dash cache clean
```

## Offline mode

`K_DASH_OFFLINE=1` 时：

- 禁止所有 Registry 请求。
- 非 Dev Version 必须已有缓存的 Release Resolution。
- Dev Version 使用上次解析 digest，并发出可能过期警告。
- Build cache hit 直接加载。
- Build miss 但 Source 已缓存时，以 Nix offline mode 尝试 Local JIT。
- Source、Resolution 或 Nix closure 缺失时报告 `OfflineCacheMiss`。
