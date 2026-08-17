---
status: accepted
---

# Kernel 必须声明 Args Schema

每个 Kernel 必须声明强类型 Args Schema，并由发布期预编译和运行期按需编译共享。未知字段、缺失的必填字段和不满足约束的值必须在构建前失败；默认值应在构建身份确定前展开，等价对象不能因字段顺序不同而形成不同身份。Schema 的承载文件格式尚待决定。
