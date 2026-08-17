---
status: accepted
---

# Registry 配置允许明文认证信息

Registry auth 支持 anonymous、Docker credential config/helper、环境变量引用，也允许 `basic` 直接在 YAML 中保存 username/password。明文 secret 是显式支持的便利性选择，配置文件本身承担访问控制责任；TLS 默认验证，可配置内部 CA，也允许显式关闭验证并产生安全警告。
