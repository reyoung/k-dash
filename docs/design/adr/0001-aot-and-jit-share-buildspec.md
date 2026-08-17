---
status: accepted
---

# AOT 与 JIT 共享 BuildSpec

k-dash 使用同一个 BuildSpec 表达发布期预编译和运行期按需编译的构建需求。AOT 只是对 BuildSpec 的提前物化；运行期出现相同 BuildSpec 时必须复用其物化构建，而不是进入一套独立的 AOT 匹配体系，从而避免两套构建身份随时间产生分歧。
