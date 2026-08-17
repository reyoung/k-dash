---
status: accepted
---

# Local JIT 直接使用 Nix，AOT 借助 Docker

运行期 `k_dash.load` 在二进制未命中时直接检查并使用训练或推理环境中的 Nix，不依赖 Docker-in-Docker；缺少必要构建依赖时必须给出明确错误。发布期 AOT 则通过 Docker 在无 GPU Linux 或 macOS 上执行相同 BuildSpec，Builder Image 不需要成为固定的二进制身份，构建固定性主要由 Nix 契约提供；`k-dash init` 不再生成 `.devcontainer`。
