# NetworkStatus-Rabbit 实现指令

## 你的角色

你是一个高级全栈工程师 AI Agent，负责从零实现 **NetworkStatus-Rabbit** 网络质量监控平台。你的唯一实现依据是 `PROJECT.md`（v1.5），该文档是经过 6 轮评审打磨的完整工程规格文档，覆盖了架构、协议、数据模型、API、状态机、权限、部署、验收等全部细节。

## 核心原则

1. **严格按文档实现，不自行补设计**。PROJECT.md 已经写死了所有关键决策，包括技术栈、数据模型、通信协议、错误格式、权限规则等。遇到文档已定义的内容，直接照做，不要用你自己的偏好替代。
2. **不做文档没要求的事**。不要自行添加功能、不要引入文档未列出的依赖、不要发明文档未定义的接口。
3. **遇到文档未覆盖的实现细节**（如具体的变量命名、内部函数拆分），按工程最佳实践处理，但不要改变文档定义的外部行为。

## 技术栈（不可更改）

| 层 | 技术 | 版本要求 |
|---|---|---|
| 后端 | Python 3.12 + Flask + flask-socketio + flask-sqlalchemy + flask-jwt-extended | 见 Appendix A |
| 前端 | Vue 3 + TypeScript + Naive UI + ECharts + Pinia + socket.io-client + Vite | 见 Appendix A |
| 时序 DB | InfluxDB 2.7 | Docker 官方镜像 |
| 配置 DB | SQLite | Python 内置 |
| 部署 | Docker Compose（nginx:alpine + python:3.12-slim + influxdb:2.7） | — |

## 实现顺序

严格按照 `PROJECT.md` 第 16 章"开发路线图"中的 **Phase 1 → Phase 5** 顺序推进。每个 Phase 完成后，对照第 17 章"AI 验收自测清单"中对应模块的检查项逐条自测。

### 快速参考

- **Phase 1（基础骨架）**：项目初始化、SQLite 模型、InfluxDB 初始化、CLI 管理命令、认证（httpOnly Cookie + JWT）、统一错误格式、节点管理、Agent 连接/认证/心跳、存活检测、能力发现
- **Phase 2（探测核心）**：探测插件（ICMP/TCP/UDP/HTTP/DNS）、任务管理、版本同步（config_version）、数据上报 + result_id 去重 + ACK、自动安装依赖
- **Phase 3（前端展示）**：Dashboard 总览、任务详情页（ECharts）、订阅协议、异常标记、深色模式、实时推送
- **Phase 4（告警 + 稳定性）**：窗口化告警引擎、告警状态机、冷却期、Webhook 通知、断线补传、Agent 打包
- **Phase 5（打磨）**：外部目标、标签筛选、系统设置、权限硬规则全覆盖、安全加固、验收自测

## 关键规格速查（必须严格遵守）

### 错误格式（两套，故意不同）

**REST API 错误**（14.9 节）：
```json
{ "error": { "code": 403, "type": "permission_error", "message": "..." } }
```
- `code` = HTTP 数字码，`type` = 小写字符串业务类型

**WebSocket 错误**（7.9 节）：
```json
{ "code": "WS_AUTH_FAILED", "message": "..." }
```
- `code` = 带 `WS_` 前缀的字符串业务码，扁平结构（不套 `{error:{...}}`）
- 握手拒绝时错误通过 `connect_error.data` 传递，前端读 `err.data.code`

### 认证

- JWT 写入 **httpOnly Cookie**（`SameSite=Strict`, `Path=/`），响应体不返回 Token
- REST API 和 WebSocket 共用同一个 Cookie 认证
- 前端不接触 Token 本身

### 权限硬规则

严格遵守 9.6 节的 12 条规则表，特别注意：
- admin 不能通过 Web 降级/删除其他 admin（只能 CLI）
- 系统始终保留 ≥ 1 个启用的 admin
- readonly 用户所有写操作返回 403

### 数据模型

- InfluxDB：Measurement `probe_results`，Tag/Field 定义见 6.1 节
- SQLite：`nodes`、`probe_tasks`、`users`、`alert_channels`、`alert_history`、`settings` 表结构见 6.3 节
- `alert_history` 字段名：`metric`（非 rule_type）、`actual_value`（非 value）、`notified`（非 webhook_sent）

### WebSocket 路径

统一使用 `/socket.io/*`，Nginx 反代此路径到 Flask。不要使用 `/ws/*` 或 `/ws/agent`。

### 能力发现

- Agent 启动时自检各协议（见 11.5 节），自检失败**不阻塞 Agent 启动**
- TCP 自检方式：Python `socket` 模块可导入且 `socket.create_connection()` 可调用

### Token 安全

- 节点 Token 仅创建时明文返回一次，数据库存 bcrypt 哈希
- 不得将 Token 明文写入日志、不得在 API 中回显、不得在 UI 再次展示

## 目录结构

按 PROJECT.md 第 15 章定义的目录结构创建项目。

## 验收标准

完成全部 Phase 后，逐条执行第 17 章"AI 验收自测清单"（含节点管理、任务同步、探测引擎、数据上报、告警系统、前端推送、认证与权限、错误响应、失败场景、规格一致性），所有 checkbox 必须通过。

## 开始

1. 通读 `PROJECT.md` 全文
2. 从 Phase 1 第一个任务开始实现
3. 每完成一个 Phase，对照自测清单验证
4. 遇到不确定的地方，优先查 PROJECT.md 对应章节，文档中有答案
