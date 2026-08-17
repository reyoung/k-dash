---
status: accepted
---

# Kernel Args 只有一种规范形式

发布和加载必须使用同一流程处理 Kernel Args：拒绝重复 key，按 Args Schema 递归应用缺失默认值，验证必填、类型、范围与未知字段，再转换为 JCS/I-JSON。整数限制在 `[-(2^53-1), 2^53-1]`，浮点只允许有限 IEEE-754 double 并禁止负零歧义，超范围整数或精确十进制必须用 Schema 约束的字符串表示，字符串不做 Unicode normalization。
