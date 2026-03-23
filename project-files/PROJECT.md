# NetworkStatus-Rabbit 🐇🌐

## 基础工程文档 v1.5

> **文档日期**：2026-03-23（v1.5 更新：采纳 GPT5.4 第五轮评审建议，修正 TCP 自检逻辑、统一自测清单错误码、统一 connect_error 读取方式、补能力发现/告警历史/Token 边界说明）
> **项目定位**：独立的网络质量监控平台（不兼容 ServerStatus-Rabbit，不做服务器状态监控）
> **许可协议**：MIT

---

## 目录

- [v1.1 变更记录](#v11-变更记录)
- [v1.2 变更记录](#v12-变更记录)
- [v1.3 变更记录](#v13-变更记录)
- [v1.4 变更记录](#v14-变更记录)
- [v1.5 变更记录](#v15-变更记录)

1. [项目概述](#1-项目概述)
2. [核心概念与术语](#2-核心概念与术语)
3. [架构设计与决策说明](#3-架构设计与决策说明)
4. [技术栈与选型理由](#4-技术栈与选型理由)
5. [系统组件](#5-系统组件)
6. [数据模型与存储策略](#6-数据模型与存储策略) ✏️ ✏️ ✏️
7. [通信协议设计](#7-通信协议设计) ✏️ ✏️ ✏️ ✏️ ✏️
8. [核心状态机](#8-核心状态机) 🆕
9. [认证与权限模型](#9-认证与权限模型) ✏️ ✏️
10. [前端设计](#10-前端设计) ✏️
11. [探测引擎（插件架构）](#11-探测引擎插件架构) 🆕 11.5 ✏️ ✏️
12. [告警系统](#12-告警系统) ✏️
13. [部署方案](#13-部署方案) ✏️ ✏️ ✏️
14. [内部 API 设计](#14-内部-api-设计) ✏️ ✏️ ✏️ ✏️
15. [目录结构](#15-目录结构)
16. [开发路线图](#16-开发路线图) ✏️
17. [AI 验收自测清单](#17-ai-验收自测清单) 🆕 ✏️
18. [Future Features（远期功能）](#18-future-features远期功能) ✏️

---

## v1.1 变更记录

> 本节记录 v1.1 相对 v1.0 的所有变更。变更依据：GPT5.4 评审建议（详见 `GPT5.4的建议-1.md`）。
> 文档中，带 `🆕` 标记的章节为 v1.1 **新增**，带 `✏️` 标记的章节为 v1.1 **修改**。

### 新增章节

| 章节 | 内容 | 对应 GPT5.4 建议 |
|---|---|---|
| **8. 核心状态机** 🆕 | 节点状态机（registered→online→offline→disabled）、告警事件状态机（normal→alerting→recovering）、任务同步状态机（synced→pending→desync） | "缺少状态机定义，状态转换不够明确" |
| **11.5 能力发现** 🆕 | Agent 启动自检各协议依赖（ping/curl/dig/nc），上报 capabilities JSON；Linux 三大发行版 + Docker 自动安装依赖命令 | "Agent 运行前提没锁死" |
| **7.2 关键事件 JSON 示例** 🆕 | agent:auth、agent:probe_result、agent:probe_batch、center:task_sync、center:batch_ack 的完整 JSON payload 示例 | "JSON 格式给出完整 payload 样例" |
| **7.5 节点存活检测** 🆕 | 120 秒滑动窗口 + 心跳计数 ≤20=离线 的详细设计 | "实时推送协议不够保守" |

### 修改章节

| 章节 | 修改内容 | 对应 GPT5.4 建议 |
|---|---|---|
| **7. 通信协议设计** ✏️ | 整体重写：新增 `result_id` 去重机制、`seq_id` 心跳序列号、`config_version` 任务版本同步、`center:result_ack` / `center:batch_ack` ACK 确认机制、补传优先级策略 | "断线补传协议不完整（无 ACK、无去重）"、"任务同步无版本号" |
| **6.3 nodes 表** ✏️ | 新增 5 个字段：`config_version`（任务版本号）、`capabilities`（JSON 能力信息）、`agent_version`（Agent 版本）、`public_ip`、`private_ip` | "能力发现需持久化" |
| **6.3 probe_tasks 表** ✏️ | 新增 4 个字段：`alert_eval_window`（评估窗口大小）、`alert_trigger_count`（触发阈值）、`alert_recovery_count`（恢复阈值）、`alert_cooldown_seconds`（冷却时间） | "告警参数需要窗口化" |
| **12.1 告警规则** ✏️ | 从单次触发改为窗口化评估：最近 N 次探测中 ≥ M 次超阈值才告警；新增冷却期机制；新增"为什么用窗口化"解释 | "告警过于理想化，一次超阈值就告警会产生告警风暴" |
| **12.2 告警流程** ✏️ | 新增历史补传数据告警抑制（timestamp 早于 60 秒的数据只入库不告警） | "补传的历史数据不应触发告警" |
| **10.3 图表设计** ✏️ | 新增异常区间标记：用 ECharts markArea 在图表上显示半透明红色告警时段 | "前端缺少告警可视化" |
| **10.6 节点管理页** ✏️ | 新增协议支持状态展示（绿色=支持/灰色=不支持），与能力发现联动 | "能力发现需前端展示" |
| **10.6 任务管理页** ✏️ | 新增协议兼容性检查提示 + 告警窗口参数配置 | "创建任务时应检查源节点协议支持" |
| **16. 开发路线图** ✏️ | Phase 1-5 全面重排：Phase 1 新增心跳存活检测+能力发现；Phase 2 新增 config_version+ACK+去重；Phase 3 新增异常区间标记+协议状态展示；Phase 4 新增窗口化告警+状态机+历史抑制；Phase 5 新增标签筛选+自定义时间 | 路线图需反映所有新增特性 |
| **17. Future Features** ✏️ | 新增 4 条：链路健康评分、静默时段/维护窗口、Dashboard 聚合推送、多视角看板 | 采纳 GPT5.4 的功能建议但放入远期 |

---

## v1.2 变更记录

> 本节记录 v1.2 相对 v1.1 的所有变更。变更依据：GPT5.4 第二轮评审建议（详见 `GPT5.4的建议-2.md`）。
> 文档中，带 `🆕` 标记的章节为 **新增**，带 `✏️` 标记的章节为 **修改**（多个 ✏️ 表示该章节在多个版本中被修改过）。

### 新增章节

| 章节 | 内容 | 对应 GPT5.4 建议 |
|---|---|---|
| **6.3 alert_history 表** 🆕 | 告警历史表字段定义（event_type/task_id/metric/actual_value/threshold/duration/状态…） | "alert_history 只有概念没有结构" |
| **6.4 Agent 本地缓存表** 🆕 | Agent 端 SQLite 缓存表 `local_results` 字段定义（result_id/batch_id/ack_status/retry_count…） | "本地缓存表结构没有写到实现级别" |
| **7.8 详情页订阅协议** 🆕 | subscribe_task / unsubscribe_task 完整事件定义、payload、生命周期规则 | "订阅协议没有定义完整" |
| **9.6 权限硬规则表** 🆕 | 12 条"允许/禁止"规则明确写死权限边界 | "权限边界写成禁止项规则表" |
| **11.6 操作系统支持范围** 🆕 | 正式支持/不保证/不支持/已知限制 四级声明 | "正式支持范围还不够硬" |
| **14.9 统一错误响应规范** 🆕 | HTTP 错误码语义表 + 统一 JSON 错误格式 | "统一失败语义和错误码规则还没有锁死" |
| **14.10 REST API 请求/响应示例** 🆕 | 6 个核心接口的完整请求体 + 成功响应体 JSON 示例 | "REST API 仍然不够像可直接照着写的规格" |
| **17. AI 验收自测清单** 🆕 | 30+ 条分模块自测项，覆盖节点、任务同步、探测、告警、补传、前端、安全 | "给验收清单补一节 AI 自测项" |

### 修改章节

| 章节 | 修改内容 | 对应 GPT5.4 建议 |
|---|---|---|
| **9.2 管理员管理** ✏️ | 新增"不能降级其他 admin"规则 | "admin 能不能把另一个 admin 降级" |
| **9.5 登录安全** ✏️ | JWT 从 localStorage 改为 httpOnly Cookie + CSRF 防护（SameSite=Strict） | "JWT 和 localStorage 仍然保留" |
| **16. 开发路线图** ✏️ | Phase 2 新增 httpOnly Cookie；Phase 4 新增本地缓存表；Phase 5 新增权限硬规则验证 | 路线图需反映新特性 |
| **18. Future Features** ✏️ | 章节号从 17→18（因插入自测清单章节） | 章节重编号 |

---

## v1.3 变更记录

> 本节记录 v1.3 相对 v1.2 的所有变更。变更依据：GPT5.4 第三轮评审建议（详见 `GPT5.4的建议-3.md`）。

### 修复

| 章节 | 问题 | 修复 |
|---|---|---|
| **9.5 登录安全** 🔧 | Cookie `Path=/api` 与 WebSocket（`/socket.io/*`）路径不匹配，导致 WS 握手时浏览器不携带 Cookie | Cookie Path 改为 `/`，API 与 WebSocket 共用认证 Cookie |

### 新增章节

| 章节 | 内容 | 对应 GPT5.4 建议 |
|---|---|---|
| **7.9 WebSocket 错误事件规范** 🆕 | 统一 Socket.IO 错误事件格式（认证失败/权限不足/订阅无效），含自动断连规则 | "WebSocket 的失败语义仍然没有完全写死" |

### 修改章节

| 章节 | 修改内容 | 对应 GPT5.4 建议 |
|---|---|---|
| **9.5 登录安全** ✏️ | Cookie Path 从 `/api` 改为 `/`；补充部署前提（前后端必须同站点） | "Cookie Path 和 WebSocket 认证描述存在直接冲突" |
| **6.1 InfluxDB 数据模型** ✏️ | 补充 `target` Tag 规模边界说明（预期 ≤200 个离散值） | "`target` Tag 高基数风险" |
| **13.2 探测节点** ✏️ | Token 明文传参标注为"MVP 权衡"并说明后续改进方向 | "节点 Token 明文暴露在部署命令中" |
| **14.4 数据查询 API** ✏️ | Dashboard 查询接口补充筛选参数定义（protocol/label/status/search） | "Dashboard 筛选输入还没写清" |
| **14.10 REST API 示例** ✏️ | 新增 5 个高风险接口示例（用户角色修改、Webhook 通道、告警历史、系统设置、任务启停） | "还没有完全覆盖高风险接口" |
| **17. AI 验收自测清单** ✏️ | 新增"失败场景自测"分组（WS 鉴权被拒、readonly 403、删最后 admin 409 等） | "还缺失败场景自测" |

---

## v1.4 变更记录

> 本节记录 v1.4 相对 v1.3 的所有变更。变更依据：GPT5.4 第四轮评审建议（详见 `GPT5.4的建议-4.md`）。

### 修复（内部一致性）

| 章节 | 问题 | 修复 |
|---|---|---|
| **14.10 REST API 示例** 🔧 | 错误响应示例中 `error.code` 用了字符串（`"PERMISSION_DENIED"`），与 14.9 统一规范（int HTTP 码 + `type` 字段）冲突 | 所有错误示例统一为 `{error: {code: int, type: string, message: string}}` |
| **5.1 / 7.3 WebSocket 路径** 🔧 | `/ws/*`、`/ws/agent`、`/socket.io/*` 三种写法共存，AI Agent 无法确定标准 | 统一为 `/socket.io/*`，Nginx 反代此路径到 Flask |
| **7.9 WS 错误格式声明** 🔧 | 声称"与 REST API 错误格式保持一致"但实际结构不同 | 显式声明 WS 与 REST 故意采用不同格式，说明原因 |
| **6.3 alert_history 表** 🔧 | 表字段名（`rule_type/value/webhook_sent`）与 14.10 API 返回字段名（`metric/actual_value/notified`）不一致 | 统一为 API 字段名（`metric/actual_value/notified`），DB 与 API 同名 |

### 修改章节

| 章节 | 修改内容 | 对应 GPT5.4 建议 |
|---|---|---|
| **5.1 中心节点组件** ✏️ | Nginx 反代路径从 `/ws/*` 改为 `/socket.io/*` | "WebSocket 路径三种说法共存" |
| **7.3 连接生命周期** ✏️ | 连接 URL 从 `ws://center:port/ws/agent` 改为 `ws://center:port`（Socket.IO 自动处理路径） | 同上 |
| **7.9 WS 错误事件规范** ✏️ | 明确声明 WS 与 REST 错误格式故意不同并说明原因 | "口头上统一、结构上不统一" |
| **6.3 alert_history 表** ✏️ | `rule_type→metric`、`value→actual_value`、`webhook_sent→notified` | "DB 字段名与 API 字段名不一致" |
| **8.2 告警状态机** ✏️ | `rule_type` → `metric`（与字段名统一） | 同上 |
| **13.2 探测节点** ✏️ | Token 安全边界补充：不得明文写入日志、不得在 UI 回显 | "MVP 权衡可以更硬" |
| **14.4 数据查询 API** ✏️ | Dashboard 接口补充默认排序规则 | "排序规则还没单列" |
| **14.10 REST API 示例** ✏️ | 所有错误响应示例统一为 14.9 规范格式 | "`code` / `type` 规范不一致" |
| **17. AI 验收自测清单** ✏️ | 新增"规格一致性自查"分组（3 条） | "再补文档一致性自查" |

---

## v1.5 变更记录

> 本节记录 v1.5 相对 v1.4 的所有变更。变更依据：GPT5.4 第五轮评审建议（详见 `GPT5.4的建议-5.md`）。

### 修复

| 章节 | 问题 | 修复 |
|---|---|---|
| **11.5 能力发现** 🔧 | TCP 自检描述为"连接 `127.0.0.1:自身WS端口`"，但 Agent 不监听本地端口，自检必定失败 | 改为"Python `socket` 模块可导入且 `socket.create_connection()` 可正常调用" |
| **17 失败场景自测** 🔧 | 错误码用大写字符串（`PERMISSION_DENIED`/`CONFLICT`/`VALIDATION_ERROR`），与 14.9 规范的小写 `type` 字段不一致 | 统一为 14.9 格式：`403 + permission_error`、`409 + conflict`、`422 + validation_error` |
| **7.9 前端代码示例** 🔧 | `connect_error` 用 `err.message.includes('AUTH')` 但流程图说用 `connect_error.data` 传递，读取方式矛盾 | 统一为读取 `err.data.code`，`err.message` 不作为业务判断依据 |

### 修改章节

| 章节 | 修改内容 | 对应 GPT5.4 建议 |
|---|---|---|
| **11.5 能力发现** ✏️ | TCP 自检方式改为模块检测；补充"自检失败不阻塞 Agent 启动"硬规则 | "TCP 自检逻辑不成立" + "自检失败是否影响启动没说死" |
| **7.9 WebSocket 错误事件** ✏️ | `connect_error` 前端读取方式统一为 `err.data.code`；后端握手拒绝写入 `data` 字段 | "`connect_error` 读取方式矛盾" |
| **13.2 探测节点** ✏️ | Token 措辞从"业界常见做法"收紧为"MVP 权衡，非默认最佳实践" | "措辞略显过宽" |
| **14.10 REST API 示例** ✏️ | `GET /api/alerts/history` 补充字段完整性说明 | "示例是否为最小子集" |
| **17 AI 验收自测清单** ✏️ | 失败场景自测错误码全部与 14.9 对齐 | "验收规格还没完全跟上" |

---

## 1. 项目概述

### 1.1 是什么

NetworkStatus-Rabbit 是一个 **网络质量监控平台**，用于检测不同节点之间、以及节点到外部目标的网络连通性和质量。

它可以回答这些问题：
- 节点 B 到节点 C 的延迟是多少？丢包率呢？
- 最近 7 天某条链路的网络质量趋势如何？
- 哪些链路在过去 24 小时出现过异常？

### 1.2 不做什么

- **不做**服务器状态监控（CPU/内存/磁盘等 → 那是 ServerStatus-Rabbit 的工作）
- **不做**对外开放的 API 接口
- **不做**全网格自动互 Ping（防止大规模节点场景下失控）

### 1.3 灵感来源

| 项目 | 借鉴了什么 |
|---|---|
| [Network-Monitoring-Tools](https://github.com/littlewolf9527/Network-Monitoring-Tools) | 探测协议实现（ICMP/TCP/UDP/HTTP/DNS），作为底层探测模块直接集成 |
| [ServerStatus-Rabbit](https://github.com/wingsrabbit/ServerStatus-Rabbit) | UI 风格参考、Docker 部署模式、Web 后台管理理念、Webhook 告警机制 |
| [SmartPing](https://github.com/smartping/smartping) | 监控时序图表样式、时间范围切换交互、延迟/丢包可视化设计 |

---

## 2. 核心概念与术语

| 术语 | 含义 |
|---|---|
| **中心节点（Center / A）** | 管理服务端，运行 Web 后台、Dashboard、数据库，汇总存储所有数据 |
| **探测节点（Agent / B, C, D...）** | 部署在被监控机器上的无头客户端，执行实际的网络探测任务并上报数据 |
| **探测任务（Probe Task）** | 一条具体的探测指令，如"节点 B → 节点 C，ICMP Ping，间隔 5 秒" |
| **内部目标** | 系统内的其他探测节点（通过节点 ID 引用） |
| **外部目标** | 系统外的 IP/域名/URL（手动输入） |
| **探测协议（Protocol）** | 执行探测的方式：ICMP Ping / TCP Ping / UDP Ping / HTTP(S) / DNS Lookup |
| **标签（Label）** | 节点的自定义分类标记，最多 3 个，内容不固定（如"华东"、"电信"、"核心"） |
| **降采样（Downsampling）** | 将高精度数据聚合为低精度数据（1s → 1min → 1h），节省存储空间 |

---

## 3. 架构设计与决策说明

### 3.1 整体架构：集中式管理 + 分布式探测

```
┌─────────────────────────────────────────────────────────────┐
│                    中心节点 A (Center)                        │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐ │
│  │  Flask     │  │  Vue 3    │  │ InfluxDB │  │  SQLite   │ │
│  │  后端      │  │  前端     │  │ 时序数据  │  │ 配置数据  │ │
│  │  + WS      │  │  + Naive  │  │ (30天)   │  │ (用户/    │ │
│  │  Server    │  │  UI       │  │          │  │  任务等)  │ │
│  └─────┬─────┘  └───────────┘  └──────────┘  └───────────┘ │
│        │ WebSocket                                           │
└────────┼────────────────────────────────────────────────────┘
         │
    ┌────┴────┬──────────┐
    │         │          │
┌───▼───┐ ┌──▼────┐ ┌───▼───┐
│ 节点 B │ │ 节点 C │ │ 节点 D │    ← 无头探测客户端
│ Agent  │ │ Agent  │ │ Agent  │
│ 本地3天│ │ 本地3天│ │ 本地3天│
└───────┘ └───────┘ └───────┘
```

### 3.2 为什么选集中式？不选去中心化？

**去中心化方案**（如 SmartPing）的做法是：每个节点存自己的数据，查询时前端通过 Ajax 从各节点聚合。

这在"查看全局视图"时有明显问题：
- 任何一个节点网络不通，就查不到它的数据
- 无法做全局统一告警（没有中心来判断）
- 节点越多，前端聚合延迟越高

**集中式方案**的优势：
- 中心节点统一存储，Dashboard 查询快且可靠
- 全局告警只在一个地方判断，逻辑简单
- 管理员在一个界面管理所有节点和任务

**代价**：中心节点是单点。但对于网络监控场景，中心挂了影响的只是"看不到数据"，探测节点本地还有 3 天缓存，中心恢复后不丢数据。

### 3.3 为什么探测节点本地存 3 天？

防止中心节点短暂不可达时丢数据。节点本地用 SQLite 缓存最近 3 天的探测结果：
- 正常情况：数据实时经 WebSocket 上报中心，本地缓存作为备份
- 中心不可达时：数据先存本地，恢复连接后批量补传
- 3 天后自动清理本地数据（节点磁盘可控）

---

## 4. 技术栈与选型理由

### 4.1 后端：Python 3.12 + Flask

| 选项 | 为什么选 / 不选 |
|---|---|
| ✅ **Python + Flask** | Network-Monitoring-Tools 是纯 Python 项目，直接作为模块调用无需跨语言适配；Flask 轻量灵活；ServerStatus-Rabbit 也是 Flask，经验可复用 |
| ❌ Go | SmartPing 用 Go，性能好但需要重写所有探测模块，开发成本高 |
| ❌ Node.js | 前后端都用 JS 看似方便，但 Python 在网络探测领域的库（scapy, socket, subprocess 调 ping/curl）远比 Node 成熟 |

### 4.2 前端：Vue 3 + TypeScript + Naive UI

| 选项 | 为什么选 / 不选 |
|---|---|
| ✅ **Vue 3 + TypeScript** | ServerStatus-Rabbit 前端已用 Vue 3 + TS，保持技术栈一致，降低维护成本 |
| ✅ **Naive UI** | Vue 3 + TS 原生支持；**内建深色模式**，切换丝滑；DataTable 组件强大（支持分组、排序、筛选，正好满足 Dashboard 表格需求）；Tree/Tag 组件适合标签管理；体积小性能好 |
| ❌ Semantic UI | ServerStatus-Rabbit 用的，但它本质是 jQuery 时代的 UI 库，与 Vue 3 的响应式系统集成不够原生 |
| ❌ Element Plus | 国内最流行的 Vue 3 组件库，但表格组件在大数据量分组场景下不如 Naive UI 灵活 |
| ❌ Ant Design Vue | 设计偏企业级办公系统风格，监控面板的视觉冲击力不够 |

### 4.3 图表：ECharts

| 选项 | 为什么选 / 不选 |
|---|---|
| ✅ **ECharts** | SmartPing 的监控图表样式就是 ECharts 实现的，保持视觉一致性；在渲染大量数据点（1 秒粒度 × 24 小时 = 86400 个点）时有 **dataZoom 缩放**、**增量渲染**、**大数据量优化模式（sampling）**，其他图表库做不到这个规模的流畅交互 |
| ❌ Chart.js | 轻量但大数据量下卡顿严重，不适合 1 秒粒度的时序数据 |
| ❌ ApexCharts | API 优雅但生态和性能不如 ECharts |

### 4.4 时序数据库：InfluxDB 2.x

| 选项 | 为什么选 / 不选 |
|---|---|
| ✅ **InfluxDB** | **专业的时序数据库**，天生为"带时间戳的指标数据"设计。核心优势：① 内建 **Retention Policy**（数据保留策略），设好规则自动删过期数据，不用写定时清理脚本；② 内建 **Continuous Query / Task**（持续查询），自动完成降采样（1s→1min→1h），不用手动写聚合逻辑；③ 存储效率极高，时序数据压缩率远超关系型数据库（同样的数据量，InfluxDB 磁盘占用约为 MySQL 的 1/10）；④ 查询语法（Flux）专为时间范围聚合优化 |
| ❌ SQLite | 单文件数据库，不支持自动降采样和保留策略，需要大量手写维护逻辑；1 秒粒度写入性能是瓶颈 |
| ❌ PostgreSQL + TimescaleDB | 功能上可以，但多引入一个大型数据库 + 扩展，部署复杂度远高于 InfluxDB 单容器 |
| ❌ MySQL | 不适合时序场景，无原生降采样能力 |

### 4.5 配置数据库：SQLite

时序数据之外的**配置性数据**（用户账户、节点注册信息、探测任务定义、告警规则、系统设置）存在 SQLite 中。

| 选项 | 为什么选 / 不选 |
|---|---|
| ✅ **SQLite** | 配置数据量很小（几十到几百条记录），SQLite 完全够用；单文件，不需要额外容器；备份就是复制一个文件；Flask 生态有 SQLAlchemy 完美支持 |
| ❌ PostgreSQL | 杀鸡用牛刀，多加一个容器只为存几百行配置数据不值得 |

### 4.6 通信协议：WebSocket（Socket.IO）

| 选项 | 为什么选 / 不选 |
|---|---|
| ✅ **WebSocket (Socket.IO)** | 本项目需要**双向通信**：中心 A 要向节点 B 下发探测任务（A→B），节点 B 要向中心 A 上报探测数据（B→A）。WebSocket 天然支持双向实时通信，一条连接解决两个方向的需求。Socket.IO 是 WebSocket 的封装库，提供自动重连、房间/命名空间、事件驱动等开箱即用的能力，Python 端用 `python-socketio`，前端用 `socket.io-client` |
| ❌ HTTP API 轮询 | 节点定期拉取任务 + 推送数据的方式太原始。轮询间隔设长了延迟高（任务下发要等好久），设短了浪费带宽和 CPU。对于 1 秒探测间隔的场景，轮询完全不适合 |
| ❌ gRPC | 性能极好，双向流也支持，但 Python 端的 gRPC 依赖（grpcio）编译安装慢且体积大，在低配 VPS 上编译可能失败；调试工具不如 WebSocket 方便；前端无法直接用 gRPC（需要 gRPC-Web 代理），增加了架构复杂度 |
| ❌ 原生 TCP 长连接 | ServerStatus-Rabbit 用的方案。能用但要自己实现协议解析、心跳、重连、粘包拆包等底层逻辑。Socket.IO 已经把这些全做好了，没必要重复造轮子 |

### 4.7 Web 服务器 / 反向代理：Nginx

| 选项 | 为什么选 / 不选 |
|---|---|
| ✅ **Nginx** | 作为 Docker Compose 中的入口容器，反代 Flask 后端 API 和 WebSocket 连接，同时直接服务 Vue 构建产物（静态文件）。好处是：前后端共用一个端口对外暴露，部署简洁；Nginx 处理静态文件性能远超 Flask 内建服务器；后续如需 HTTPS 也在 Nginx 层一站搞定 |

### 4.8 容器化：Docker Compose

| 选项 | 为什么选 / 不选 |
|---|---|
| ✅ **Docker Compose 多容器** | 本项目需要跑多个服务（Flask 后端 + InfluxDB + Nginx），把它们塞进一个容器需要用 supervisord 管理多进程，一个挂了全挂，调试困难。Compose 让每个服务独立运行、独立日志、独立重启、独立升级。InfluxDB 出新版本只需要改 Compose 文件的镜像 tag，不用重建整个项目镜像 |
| ❌ 单容器 | ServerStatus-Rabbit 能用单容器是因为它只有一个 Python 进程 + 前端静态文件。加了 InfluxDB 后单容器方案不合理 |

---

## 5. 系统组件

### 5.1 中心节点（Center）组件

```
Center 容器组 (Docker Compose)
├── nginx          # 反向代理 + 静态文件服务
│   ├── 前端静态文件 (Vue 3 构建产物)
│   ├── 反代 /api/* → Flask
│   └── 反代 /socket.io/* → Flask Socket.IO
├── backend        # Flask 后端
│   ├── REST API（节点管理、任务管理、用户管理、告警设置）
│   ├── Socket.IO 服务端（接收探测数据、下发任务）
│   ├── 降采样调度器（触发 InfluxDB Task）
│   ├── 告警引擎（检测阈值、触发 Webhook）
│   └── SQLite（配置数据）
└── influxdb       # 时序数据存储
    ├── raw 桶（原始数据，保留 3 天）
    ├── downsampled_1m 桶（1 分钟聚合，保留 7 天）
    └── downsampled_1h 桶（1 小时聚合，保留 30 天）
```

### 5.2 探测节点（Agent）组件

```
Agent 进程（单个 Python 进程，非 Docker 也可运行）
├── WebSocket 客户端（连接中心、接收任务、上报数据）
├── 任务调度器（按间隔执行探测任务）
├── 探测引擎
│   └── probes/        ← Network-Monitoring-Tools 集成
│       ├── icmp_ping.py
│       ├── tcp_ping.py
│       ├── udp_ping.py
│       ├── http_ping.py
│       └── dns_lookup.py
└── 本地缓存（SQLite，3 天数据备份）
```

---

## 6. 数据模型与存储策略

### 6.1 InfluxDB 数据模型

#### Measurement（相当于"表"）：`probe_result`

| 字段类型 | 名称 | 说明 |
|---|---|---|
| **Tag** | `task_id` | 探测任务 ID |
| **Tag** | `source_node` | 源节点 ID |
| **Tag** | `target` | 目标（节点 ID 或外部地址） |
| **Tag** | `protocol` | 协议（icmp / tcp / udp / http / dns） |
| **Field** | `latency` | 延迟（ms），float |
| **Field** | `packet_loss` | 丢包率（%），float（ICMP/UDP） |
| **Field** | `jitter` | 抖动（ms），float（ICMP） |
| **Field** | `success` | 是否成功，bool（0/1） |
| **Field** | `status_code` | HTTP 状态码，int（HTTP 协议专用） |
| **Field** | `dns_time` | DNS 解析时间（ms），float（HTTP/DNS） |
| **Field** | `tcp_time` | TCP 连接时间（ms），float（HTTP/TCP） |
| **Field** | `tls_time` | TLS 握手时间（ms），float（HTTP） |
| **Field** | `ttfb` | 首字节时间（ms），float（HTTP） |
| **Field** | `total_time` | 总响应时间（ms），float（HTTP） |
| **Field** | `resolved_ip` | 解析到的 IP，string（DNS） |
| **Timestamp** | 自动 | 纳秒精度时间戳 |

> **Tag vs Field 的区别**：Tag 是索引字段，用于 WHERE 过滤和 GROUP BY 分组，值是字符串；Field 是数据字段，用于计算聚合（mean/max/min），值可以是数字。把 `task_id`、`source_node`、`protocol` 设为 Tag，查询时可以高效筛选"某个任务的某种协议在某个时间范围的数据"。

> ✏️ **target Tag 规模说明**：本项目预期外部探测目标数量在 **≤200 个离散值**以内（`target` 字段存储对端节点名或外部地址）。此规模下 `target` 作为 Tag 不存在 InfluxDB 高基数（high cardinality）风险。如未来目标数量增长至数千级别，需评估将 `target` 降级为 Field 或引入 Tag 值归一化方案。

### 6.2 三级存储与降采样策略

```
┌─────────────────────────────────────────────────────────┐
│            InfluxDB Buckets & Retention                  │
├─────────────┬──────────┬────────────────────────────────┤
│ Bucket 名   │ 保留时间  │ 数据粒度                       │
├─────────────┼──────────┼────────────────────────────────┤
│ raw         │ 3 天     │ 原始探测数据（1s~60s 间隔）     │
│ agg_1m      │ 7 天     │ 每分钟聚合：avg/max/min/p95     │
│ agg_1h      │ 30 天    │ 每小时聚合：avg/max/min/p95     │
└─────────────┴──────────┴────────────────────────────────┘
```

**InfluxDB Task（自动降采样任务）**会自动运行：
- 每 1 分钟：从 `raw` 聚合写入 `agg_1m`（计算该分钟内的 avg_latency, max_latency, min_latency, p95_latency, avg_packet_loss）
- 每 1 小时：从 `agg_1m` 聚合写入 `agg_1h`（同样的聚合字段）

**前端查询时自动选择 Bucket**：

| 用户选择时间范围 | 查询的 Bucket | 预期数据点数（5s 间隔任务） |
|---|---|---|
| 6 小时 | `raw` | ~4,320 |
| 12 小时 | `raw` | ~8,640 |
| 24 小时 | `raw` | ~17,280 |
| 3 天 | `agg_1m` | ~4,320 |
| 7 天 | `agg_1m` | ~10,080 |
| 14 天 | `agg_1h` | ~336 |
| 30 天 | `agg_1h` | ~720 |

### 6.3 SQLite 配置数据模型

#### 表：`nodes`（探测节点）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 节点唯一 ID |
| `name` | TEXT | 节点显示名称 |
| `token` | TEXT | 连接认证 Token（bcrypt 哈希存储） |
| `label_1` | TEXT | 自定义标签 1（可空） |
| `label_2` | TEXT | 自定义标签 2（可空） |
| `label_3` | TEXT | 自定义标签 3（可空） |
| `status` | TEXT | 状态（registered/online/offline/disabled） |
| `last_seen` | DATETIME | 最后心跳时间 |
| `created_at` | DATETIME | 注册时间 |
| `enabled` | BOOLEAN | 是否启用 |
| `config_version` | INT | 当前任务配置版本号，默认 0 |
| `capabilities` | TEXT (JSON) | Agent 上报的能力信息（支持的协议列表、OS、版本等），JSON 序列化存储 |
| `agent_version` | TEXT | Agent 版本号 |
| `public_ip` | TEXT | Agent 上报的公网 IP |
| `private_ip` | TEXT | Agent 上报的内网 IP |

#### 表：`probe_tasks`（探测任务）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 任务 ID |
| `name` | TEXT | 任务名称（可选，管理员起的描述性名字） |
| `source_node_id` | TEXT (FK) | 源节点 ID |
| `target_type` | TEXT | 目标类型：`internal`（系统内节点）/ `external`（外部地址） |
| `target_node_id` | TEXT (FK) | 内部目标节点 ID（target_type=internal 时） |
| `target_address` | TEXT | 外部目标地址（target_type=external 时，如 8.8.8.8 或 google.com） |
| `target_port` | INT | 目标端口（TCP/UDP/HTTP 时使用） |
| `protocol` | TEXT | 探测协议（icmp/tcp/udp/http/dns） |
| `interval` | INT | 探测间隔（秒），1-60，默认 5 |
| `timeout` | INT | 超时时间（秒），默认 10 |
| `enabled` | BOOLEAN | 是否启用 |
| `created_at` | DATETIME | 创建时间 |
| `alert_latency_threshold` | FLOAT | 延迟告警阈值（ms），NULL 表示不告警 |
| `alert_loss_threshold` | FLOAT | 丢包率告警阈值（%），NULL 表示不告警 |
| `alert_fail_count` | INT | 连续失败次数告警阈值，NULL 表示不告警 |
| `alert_eval_window` | INT | 评估窗口大小：看最近 N 次探测结果，默认 5 |
| `alert_trigger_count` | INT | 触发阈值：窗口内 ≥ M 次超阈值才告警，默认 3 |
| `alert_recovery_count` | INT | 恢复阈值：连续 K 次正常才发恢复通知，默认 3 |
| `alert_cooldown_seconds` | INT | 冷却时间（秒），默认 300 |

#### 表：`users`（用户）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 用户 ID |
| `username` | TEXT | 用户名 |
| `password_hash` | TEXT | 密码（bcrypt 哈希） |
| `role` | TEXT | 角色：`admin` / `readonly` |
| `created_at` | DATETIME | 创建时间 |
| `created_by` | TEXT | 创建者（管理员用户名，或 "system" 表示 Docker 命令创建） |

#### 表：`alert_channels`（告警通道）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 通道 ID |
| `name` | TEXT | 通道名称（如"企业微信运维群"） |
| `type` | TEXT | 类型：`webhook` |
| `url` | TEXT | Webhook URL |
| `enabled` | BOOLEAN | 是否启用 |

#### 表：`alert_history`（告警历史） 🆕

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 告警事件 ID |
| `task_id` | TEXT (FK) | 关联的探测任务 ID |
| `event_type` | TEXT | 事件类型：`alert`（告警触发）/ `recovery`（恢复正常） |
| `metric` | TEXT | 触发的告警指标类型：`latency` / `packet_loss` / `continuous_fail` |
| `actual_value` | FLOAT | 触发时的实际值（延迟 ms / 丢包率 % / 连续失败次数） |
| `threshold` | FLOAT | 对应的告警阈值 |
| `message` | TEXT | 人类可读的告警描述（如"延迟 235ms 超过阈值 100ms"） |
| `alert_started_at` | DATETIME | 告警开始时间（alert 事件填写触发时间；recovery 事件填写对应的告警开始时间） |
| `duration_seconds` | INT | 告警持续时长（秒），仅 recovery 事件填写（= recovery 时间 - alert_started_at） |
| `notified` | BOOLEAN | 通知是否发送成功（包含 Webhook 等所有通知渠道） |
| `created_at` | DATETIME | 本条记录创建时间 |

> **去重规则**：同一 `(task_id, metric)` 组合在 alerting 状态且冷却期内，不重复写入 alert_history。冷却期过后再次触发才写新记录。

#### 表：`settings`（系统设置）

| 列 | 类型 | 说明 |
|---|---|---|
| `key` | TEXT (PK) | 设置项键名 |
| `value` | TEXT | 设置项值（JSON 序列化） |

### 6.4 Agent 本地缓存数据模型 🆕

Agent 端使用独立的 SQLite 数据库缓存未确认的探测结果，保证断线期间数据不丢失。

#### 表：`local_results`（本地缓存探测结果）

| 列 | 类型 | 说明 |
|---|---|---|
| `result_id` | TEXT (PK) | 探测结果全局唯一 ID（格式：`{node_id}-{unix_timestamp_ms}-{protocol}-{seq}`） |
| `task_id` | TEXT | 关联的探测任务 ID |
| `payload_json` | TEXT | 完整的探测结果 JSON（与 `agent:probe_result` 事件的 payload 一致） |
| `ack_status` | TEXT | ACK 状态：`pending`（待发送/待确认）/ `sent`（已发送待 ACK）/ `acked`（已确认） |
| `batch_id` | TEXT | 所属的补传批次 ID（仅补传时填写，实时发送时为 NULL） |
| `retry_count` | INT | 发送重试次数，默认 0 |
| `created_at` | DATETIME | 探测时间（本地时钟） |
| `sent_at` | DATETIME | 最近一次发送时间（NULL 表示尚未发送） |
| `acked_at` | DATETIME | 收到 ACK 的时间（NULL 表示尚未确认） |

**生命周期**：

1. 探测完成 → 写入 `local_results`（ack_status = `pending`）
2. 在线时 → 发送 `agent:probe_result` → ack_status 改为 `sent`
3. 收到 `center:result_ack` → ack_status 改为 `acked`，记录 acked_at
4. ack_status = `acked` 的记录保留至 **超过 3 天** 后定时清理
5. 断线重连 → 查询所有 ack_status ≠ `acked` 的记录 → 组装为 batch → 发送 `agent:probe_batch`
6. 收到 `center:batch_ack` → 匹配 `accepted_ids` → 批量更新为 `acked`

**定时清理规则**：每小时运行一次，删除 `acked_at < now() - 3天` 的记录。`pending` / `sent` 状态的记录**不清理**（可能还需要补传）。

---

## 7. 通信协议设计 ✏️

### 7.1 Socket.IO 事件定义

#### 节点 → 中心（上行）

| 事件名 | 触发时机 | 数据格式 |
|---|---|---|
| `agent:auth` | 节点连接后首次认证 | `{ node_id, token, config_version, capabilities }` |
| `agent:heartbeat` | 每秒 1 次（详见 7.5 节点存活检测） | `{ node_id, seq }` |
| `agent:probe_result` | 每次探测完成后 | `{ result_id, task_id, timestamp, protocol, metrics }` |
| `agent:probe_batch` | 断线重连后批量补传 | `{ batch_id, results: [ { result_id, ... }, ... ] }` |
| `agent:task_ack` | 节点确认任务同步成功 | `{ config_version }` |

#### 中心 → 节点（下行）

| 事件名 | 触发时机 | 数据格式 |
|---|---|---|
| `center:auth_result` | 认证响应 | `{ success, message }` |
| `center:task_assign` | 下发新探测任务 | `{ task_id, target, protocol, interval, timeout, config_version, ... }` |
| `center:task_update` | 更新已有任务参数 | `{ task_id, changes, config_version }` |
| `center:task_remove` | 删除探测任务 | `{ task_id, config_version }` |
| `center:task_sync` | 全量同步 | `{ config_version, tasks: [ { task_id, ... }, ... ] }` |
| `center:batch_ack` | 确认批量补传已入库 | `{ batch_id, accepted_ids: [...] }` |
| `center:result_ack` | 确认单条数据已入库 | `{ result_id }` |

### 7.2 关键事件 JSON 示例

#### `agent:auth`（节点认证）

```json
{
  "node_id": "node-b-uuid-1234",
  "token": "raw-token-string",
  "config_version": 5,
  "capabilities": {
    "protocols": ["icmp", "tcp", "http", "dns"],
    "unsupported": ["udp"],
    "unsupported_reasons": { "udp": "nc (netcat) not installed" },
    "agent_version": "0.1.0",
    "os": "Ubuntu 22.04",
    "public_ip": "203.0.113.10",
    "private_ip": "10.0.1.5"
  }
}
```

#### `agent:probe_result`（单条探测结果）

```json
{
  "result_id": "node-b-1711152930-icmp-001",
  "task_id": "task-uuid-5678",
  "timestamp": "2026-03-23T10:15:30.000Z",
  "protocol": "icmp",
  "metrics": {
    "success": true,
    "latency": 12.5,
    "packet_loss": 0.0,
    "jitter": 1.2,
    "error": null
  }
}
```

> **`result_id` 生成规则**：`{node_id}-{unix_timestamp_ms}-{protocol}-{seq}`，在单节点范围内保证唯一。中心端写入 InfluxDB 前用 `result_id` 去重（幂等写入），避免断线补传时重复写入同一条数据。

#### `agent:probe_batch`（批量补传）

```json
{
  "batch_id": "batch-node-b-1711153000",
  "results": [
    {
      "result_id": "node-b-1711152000-icmp-001",
      "task_id": "task-uuid-5678",
      "timestamp": "2026-03-23T09:00:00.000Z",
      "protocol": "icmp",
      "metrics": { "success": true, "latency": 15.3, "packet_loss": 0.0, "jitter": 0.8, "error": null }
    },
    {
      "result_id": "node-b-1711152005-icmp-002",
      "task_id": "task-uuid-5678",
      "timestamp": "2026-03-23T09:00:05.000Z",
      "protocol": "icmp",
      "metrics": { "success": false, "latency": null, "packet_loss": 100.0, "jitter": null, "error": "Request timed out" }
    }
  ]
}
```

#### `center:task_sync`（全量任务同步）

```json
{
  "config_version": 8,
  "tasks": [
    {
      "task_id": "task-uuid-5678",
      "target_type": "internal",
      "target_address": "10.0.1.10",
      "target_port": null,
      "protocol": "icmp",
      "interval": 5,
      "timeout": 10,
      "enabled": true
    },
    {
      "task_id": "task-uuid-9012",
      "target_type": "external",
      "target_address": "8.8.8.8",
      "target_port": 53,
      "protocol": "tcp",
      "interval": 10,
      "timeout": 5,
      "enabled": true
    }
  ]
}
```

#### `dashboard:probe_snapshot`（Dashboard 聚合快照，替代逐条广播）

```json
{
  "timestamp": "2026-03-23T10:15:31.000Z",
  "tasks": {
    "task-uuid-5678": {
      "last_latency": 12.5,
      "last_packet_loss": 0.0,
      "last_success": true,
      "status": "normal"
    },
    "task-uuid-9012": {
      "last_latency": 235.0,
      "last_packet_loss": 0.0,
      "last_success": true,
      "status": "warning"
    }
  }
}
```

### 7.3 连接生命周期

```
节点启动
  │
  ├─→ 连接 WebSocket → ws://center:port（Socket.IO 自动使用 /socket.io/ 路径）
  │
  ├─→ 发送 agent:auth { node_id, token, config_version, capabilities }
  │         ↑ capabilities 包含支持的协议列表、Agent 版本、OS 信息
  │
  ├─→ 收到 center:auth_result { success: true }
  │
  ├─→ 中心比较 config_version：
  │     ├─ 节点版本 < 中心版本 → 发送 center:task_sync（全量）
  │     └─ 节点版本 = 中心版本 → 不发送（任务未变化）
  │
  ├─→ 节点收到 task_sync → 应用任务 → 回复 agent:task_ack { config_version }
  │
  ├─→ 检查本地是否有未 ACK 的缓存数据 → 如有，发送 agent:probe_batch
  │     ├─→ 中心入库 → 回复 center:batch_ack { batch_id, accepted_ids }
  │     └─→ 节点收到 ACK → 删除已确认的本地缓存
  │
  ├─→ 开始执行探测任务 ─→ 循环发送 agent:probe_result
  │     ├─→ 中心入库 → 回复 center:result_ack { result_id }
  │     └─→ 节点收到 ACK → 标记本地缓存为已确认
  │
  ├─→ 每秒 发送 agent:heartbeat（轻量，仅 { node_id, seq }）
  │
  ├─→ 收到 center:task_assign / task_update / task_remove（均带 config_version）
  │     └─→ 节点应用变更 → 回复 agent:task_ack { config_version }
  │
  └─→ 断线 → 数据暂存本地 SQLite → Socket.IO 自动重连 → 重新 auth → 补传
```

### 7.4 断线补传协议

断线补传是保障数据完整性的关键机制。核心规则如下：

#### 7.4.1 数据去重（幂等写入）

- 每条探测结果携带全局唯一的 `result_id`
- `result_id` 格式：`{node_id}-{unix_timestamp_ms}-{protocol}-{seq}`
- 中心写入 InfluxDB 前检查 `result_id` 是否已存在
- 已存在则跳过写入但仍返回 ACK（幂等）
- **效果**：即使网络抖动导致同一条数据发送了两次，也不会在数据库中出现重复记录

#### 7.4.2 ACK 确认机制

- **实时数据**：每条 `agent:probe_result` 入库后，中心回复 `center:result_ack { result_id }`
- **批量补传**：每批 `agent:probe_batch` 入库后，中心回复 `center:batch_ack { batch_id, accepted_ids }`
- 节点只删除已收到 ACK 的本地缓存数据
- 未收到 ACK 的数据保留在本地，下次连接时重传

#### 7.4.3 告警重放抑制

- **关键规则：历史补传数据不触发实时告警**
- 中心收到数据时，判断 `timestamp` 与当前时间的差值
- 若 `timestamp` 早于当前时间超过 **60 秒**，视为历史补传数据，只入库不告警
- 只有时间戳在 60 秒内的数据才进入告警引擎评估
- **原因**：假设节点断线 1 小时后重连，补传了 1 小时的数据。如果这些数据全部进入告警引擎，会瞬间触发大量过期告警，造成告警风暴，毫无实际运维价值

### 7.5 节点存活检测

节点的在线/离线判定**不依赖**简单的"3 次心跳超时"，而是采用更精确的**滑动窗口成功率检测**。

#### 检测机制

- Agent 每秒向中心发送 1 个轻量心跳包：`agent:heartbeat { node_id, seq }`
- 中心维护每个节点最近 **120 秒** 的心跳接收记录（滑动窗口，120 个槽位）
- 每个槽位记录该秒是否收到心跳：收到 = 1，未收到 = 0

#### 离线判定规则

| 条件 | 结果 |
|---|---|
| 120 秒窗口内收到 ≥ 21 个心跳 | **在线（online）** |
| 120 秒窗口内收到 ≤ 20 个心跳 | **离线（offline）** |

> **设计理由**：阈值 20/120 意味着 83.3% 的心跳丢失才判定离线。这个设计可以容忍短暂的网络抖动和偶发丢包——即使链路质量很差（丢了 83% 的包），只要还有 17% 能到达，就说明节点还活着。但如果 120 秒内只收到不到 20 个包，基本等同于节点已经不可达了。

#### 为什么不用"3 次心跳超时 = 离线"？

传统方案（如每 30 秒心跳一次，90 秒未收到就离线）有一个致命问题：**网络抖动时过于敏感**。如果链路偶尔丢几个包，节点就会被误判为离线，然后恢复，然后又离线——产生大量无意义的离线/上线告警。

滑动窗口方案的优势是：在 2 分钟窗口内统计成功率，只有持续性的不可达才会触发离线，偶发性丢包不会。

### 7.6 任务版本同步（config_version）

任务同步使用**乐观版本号**机制防止乱序覆盖：

#### 规则

1. 中心端维护每个节点的 `config_version`（整数，从 0 开始）
2. 每次对某节点的任务进行增/删/改，该节点的 `config_version` +1
3. 所有任务变更事件（`task_assign` / `task_update` / `task_remove`）都携带当前 `config_version`
4. 节点应用变更后回复 `agent:task_ack { config_version }`
5. 节点断线重连时上报自己当前的 `config_version`：
   - 若节点版本 < 中心版本 → 中心发送 `center:task_sync`（全量覆盖）
   - 若节点版本 = 中心版本 → 不发送（无变化）
   - 若节点版本 > 中心版本 → **异常**，中心强制发送全量同步并记录警告日志

#### 为什么不用增量同步？

增量同步（只发送差异）理论上更高效，但实现复杂度高（要维护变更日志、处理合并冲突等）。对于本项目的规模（单节点通常只有几十个任务），全量同步的开销可以忽略不计，但可靠性高很多。**简单可靠优先于理论最优**。

### 7.7 前端实时推送

前端 Dashboard 通过 Socket.IO 连接后端，接收实时数据更新。

**采用节流推送模式**：后端不会把每一条探测结果都逐条广播到前端，而是按固定频率（每秒 1 次）发送聚合快照。

| 事件名 | 方向 | 说明 |
|---|---|---|
| `dashboard:node_status` | 后端 → 前端 | 节点在线/离线状态变更（即时推送，不节流） |
| `dashboard:probe_snapshot` | 后端 → 前端 | 所有任务的最新状态快照（每秒 1 次，包含每个任务的最新延迟/丢包/状态） |
| `dashboard:alert` | 后端 → 前端 | 触发的告警通知（即时推送，不节流） |
| `dashboard:task_detail` | 后端 → 前端 | 单个任务的详细探测数据（仅当用户打开某个任务详情页时，订阅该任务的细粒度数据推送） |

> **节流推送 vs 逐条广播**：如果有 100 个探测任务，每个任务 5 秒间隔，逐条广播意味着每秒平均推送 20 条消息给每个在线前端用户。节流为每秒 1 条快照，数据量降低 20 倍，前端渲染压力也大幅减轻。详情页需要看细粒度数据时，前端通过 `subscribe_task` 事件订阅特定任务的增量推送。

### 7.8 详情页订阅协议 🆕

当用户打开某个任务的详情页时，前端需要订阅该任务的细粒度实时数据。订阅协议定义如下：

#### 事件定义

| 事件名 | 方向 | 触发时机 | 数据格式 |
|---|---|---|---|
| `dashboard:subscribe_task` | 前端 → 后端 | 进入任务详情页时 | `{ task_id }` |
| `dashboard:unsubscribe_task` | 前端 → 后端 | 离开任务详情页时 | `{ task_id }` |
| `dashboard:task_detail` | 后端 → 前端 | 订阅生效后每条新探测结果到达时 | `{ task_id, result }` |

#### `dashboard:subscribe_task`

```json
{
  "task_id": "task-uuid-5678"
}
```

后端收到后：
1. 将该 Socket.IO 连接加入 room `task:{task_id}`
2. 后续该任务每收到一条新的探测结果，向 room 内所有连接推送 `dashboard:task_detail`

#### `dashboard:unsubscribe_task`

```json
{
  "task_id": "task-uuid-5678"
}
```

后端收到后：将该连接从 room `task:{task_id}` 移除。

#### `dashboard:task_detail`（推送数据示例）

```json
{
  "task_id": "task-uuid-5678",
  "result": {
    "result_id": "node-b-uuid-1711180805123-icmp-42",
    "timestamp": "2026-03-23T12:00:05Z",
    "protocol": "icmp",
    "latency": 12.5,
    "packet_loss": 0,
    "jitter": 1.2,
    "success": true
  }
}
```

#### 生命周期规则

| 规则 | 说明 |
|---|---|
| 一个连接可以同时订阅多个任务 | 例如用户在多个标签页打开不同详情页（同一个 WebSocket 连接） |
| 离开详情页必须取消订阅 | 前端在 Vue `onUnmounted` 生命周期中发送 `unsubscribe_task` |
| 连接断开自动清理 | 后端在 `disconnect` 事件中自动将该连接从所有 task room 移除 |
| 订阅不影响快照推送 | `dashboard:probe_snapshot` 仍然独立推送，订阅的细粒度数据是**额外的**增量数据 |

### 7.9 WebSocket 错误事件规范 🆕

Socket.IO 错误事件格式。

> ⚠️ **格式说明**：WS 错误格式与 REST API 错误格式 **故意不同**。REST 使用 `{error: {code, type, message}}` 包裹结构，而 WS 事件名本身就是 `error`，已起到外层包裹的作用，再套一层 `{error:{...}}` 是冗余的。因此 WS 错误 payload 直接是扁平的 `{code, message}` 结构，其中 `code` 为字符串业务码（带 `WS_` 前缀，与 REST 的 HTTP 数字码明确区分）。

```
事件名: error
方向: Server → Client
```

```json
{
  "code": "WS_AUTH_FAILED",
  "message": "Cookie 中的 JWT 无效或已过期"
}
```

#### 错误码定义

| 错误码 | 触发场景 | 后端处理 | 前端处理 |
|---|---|---|---|
| `WS_AUTH_FAILED` | 连接握手时 Cookie 无效 / 缺失 / JWT 过期 | **拒绝连接**（`connect_error`） | 跳转登录页 |
| `WS_TOKEN_EXPIRED` | 连接中 JWT 过期（长连接场景） | 发送 error 事件 → 5 秒后断开 | 尝试静默刷新；失败则跳转登录页 |
| `WS_PERMISSION_DENIED` | 无权限的操作（如 readonly 用户尝试写操作） | 发送 error 事件，**不断开** | 显示提示信息 |
| `WS_INVALID_SUBSCRIBE` | 订阅不存在的 task_id 或无权限的任务 | 发送 error 事件，**不断开** | 显示提示，返回上级页面 |
| `WS_BAD_REQUEST` | 事件参数格式错误（缺少必填字段、类型错误） | 发送 error 事件，**不断开** | 开发期日志输出 |

#### 连接拒绝 vs 事件推送 的区别

```
连接握手阶段（connect）：
  ├── Cookie 有效 → 连接成功 ✅
  └── Cookie 无效/缺失 → 拒绝连接 ❌（触发客户端 connect_error 事件）
                          后端通过 `raise ConnectionRefusedError` 时写入 `data` 字段：
                          `{ code: 'WS_AUTH_FAILED', message: '...' }`
                          前端统一从 `err.data.code` 读取错误码

连接建立后（已连接状态）：
  ├── JWT 过期 → server emit('error', {code: 'WS_TOKEN_EXPIRED', ...}) → 延迟断开
  ├── 权限不足 → server emit('error', {code: 'WS_PERMISSION_DENIED', ...}) → 不断开
  └── 参数错误 → server emit('error', {code: 'WS_BAD_REQUEST', ...}) → 不断开
```

#### 前端统一监听

```typescript
// socket.io-client 连接配置
const socket = io({
  withCredentials: true,  // 携带 httpOnly Cookie
  // 无需手动传 token，Cookie 自动携带
});

// 连接握手失败
socket.on('connect_error', (err) => {
  // 统一从 err.data.code 读取错误码，err.message 不作为业务判断依据
  if (err.data?.code === 'WS_AUTH_FAILED') {
    router.push('/login');
  }
});

// 连接建立后的错误
socket.on('error', (payload: { code: string; message: string }) => {
  switch (payload.code) {
    case 'WS_TOKEN_EXPIRED':
      // 尝试刷新 or 跳转登录
      break;
    case 'WS_PERMISSION_DENIED':
    case 'WS_INVALID_SUBSCRIBE':
      notification.warning({ content: payload.message });
      break;
  }
});
```

---

## 8. 核心状态机 🆕

### 8.1 节点状态机

```
                       ┌─────────────┐
     节点首次注册 ────→  │  registered  │  （已注册，从未连接）
                       └──────┬──────┘
                              │ agent:auth 成功
                              ▼
                       ┌─────────────┐
              ┌───────→│   online     │←──────────┐
              │        └──────┬──────┘            │
              │               │                    │
              │  120s 窗口内   │ 120s 窗口内        │ 重新连接 +
              │  心跳 ≥ 21    │ 心跳 ≤ 20          │ auth 成功 +
              │               │                    │ 心跳恢复
              │               ▼                    │
              │        ┌─────────────┐            │
              └────────│   offline    │────────────┘
                       └──────┬──────┘
                              │ 管理员手动禁用
                              ▼
                       ┌─────────────┐
                       │  disabled    │  （管理员禁用，不接受连接）
                       └─────────────┘
```

| 当前状态 | 触发条件 | 下一个状态 | 系统行为 |
|---|---|---|---|
| registered | Agent 首次 auth 成功 | online | 记录 capabilities，开始接收心跳 |
| online | 120s 窗口内心跳 ≤ 20 | offline | 触发节点离线告警通知，Dashboard 更新状态 |
| offline | Agent 重连 + auth 成功 + 心跳恢复到 ≥ 21 | online | 触发节点上线恢复通知，触发断线补传流程 |
| online / offline | 管理员在后台禁用节点 | disabled | 断开 WebSocket 连接，停止所有该节点的任务 |
| disabled | 管理员在后台启用节点 | registered | 等待 Agent 重新连接 |

### 8.2 告警事件状态机

每个 `(task_id, metric)` 组合维护一个独立的状态机：

```
              ┌─────────────┐
   初始状态 →  │   normal     │
              └──────┬──────┘
                     │ 评估窗口内触发次数 ≥ alert_trigger_count
                     ▼
              ┌─────────────┐
              │  alerting    │ ← 发送告警通知 + 记录告警历史
              └──────┬──────┘
                     │ 连续 alert_recovery_count 次正常
                     ▼
              ┌─────────────┐
              │  recovering  │ ← 发送恢复通知
              └──────┬──────┘
                     │ 自动
                     ▼
              ┌─────────────┐
              │   normal     │
              └─────────────┘
```

| 当前状态 | 触发条件 | 下一个状态 | 系统行为 |
|---|---|---|---|
| normal | 评估窗口（最近 N 次）中有 ≥ M 次超阈值 | alerting | 发送 Webhook 告警通知；推送前端告警；记录 alert_history |
| alerting | 同一规则在冷却期内再次评估为超阈值 | alerting（保持） | 不重复发送通知（冷却中） |
| alerting | 冷却期过后再次评估为超阈值 | alerting（保持） | 重新发送告警通知 |
| alerting | 连续 K 次探测结果正常 | recovering → normal | 发送恢复通知；记录恢复事件 |
| normal | 单次超阈值但窗口内总计未达 M 次 | normal（保持） | 不触发告警（容忍偶发异常） |

### 8.3 任务同步状态机

每个节点维护一个 config_version 的同步状态：

| 当前状态 | 触发条件 | 下一个状态 | 系统行为 |
|---|---|---|---|
| synced | 管理员创建/修改/删除该节点的任务 | pending | 中心 config_version +1，发送 task_assign/update/remove |
| pending | 节点回复 agent:task_ack 且版本匹配 | synced | 确认同步完成 |
| pending | 节点断线 | desync | 等待节点重连 |
| desync | 节点重连并上报旧版本号 | pending | 中心发送 center:task_sync 全量同步 |
| pending | 30 秒内未收到 task_ack | pending（重试） | 重新发送变更事件，最多重试 3 次，3 次后标记为 desync |

---

## 9. 认证与权限模型 ✏️

### 9.1 角色定义

| 角色 | 权限 |
|---|---|
| **admin** | 节点增删改、任务增删改、告警设置、用户管理（创建/删除只读用户、设置其他用户为管理员）、系统设置 |
| **readonly** | 查看 Dashboard、查看详情图表、查看告警历史。**不能**创建/修改/删除任何数据 |

### 9.2 管理员管理

管理员是**平级**的，没有超级管理员的概念：
- 任何管理员可以把只读用户提升为管理员
- 任何管理员可以创建/删除只读用户
- 管理员**不能在 Web 界面删除其他管理员**（防止互相踢出）
- 管理员**不能在 Web 界面降级其他管理员**（要降级只能通过 CLI）
- 通过 **Docker 命令** 强制添加/删除管理员：

```bash
# 添加管理员
docker exec -it ns-center python manage.py create-admin --username=admin1 --password=xxx

# 删除管理员
docker exec -it ns-center python manage.py remove-admin --username=admin1

# 重置管理员密码
docker exec -it ns-center python manage.py reset-password --username=admin1
```

### 9.3 只读用户

- 由管理员在 Web 后台创建
- 凭用户名 + 密码登录
- 看到所有数据（初版不做数据隔离）

### 9.4 节点认证

- 管理员在后台添加节点时，系统自动生成 Token
- 节点连接时携带 `node_id + token` 进行认证
- Token 以 bcrypt 哈希存储在数据库中

### 9.5 登录安全 ✏️

- **httpOnly Cookie 认证**：登录成功后，后端将 JWT Token 写入 `Set-Cookie` 响应头，前端**不接触 Token 本身**
  - `HttpOnly`：JS 无法读取 Cookie，防止 XSS 窃取 Token
  - `SameSite=Strict`：Cookie 只在同站请求中携带，防止 CSRF 攻击
  - `Secure`：生产环境开启 HTTPS 时强制安全传输（开发环境可关闭）
  - `Path=/`：Cookie 在所有路径下携带（REST API `/api/*` 和 WebSocket `/socket.io/*` 均需要认证）
  - > ⚠️ **部署前提**：初版前后端必须同站点部署（Nginx 统一入口），`SameSite=Strict` + `HttpOnly` 已足够安全，`Path=/` 不会带来额外风险（Nginx 直接返回静态文件，Cookie 不会到达 Flask）
- 前端 axios 无需手动设置 `Authorization` header，浏览器自动携带 Cookie
- Socket.IO 连接时，浏览器同样自动携带 Cookie（Cookie Path=/ 确保 `/socket.io/*` 路径也能携带），后端从 Cookie 中提取 JWT 验证身份
- 连续 10 次密码错误锁定账户 15 分钟
- 密码使用 bcrypt 哈希存储

#### 为什么用 httpOnly Cookie 而不是 localStorage 存 JWT？

localStorage 存 Token 的问题：如果网站存在 XSS 漏洞（任何一个输入点没做好过滤），攻击者的 JS 脚本可以直接 `localStorage.getItem('token')` 偷走 Token。httpOnly Cookie 对 JS 完全不可见，即使有 XSS 也偷不到。虽然这是公网项目不是内网，安全性优先。

SameSite=Strict 已经足够防止 CSRF（Cookie 不会在跨站请求中被发送），所以**不需要额外的 CSRF Token 机制**，实现复杂度和 localStorage 方案基本一致。

### 9.6 权限硬规则表 🆕

以下规则为**禁止项**，AI Agent 实现时必须严格遵守，不得自行变通：

| # | 主体 | 操作 | 允许/禁止 | 备注 |
|---|---|---|---|---|
| 1 | admin | 通过 Web 降级其他 admin 为 readonly | ❌ 禁止 | 只能通过 CLI 操作 |
| 2 | admin | 通过 Web 删除其他 admin | ❌ 禁止 | 只能通过 CLI 操作 |
| 3 | admin | 删除自己的账户 | ❌ 禁止 | 防止系统无管理员 |
| 4 | admin | 降级自己为 readonly | ❌ 禁止 | 防止系统无管理员 |
| 5 | admin | 提升 readonly 为 admin | ✅ 允许 | Web 后台操作 |
| 6 | admin | 创建 readonly 用户 | ✅ 允许 | Web 后台操作 |
| 7 | admin | 删除 readonly 用户 | ✅ 允许 | Web 后台操作 |
| 8 | readonly | 任何写操作（增删改） | ❌ 禁止 | 只有查看权限 |
| 9 | 系统 | 删除最后一个 admin | ❌ 禁止 | 包括 CLI，必须始终保留 ≥ 1 个 admin |
| 10 | CLI | 添加/删除/降级 admin | ✅ 允许 | 唯一可操作 admin 身份的途径（受规则 9 约束） |
| 11 | 未登录用户 | 访问任何 `/api/*`（除 login） | ❌ 禁止 | 返回 401 |
| 12 | readonly | 访问 `/admin/*` 管理页面 | ❌ 禁止 | 前端路由守卫 + 后端 403 双重拦截 |

---

## 10. 前端设计

### 10.1 页面结构

```
/                        → 登录页（未登录时）
/dashboard               → Dashboard 总览（默认首页）
/dashboard/:taskId       → 探测任务详情（时序图表）
/admin/nodes             → 节点管理
/admin/tasks             → 任务管理
/admin/alerts            → 告警设置
/admin/users             → 用户管理（仅 admin）
/admin/settings          → 系统设置
```

### 10.2 Dashboard 总览页

**布局**：

```
┌──────────────────────────────────────────────────────────┐
│  NetworkStatus-Rabbit          [深色模式切换] [用户菜单]   │
├──────────────────────────────────────────────────────────┤
│  状态概览栏                                               │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐                 │
│  │ 节点数 │ │ 任务数 │ │ 正常  │ │ 告警  │                 │
│  │  12   │  │  34  │  │  31  │  │  3   │                 │
│  └──────┘  └──────┘  └──────┘  └──────┘                 │
├──────────────────────────────────────────────────────────┤
│  筛选栏：[协议▼] [标签▼] [状态▼] [搜索...]               │
├──────────────────────────────────────────────────────────┤
│  ▼ 节点 B (华东-电信)               ← 按源节点分组，可折叠  │
│  ┌──────┬──────┬────┬─────┬────┬────┬──────┐            │
│  │ 任务名 │ 目标  │ 协议 │ 延迟  │ 丢包 │ 状态 │ 操作   │            │
│  ├──────┼──────┼────┼─────┼────┼────┼──────┤            │
│  │ B→C  │ 节点C │ ICMP│ 12ms│ 0% │ 🟢 │ [详情]│            │
│  │ B→8.8│ 8.8.8│ ICMP│ 45ms│ 1% │ 🟡 │ [详情]│            │
│  │ B→Web│ goo..│ HTTP│ 120m│ 0% │ 🟢 │ [详情]│            │
│  └──────┴──────┴────┴─────┴────┴────┴──────┘            │
│                                                          │
│  ▶ 节点 C (华南-联通)               ← 折叠状态            │
│  ▶ 节点 D (华北-移动)                                     │
└──────────────────────────────────────────────────────────┘
```

- 表格实时刷新（WebSocket 推送最新数据）
- 状态灯颜色：🟢 正常 / 🟡 警告（接近阈值）/ 🔴 异常（超阈值或失败）/ ⚫ 离线
- 点击 `[详情]` 进入任务详情页

### 10.3 任务详情页（时序图表）

**布局**：

```
┌──────────────────────────────────────────────────────────┐
│  ← 返回     任务：B → C (ICMP Ping)                      │
├──────────────────────────────────────────────────────────┤
│  时间范围：[6h] [12h] [24h] [3d] [7d] [14d] [30d] [自定义]│
├──────────────────────────────────────────────────────────┤
│                                                          │
│  延迟 (ms)                              ← ECharts 折线图  │
│  200 ┤                                                   │
│  150 ┤         ╱╲                                        │
│  100 ┤    ╱╲╱╲╱  ╲╱╲                                    │
│   50 ┤╱╲╱              ╲╱╲╱╲╱╲╱╲                       │
│    0 ┼───────────────────────────────→ 时间               │
│        [=========== dataZoom 缩放条 ===========]          │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  丢包率 (%)                             ← ECharts 柱状图  │
│  100 ┤                                                   │
│   50 ┤                                                   │
│    0 ┤▁▁▁▁▁▁▁▁█▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁→ 时间               │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  统计面板                                                 │
│  ┌──────────┬──────────┬──────────┬──────────┐           │
│  │ 平均延迟  │ 最大延迟  │ 最小延迟  │ P95 延迟 │           │
│  │  32ms    │  189ms   │  8ms     │  67ms    │           │
│  ├──────────┼──────────┼──────────┼──────────┤           │
│  │ 平均丢包率│ 总探测次数│ 成功次数  │ 可用率    │           │
│  │  0.3%    │  17280   │  17228   │  99.7%   │           │
│  └──────────┴──────────┴──────────┴──────────┘           │
└──────────────────────────────────────────────────────────┘
```

- 图表支持 **dataZoom**（底部缩放条，可拖拽选择子范围）
- 图表支持 **tooltip**（鼠标悬停显示精确数值和时间）
- 图表支持 **异常区间标记**（ECharts markArea）：在图表上用半透明红色区域标注告警触发时段，鼠标悬停显示告警规则和持续时间
- 不同协议展示不同指标组合（见 10.4）

### 10.4 各协议展示的图表

| 协议 | 图表 1 | 图表 2 | 图表 3 | 统计面板额外字段 |
|---|---|---|---|---|
| **ICMP Ping** | 延迟折线图 | 丢包率柱状图 | 抖动折线图 | — |
| **TCP Ping** | 连接延迟折线图 | 连接成功率柱状图 | — | — |
| **UDP Ping** | 延迟折线图 | 丢包率柱状图 | — | — |
| **HTTP/HTTPS** | 总响应时间折线图 | 各阶段堆叠面积图（DNS+TCP+TLS+TTFB） | HTTP 状态码散点图 | — |
| **DNS Lookup** | 解析时间折线图 | 解析成功率柱状图 | — | 解析 IP 变更记录 |

### 10.5 深色模式

- Naive UI 内建 dark theme 支持
- 用户偏好保存在 localStorage
- ECharts 图表同步切换深色配色

### 10.6 后台管理页

| 页面 | 功能 |
|---|---|
| 节点管理 | 节点列表（含协议支持状态：绿色=支持/灰色=不支持）、添加节点（自动生成 Token 和部署命令）、编辑标签、禁用/启用、删除 |
| 任务管理 | 任务列表、创建任务（选源节点→检查协议支持→选内部目标或填外部目标→选协议→设间隔→设告警阈值和窗口参数）、编辑、启用/禁用、删除 |
| 告警设置 | Webhook 通道管理（增删改测试发送）、告警历史记录查看 |
| 用户管理 | 用户列表、创建只读用户、提升/降级角色、删除用户 |
| 系统设置 | 页面标题/副标题自定义 |

---

## 11. 探测引擎（插件架构）

### 11.1 设计原则

探测引擎采用 **模块化插件架构**，每种协议是一个独立的 Python 模块。Network-Monitoring-Tools 的代码放在专用文件夹中，探测引擎通过统一接口调用。

### 11.2 插件接口定义

每个探测插件必须实现以下接口：

```python
# probes/base.py — 抽象基类

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ProbeResult:
    """统一的探测结果数据结构"""
    success: bool                    # 是否成功
    latency: Optional[float]         # 延迟 (ms)
    packet_loss: Optional[float]     # 丢包率 (%)
    jitter: Optional[float]          # 抖动 (ms)
    status_code: Optional[int]       # HTTP 状态码
    dns_time: Optional[float]        # DNS 解析时间 (ms)
    tcp_time: Optional[float]        # TCP 连接时间 (ms)
    tls_time: Optional[float]        # TLS 握手时间 (ms)
    ttfb: Optional[float]            # 首字节时间 (ms)
    total_time: Optional[float]      # 总响应时间 (ms)
    resolved_ip: Optional[str]       # 解析到的 IP
    error: Optional[str]             # 错误信息

class BaseProbe(ABC):
    """探测插件基类"""

    @abstractmethod
    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        """执行一次探测，返回结果"""
        pass

    @abstractmethod
    def protocol_name(self) -> str:
        """返回协议名称，如 'icmp', 'tcp', 'udp', 'http', 'dns'"""
        pass
```

### 11.3 插件注册与发现

```python
# probes/__init__.py — 自动发现并注册插件

PROBE_REGISTRY = {}

def register_probe(protocol: str, probe_class):
    PROBE_REGISTRY[protocol] = probe_class

def get_probe(protocol: str) -> BaseProbe:
    return PROBE_REGISTRY[protocol]()
```

### 11.4 集成 Network-Monitoring-Tools

```
agent/
├── probes/                      ← 探测插件目录
│   ├── __init__.py              ← 插件注册
│   ├── base.py                  ← 抽象基类
│   ├── icmp_probe.py            ← ICMP 探测（包装 network_tools 的实现）
│   ├── tcp_probe.py             ← TCP 探测
│   ├── udp_probe.py             ← UDP 探测
│   ├── http_probe.py            ← HTTP/HTTPS 探测
│   └── dns_probe.py             ← DNS 探测
├── network_tools/               ← Network-Monitoring-Tools 原始代码（独立文件夹）
│   ├── icmp_ping/
│   ├── tcp_ping/
│   ├── udp_ping/
│   ├── curl_ping/
│   └── dns_lookup/
└── ...
```

每个 `*_probe.py` 是一个 **适配器**，把 `network_tools/` 中对应模块的功能包装成统一的 `BaseProbe` 接口。

**新增协议的步骤**：
1. 在 `network_tools/` 下放入新协议的实现代码
2. 在 `probes/` 下新建一个 `xxx_probe.py`，继承 `BaseProbe`，调用 `network_tools/` 的代码
3. 在 `probes/__init__.py` 中注册
4. 完成——前端和后端自动识别新协议

### 11.5 能力发现机制

Agent 启动时自动检测当前环境支持哪些探测协议，检测结果在连接中心时通过 `capabilities` 字段上报。

#### 检测逻辑

Agent 启动后依次对每个已注册的探测插件执行一次**自检探测**（probe self-test），判断该协议在当前环境是否可用：

| 协议 | 自检方式 | 判定标准 |
|---|---|---|
| ICMP Ping | 尝试 `ping 127.0.0.1` | 命令可执行且返回成功 |
| TCP Ping | 检查 Python `socket` 模块可导入且 `socket.create_connection()` 可正常调用 | 模块可用且无运行时异常 |
| UDP Ping | 检查 `nc`（netcat）命令是否存在 | `which nc` 返回路径 |
| HTTP/HTTPS | 尝试 `curl --version` 或 Python requests 导入 | 命令可用或模块可导入 |
| DNS Lookup | 检查 `nslookup` 命令是否存在 | `which nslookup` 返回路径 |

#### 检测结果上报

```python
# capabilities 数据结构
{
    "protocols": ["icmp", "tcp", "http", "dns"],       # 支持的协议
    "unsupported": ["udp"],                             # 不支持的协议
    "unsupported_reasons": {
        "udp": "nc (netcat) not installed"              # 不支持的原因
    },
    "agent_version": "0.1.0",
    "os": "Ubuntu 22.04",
    "public_ip": "203.0.113.10",
    "private_ip": "10.0.1.5"
}
```

#### 中心端行为

1. 收到 capabilities 后存入 `nodes` 表的 `capabilities` 字段
2. 后台节点列表页展示每个节点支持的协议：**绿色** = 支持，**灰色** = 不支持（悬停显示原因）
3. 管理员创建任务时，如果选择的源节点不支持所选协议，显示**警告提示**（不阻止创建，但提醒）
4. Agent 每次重连时重新上报 capabilities（环境可能变化）

#### Agent 安装时自动安装依赖

Agent 的一键安装脚本和 Docker 镜像中，会**默认安装所有协议所需的系统依赖**，目标是在 Linux 三大发行版（Debian/Ubuntu、CentOS/RHEL、Alpine）上实现一个安装命令全协议启用：

**Debian / Ubuntu**：
```bash
apt-get update && apt-get install -y iputils-ping curl dnsutils netcat-openbsd
```

**CentOS / RHEL**：
```bash
yum install -y iputils curl bind-utils nmap-ncat
```

**Alpine**：
```bash
apk add --no-cache iputils curl bind-tools netcat-openbsd
```

**Docker 镜像（Dockerfile.agent）**：
```dockerfile
# 基于 python:3.12-slim (Debian)
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping curl dnsutils netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*
```

> **设计目标**：绝大多数情况下，Agent 安装后应该全部协议都是绿色（支持）。只有在极特殊环境（如容器内无法获取 ICMP 权限、精简 OS 缺少某些工具）下才会出现灰色（不支持）。

> ⚠️ **硬规则**：能力自检失败**不阻塞 Agent 启动**。某协议自检失败只影响 `capabilities` 上报结果（该协议归入 `unsupported`），Agent 仍然正常启动并执行其他已支持协议的探测任务。AI Agent 实现时不得将任何单个协议的自检失败当作启动失败处理。

### 11.6 操作系统支持范围 🆕

| 级别 | 系统 | 说明 |
|---|---|---|
| **正式支持** ✅ | Debian 11+、Ubuntu 20.04+ | 一键安装脚本 + Docker 全覆盖，CI 测试 |
| **正式支持** ✅ | CentOS 7+（含 Rocky Linux、AlmaLinux） | 一键安装脚本 + yum 依赖，CI 测试 |
| **正式支持** ✅ | Alpine 3.18+ | Docker 镜像常见基础系统，CI 测试 |
| **Docker 支持** ✅ | 基于 python:3.12-slim 的 Docker 容器 | Linux 宿主机上运行，推荐方式 |
| **不保证** ⚠️ | macOS | Python 探测脚本理论可运行，但 ICMP 可能需要 `sudo`、UDP 探测依赖 `nc`（需手动安装），不提供一键安装脚本，不做 CI 测试 |
| **不保证** ⚠️ | Windows（WSL2） | 通过 WSL2 的 Linux 环境可能可用，但不官方支持，不做测试 |
| **不支持** ❌ | Windows（原生） | 不提供 Agent，探测工具依赖 Linux 命令（ping/curl/dig/nc 参数格式不同） |
| **已知限制** ⚠️ | Docker Desktop（macOS/Windows） | 容器内 ICMP 可能不可用（Docker Desktop 的网络栈限制），UDP 探测也可能受限 |

> **初版目标**：确保 Linux 三大发行版 + Docker 模式完整可用。macOS/Windows 用户如需使用，可自行尝试但项目不保证兼容性，不受理相关 Issue。

---

## 12. 告警系统 ✏️

### 12.1 告警规则（窗口化评估）

每个探测任务可独立配置以下告警规则。告警采用**窗口化评估**而非单次触发，避免网络偶发抖动产生大量误报。

#### 规则类型

| 规则类型 | 判断方式 | 默认参数 |
|---|---|---|
| 延迟告警 | 最近 N 次探测中有 ≥ M 次延迟超过阈值 | N=5, M=3 |
| 丢包告警 | 最近 N 次探测中有 ≥ M 次丢包率超过阈值 | N=5, M=3 |
| 连续失败告警 | 连续 N 次探测完全失败（success=false） | N=5 |

#### 告警参数（每个任务独立配置，均有默认值）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `alert_latency_threshold` | NULL（不告警） | 延迟阈值（ms），设置后启用延迟告警 |
| `alert_loss_threshold` | NULL（不告警） | 丢包率阈值（%），设置后启用丢包告警 |
| `alert_fail_count` | NULL（不告警） | 连续失败次数，设置后启用连续失败告警 |
| `alert_eval_window` | 5 | 评估窗口大小：看最近 N 次探测结果 |
| `alert_trigger_count` | 3 | 触发阈值：窗口内 ≥ M 次超阈值才告警 |
| `alert_recovery_count` | 3 | 恢复阈值：连续 K 次正常才发恢复通知 |
| `alert_cooldown_seconds` | 300 | 冷却时间：同一任务同一规则 N 秒内不重复告警 |

#### 为什么用窗口化而不是单次触发？

单次触发的问题：网络抖一下（偶尔一个 ICMP 延迟突刺 500ms）就立刻告警，恢复后又发恢复通知。如果链路不稳定，会产生告警→恢复→告警→恢复的"告警风暴"，每一条都是噪音，运维人员很快就会开始忽略告警。

窗口化评估：最近 5 次探测中有 3 次超阈值才告警。这意味着：
- 偶尔 1 次突刺：不告警（5 次里只有 1 次，不够 3 次）
- 持续性劣化：告警（5 次里 3 次以上都超了，说明真有问题）
- 恢复确认：连续 3 次正常才发恢复，避免"好了一下又坏了"的误报

### 12.2 告警流程

```
探测结果到达中心
       │
       ▼
  判断是否为历史补传数据（timestamp 早于当前时间 60 秒以上）
       │
  ┌────┴────┐
  │ 是      │ 否（实时数据）
  │ 只入库  │
  │ 不告警  │
  └─────────┤
            ▼
  更新该任务的滑动评估窗口（最近 N 次结果）
       │
       ▼
  告警引擎评估 ──→ 窗口内未达触发阈值 → 跳过
       │
  窗口内 ≥ M 次超阈值
       │
       ▼
  检查当前告警状态 ──→ 已处于 alerting 且在冷却期内 → 跳过
       │
  需要告警（首次触发或冷却期已过）
       │
       ▼
  状态机转为 alerting
       │
       ▼
  记录告警历史（SQLite alert_history 表）
       │
       ▼
  遍历所有已启用的 Webhook 通道 → 发送 HTTP POST
       │
       ▼
  推送前端通知（Socket.IO dashboard:alert）

  ─── 恢复流程 ───

  告警状态为 alerting 时：
       │
       ▼
  连续 K 次探测结果正常
       │
       ▼
  状态机转为 normal
       │
       ▼
  发送恢复通知（Webhook + 前端）
       │
       ▼
  记录恢复事件到 alert_history
```

### 12.3 Webhook 通知格式

```json
{
  "event": "alert",
  "level": "critical",
  "task_name": "B → C (ICMP Ping)",
  "source_node": "节点 B",
  "target": "节点 C",
  "protocol": "icmp",
  "rule": "latency_threshold",
  "message": "延迟 235ms 超过阈值 100ms",
  "value": 235,
  "threshold": 100,
  "timestamp": "2026-03-23T10:15:30Z"
}
```

### 12.4 告警恢复通知

当之前处于告警状态的任务恢复正常时，也会发送恢复通知：

```json
{
  "event": "recovery",
  "task_name": "B → C (ICMP Ping)",
  "message": "延迟恢复正常 (当前 12ms，阈值 100ms)",
  "duration": "持续告警 5 分钟",
  "timestamp": "2026-03-23T10:20:30Z"
}
```

---

## 13. 部署方案

### 13.1 中心节点（Docker Compose）

**docker-compose.yml**：

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    container_name: ns-nginx
    ports:
      - "9191:80"           # Web 端口（可改）
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./web/dist:/usr/share/nginx/html:ro
    depends_on:
      - backend
    restart: always

  backend:
    build: .
    container_name: ns-center
    environment:
      - INFLUXDB_URL=http://influxdb:8086
      - INFLUXDB_TOKEN=${INFLUXDB_TOKEN}
      - INFLUXDB_ORG=networkstatus
      - INFLUXDB_BUCKET_RAW=raw
      - INFLUXDB_BUCKET_1M=agg_1m
      - INFLUXDB_BUCKET_1H=agg_1h
      - SECRET_KEY=${SECRET_KEY}
    volumes:
      - ./data:/app/data    # SQLite + 配置文件持久化
    depends_on:
      - influxdb
    restart: always

  influxdb:
    image: influxdb:2.7
    container_name: ns-influxdb
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=${INFLUXDB_PASSWORD}
      - DOCKER_INFLUXDB_INIT_ORG=networkstatus
      - DOCKER_INFLUXDB_INIT_BUCKET=raw
      - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=${INFLUXDB_TOKEN}
    volumes:
      - influxdb_data:/var/lib/influxdb2
    restart: always

volumes:
  influxdb_data:
```

**部署命令**：

```bash
git clone https://github.com/wingsrabbit/NetworkStatus-Rabbit.git
cd NetworkStatus-Rabbit

# 生成密钥（首次部署）
cp .env.example .env
# 编辑 .env 填入密码和 Token

docker compose up -d

# 创建第一个管理员
docker exec -it ns-center python manage.py create-admin --username=admin --password=你的密码
```

### 13.2 探测节点

#### Docker 部署

```bash
docker run -d --restart=always \
  --name ns-agent \
  --net=host \
  networkstatus-rabbit-agent \
  --server=中心节点IP \
  --port=9191 \
  --node-id=节点ID \
  --token=节点Token
```

#### 一键脚本部署（裸机）

管理员在后台添加节点后，系统自动生成部署命令：

```bash
curl -fsSL https://center-ip:9191/api/install-agent.sh | bash -s -- \
  --server=中心节点IP \
  --port=9191 \
  --node-id=自动生成的ID \
  --token=自动生成的Token
```

脚本自动完成：
1. 检查 Python 3.6+ 是否安装
2. 安装必要系统依赖（ping, curl, nslookup, nc）
3. 下载 Agent 代码
4. 创建 systemd 服务（Linux）或后台进程
5. 启动 Agent

> ✏️ **MVP 权衡说明**：初版为降低实现复杂度，接受节点 Token 通过命令行参数明文传入。这属于 MVP 权衡，不是默认最佳实践。初版不额外实现 Token 文件读取或密钥管理服务集成。后续可改进方向：`--token-file=/path/secret` 从文件读取、环境变量注入（`NS_AGENT_TOKEN`）、或对接 HashiCorp Vault 等密钥管理系统。
>
> ⚠️ **安全边界**：虽然允许命令行明文传入 Token，但 AI Agent 实现时**不得**将 Token 明文写入日志文件、不得在 API 响应中回显已存储的 Token、不得在前端 UI 中再次展示 Token（仅创建时返回一次）。

### 13.3 端口说明

| 端口 | 用途 | 必须 |
|---|---|---|
| 9191 | Web 页面 + API + WebSocket（Nginx 统一入口） | ✅ |

> 注意：只对外暴露一个端口。InfluxDB 8086 端口不对外暴露，仅 Docker 内部网络通信。

### 13.4 数据持久化

```
data/
├── networkstatus.db     # SQLite（用户、节点、任务、告警等配置数据）
└── backups/             # 自动备份目录

influxdb_data/           # Docker volume（InfluxDB 时序数据，由 Docker 管理）
```

---

## 14. 内部 API 设计 ✏️

> 注意：这是内部 API，仅供前端调用，**不对外开放**。

### 14.1 认证 API ✏️

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/api/auth/login` | 登录，成功后通过 Set-Cookie 写入 JWT（httpOnly） | 公开 |
| POST | `/api/auth/logout` | 登出，清除 Cookie | 已登录 |
| GET | `/api/auth/me` | 获取当前用户信息 | 已登录 |

### 14.2 节点管理 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/nodes` | 列出所有节点 | 已登录 |
| POST | `/api/nodes` | 添加节点 | admin |
| PUT | `/api/nodes/:id` | 编辑节点 | admin |
| DELETE | `/api/nodes/:id` | 删除节点 | admin |
| GET | `/api/nodes/:id/deploy-command` | 获取部署命令 | admin |

### 14.3 任务管理 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/tasks` | 列出所有任务 | 已登录 |
| POST | `/api/tasks` | 创建任务 | admin |
| PUT | `/api/tasks/:id` | 编辑任务 | admin |
| DELETE | `/api/tasks/:id` | 删除任务 | admin |
| PUT | `/api/tasks/:id/toggle` | 启用/禁用任务 | admin |

### 14.4 数据查询 API ✏️

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/data/dashboard` | Dashboard 总览数据（所有任务最新状态） | 已登录 |
| GET | `/api/data/task/:id?range=6h` | 指定任务的时序数据 | 已登录 |
| GET | `/api/data/task/:id/stats?range=24h` | 指定任务的统计摘要 | 已登录 |

#### Dashboard 筛选参数 🆕

`GET /api/data/dashboard` 支持以下可选查询参数，用于前端筛选/搜索：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `protocol` | string | 无 | 按探测协议筛选：`icmp` / `tcp` / `http` / `dns` |
| `label` | string | 无 | 按节点标签筛选（模糊匹配 `label_1` / `label_2` / `label_3` 任一字段） |
| `status` | string | 无 | 按节点状态筛选：`online` / `offline` |
| `alert_status` | string | 无 | 按告警状态筛选：`normal` / `alerting` |
| `search` | string | 无 | 关键词搜索（匹配 **任务名称** / **节点名称** / **目标地址**，大小写不敏感） |

> 多个参数可组合使用，后端以 AND 逻辑拼接。无参数时返回全量数据。筛选在后端执行（非前端过滤），确保大数据量时的性能。

#### Dashboard 默认排序规则 ✏️

| 数据类型 | 默认排序 | 说明 |
|---|---|---|
| `nodes` | `name` ASC | 节点按名称字母序 |
| `tasks` | `alert_status` DESC, `name` ASC | 告警中的任务置顶，其余按名称排序 |

> Dashboard 接口不支持前端传排序参数，固定使用以上规则。列表接口（`/api/nodes`、`/api/tasks` 等）的排序规则见“列表查询通用规则”。

### 14.5 用户管理 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/users` | 列出所有用户 | admin |
| POST | `/api/users` | 创建用户 | admin |
| PUT | `/api/users/:id/role` | 修改用户角色 | admin |
| DELETE | `/api/users/:id` | 删除用户 | admin |

### 14.6 告警 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/alerts/channels` | 列出告警通道 | admin |
| POST | `/api/alerts/channels` | 添加 Webhook 通道 | admin |
| PUT | `/api/alerts/channels/:id` | 编辑通道 | admin |
| DELETE | `/api/alerts/channels/:id` | 删除通道 | admin |
| POST | `/api/alerts/channels/:id/test` | 测试发送 | admin |
| GET | `/api/alerts/history` | 告警历史 | 已登录 |

### 14.7 系统设置 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/settings` | 获取系统设置 | admin |
| PUT | `/api/settings` | 更新系统设置 | admin |

### 14.8 Agent 安装脚本

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/install-agent.sh` | 返回 Agent 一键安装脚本 | 公开（脚本内不含敏感信息，Token 通过参数传入） |

### 14.9 统一错误响应规范 🆕

所有 REST API 的错误响应必须遵守以下规范，AI Agent 实现时**不得各模块自创格式**。

#### HTTP 错误码语义

| 状态码 | 语义 | 使用场景 |
|---|---|---|
| 400 | Bad Request | 请求体 JSON 格式错误、缺少必填字段、字段类型不对 |
| 401 | Unauthorized | 未登录（Cookie 中无 JWT / JWT 过期 / JWT 无效） |
| 403 | Forbidden | 已登录但权限不足（readonly 访问 admin 接口、admin 试图删除其他 admin） |
| 404 | Not Found | 资源不存在（节点 ID / 任务 ID / 用户 ID 找不到） |
| 409 | Conflict | 状态冲突（用户名已存在、试图删除最后一个 admin、节点名重复） |
| 422 | Unprocessable Entity | 请求格式正确但业务验证失败（间隔超出 1-60 范围、阈值为负数） |
| 429 | Too Many Requests | 登录被锁定（连续 10 次密码错误后 15 分钟内） |
| 500 | Internal Server Error | 服务端未预期的错误 |

#### 统一错误 JSON 格式

所有非 2xx 响应必须返回以下格式：

```json
{
  "error": {
    "code": 422,
    "type": "validation_error",
    "message": "探测间隔必须在 1-60 秒之间",
    "details": {
      "field": "interval",
      "value": 120,
      "constraint": "1 <= interval <= 60"
    }
  }
}
```

| 字段 | 类型 | 必须 | 说明 |
|---|---|---|---|
| `error.code` | int | ✅ | HTTP 状态码（与响应头一致） |
| `error.type` | string | ✅ | 错误类型标识：`auth_error` / `permission_error` / `not_found` / `conflict` / `validation_error` / `rate_limited` / `server_error` |
| `error.message` | string | ✅ | 人类可读的中文错误描述 |
| `error.details` | object | ❌ | 可选的额外信息（校验失败的字段、约束条件等） |

### 14.10 REST API 请求/响应示例 🆕

以下为核心接口的最小请求体和成功响应示例，AI Agent 实现时必须**严格遵循这些字段结构**。

#### `POST /api/auth/login`

请求体：
```json
{
  "username": "admin",
  "password": "your_password"
}
```

成功响应（200）：
```json
{
  "user": {
    "id": "uuid-xxx",
    "username": "admin",
    "role": "admin"
  }
}
```
> 注意：JWT Token 通过 `Set-Cookie` 响应头发送，**不在响应体中返回**。

#### `POST /api/nodes`

请求体：
```json
{
  "name": "东京节点",
  "label_1": "亚太",
  "label_2": "日本",
  "label_3": null
}
```
> `label_1` ~ `label_3` 均可选（可空）。

成功响应（201）：
```json
{
  "node": {
    "id": "node-uuid-1234",
    "name": "东京节点",
    "token": "raw-token-only-shown-once",
    "label_1": "亚太",
    "label_2": "日本",
    "label_3": null,
    "status": "registered",
    "enabled": true,
    "config_version": 0,
    "created_at": "2026-03-23T10:00:00Z"
  }
}
```
> `token` 明文**仅在创建时返回一次**，后续查询不再返回。

#### `PUT /api/nodes/:id`

请求体（部分更新，只发送需要修改的字段）：
```json
{
  "name": "东京节点-新名",
  "label_1": "亚太",
  "enabled": false
}
```

成功响应（200）：
```json
{
  "node": {
    "id": "node-uuid-1234",
    "name": "东京节点-新名",
    "label_1": "亚太",
    "label_2": "日本",
    "label_3": null,
    "status": "disabled",
    "enabled": false,
    "config_version": 0,
    "capabilities": { "protocols": ["icmp", "tcp", "http", "dns"], "unsupported": ["udp"] },
    "agent_version": "0.1.0",
    "public_ip": "203.0.113.10",
    "private_ip": "10.0.1.5",
    "last_seen": "2026-03-23T10:30:00Z",
    "created_at": "2026-03-23T10:00:00Z"
  }
}
```

#### `POST /api/tasks`

请求体：
```json
{
  "name": "B→C ICMP",
  "source_node_id": "node-b-uuid",
  "target_type": "internal",
  "target_node_id": "node-c-uuid",
  "target_address": null,
  "target_port": null,
  "protocol": "icmp",
  "interval": 5,
  "timeout": 10,
  "alert_latency_threshold": 100,
  "alert_loss_threshold": 10,
  "alert_fail_count": null,
  "alert_eval_window": 5,
  "alert_trigger_count": 3,
  "alert_recovery_count": 3,
  "alert_cooldown_seconds": 300
}
```
> `name` 可选。`target_node_id` 和 `target_address` 二选一（由 `target_type` 决定）。告警参数全部可选，不传则用默认值。

成功响应（201）：
```json
{
  "task": {
    "id": "task-uuid-5678",
    "name": "B→C ICMP",
    "source_node_id": "node-b-uuid",
    "target_type": "internal",
    "target_node_id": "node-c-uuid",
    "target_address": null,
    "target_port": null,
    "protocol": "icmp",
    "interval": 5,
    "timeout": 10,
    "enabled": true,
    "alert_latency_threshold": 100,
    "alert_loss_threshold": 10,
    "alert_fail_count": null,
    "alert_eval_window": 5,
    "alert_trigger_count": 3,
    "alert_recovery_count": 3,
    "alert_cooldown_seconds": 300,
    "created_at": "2026-03-23T11:00:00Z"
  }
}
```

#### `PUT /api/tasks/:id`

请求体（部分更新）：
```json
{
  "interval": 10,
  "alert_latency_threshold": 200
}
```

成功响应（200）：
```json
{
  "task": {
    "id": "task-uuid-5678",
    "name": "B→C ICMP",
    "source_node_id": "node-b-uuid",
    "target_type": "internal",
    "target_node_id": "node-c-uuid",
    "protocol": "icmp",
    "interval": 10,
    "timeout": 10,
    "enabled": true,
    "alert_latency_threshold": 200,
    "alert_loss_threshold": 10,
    "alert_fail_count": null,
    "alert_eval_window": 5,
    "alert_trigger_count": 3,
    "alert_recovery_count": 3,
    "alert_cooldown_seconds": 300,
    "created_at": "2026-03-23T11:00:00Z"
  }
}
```

#### `GET /api/data/dashboard`

无请求体。

成功响应（200）：
```json
{
  "nodes": [
    {
      "id": "node-b-uuid",
      "name": "东京节点",
      "status": "online",
      "labels": ["亚太", "日本", null],
      "capabilities": { "protocols": ["icmp", "tcp", "http", "dns"] },
      "last_seen": "2026-03-23T12:00:00Z"
    }
  ],
  "tasks": [
    {
      "task_id": "task-uuid-5678",
      "name": "B→C ICMP",
      "source_node": "东京节点",
      "target": "新加坡节点",
      "protocol": "icmp",
      "enabled": true,
      "latest": {
        "latency": 12.5,
        "packet_loss": 0,
        "jitter": 1.2,
        "success": true,
        "timestamp": "2026-03-23T12:00:05Z"
      },
      "alert_status": "normal"
    }
  ],
  "summary": {
    "total_nodes": 5,
    "online_nodes": 4,
    "offline_nodes": 1,
    "total_tasks": 20,
    "alerting_tasks": 1
  }
}
```

#### `PUT /api/users/:id/role` ✏️

> **高风险接口**：修改用户角色。仅 admin 可操作，受 9.6 权限硬规则表约束。

请求体：
```json
{
  "role": "admin"
}
```
> `role` 仅接受 `"admin"` 或 `"readonly"`。

成功响应（200）：
```json
{
  "user": {
    "id": "user-uuid-xxx",
    "username": "alice",
    "role": "admin",
    "created_at": "2026-03-20T08:00:00Z"
  }
}
```

错误响应示例：
```json
// 尝试降级 admin → 403
{
  "error": {
    "code": 403,
    "type": "permission_error",
    "message": "不允许通过 Web 降级 admin 角色"
  }
}

// 尝试修改自己 → 403
{
  "error": {
    "code": 403,
    "type": "permission_error",
    "message": "不允许修改自己的角色"
  }
}
```

#### `POST /api/alerts/channels` ✏️

> 创建告警通知通道（Webhook）。

请求体：
```json
{
  "name": "Discord 告警",
  "type": "webhook",
  "url": "https://discord.com/api/webhooks/xxx/yyy",
  "enabled": true
}
```
> `type` 初版仅支持 `"webhook"`。

成功响应（201）：
```json
{
  "channel": {
    "id": "channel-uuid-001",
    "name": "Discord 告警",
    "type": "webhook",
    "url": "https://discord.com/api/webhooks/xxx/yyy",
    "enabled": true,
    "created_at": "2026-03-23T13:00:00Z"
  }
}
```

#### `GET /api/alerts/history` ✏️

> 查询告警历史记录，支持筛选和分页。

请求示例：
```
GET /api/alerts/history?task_id=task-uuid-5678&event_type=alert&page=1&per_page=20
```

成功响应（200）：
```json
{
  "items": [
    {
      "id": "ah-uuid-001",
      "task_id": "task-uuid-5678",
      "task_name": "B→C ICMP",
      "event_type": "alert",
      "metric": "latency",
      "threshold": 100,
      "actual_value": 150.3,
      "message": "延迟超标: 150.3ms > 100ms (连续 3/5 窗口触发)",
      "notified": true,
      "created_at": "2026-03-23T12:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 42,
    "total_pages": 3
  }
}
```

> ✏️ **字段完整性说明**：以上示例展示的是**完整字段集合**（非最小子集）。后端返回时必须包含示例中的所有字段。如后续版本扩展新字段，在此处同步更新，前端至少依赖 `id`、`task_id`、`event_type`、`metric`、`actual_value`、`threshold`、`message`、`notified`、`created_at` 这些字段进行渲染。

#### `PUT /api/settings` ✏️

> **高风险接口**：修改全局系统设置。仅 admin 可操作。

请求体（部分更新）：
```json
{
  "data_retention_raw_days": 5,
  "default_probe_interval": 10
}
```

成功响应（200）：
```json
{
  "settings": {
    "data_retention_raw_days": 5,
    "data_retention_1m_days": 7,
    "data_retention_1h_days": 30,
    "default_probe_interval": 10,
    "default_probe_timeout": 10,
    "global_alert_cooldown": 300
  }
}
```

#### `PUT /api/tasks/:id/toggle` ✏️

> 启用/停用探测任务。独立接口，防止误操作（不与 PUT /api/tasks/:id 混用）。

请求体：
```json
{
  "enabled": false
}
```

成功响应（200）：
```json
{
  "task": {
    "id": "task-uuid-5678",
    "name": "B→C ICMP",
    "enabled": false
  }
}
```

#### 列表查询通用规则

所有 `GET` 列表接口（`/api/nodes`、`/api/tasks`、`/api/users`、`/api/alerts/history`）支持以下查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `page` | int | 1 | 页号（从 1 开始） |
| `per_page` | int | 50 | 每页条数（最大 100） |
| `sort` | string | `created_at` | 排序字段 |
| `order` | string | `desc` | 排序方向：`asc` / `desc` |

列表响应统一包裹在 `pagination` 元数据中：

```json
{
  "items": [ ... ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 128,
    "total_pages": 3
  }
}
```

> `/api/alerts/history` 额外支持 `?task_id=xxx` 和 `?event_type=alert|recovery` 筛选参数。

---

## 15. 目录结构

```
NetworkStatus-Rabbit/
├── docker-compose.yml           # Docker Compose 编排文件
├── Dockerfile                   # 中心节点后端镜像构建
├── Dockerfile.agent             # 探测节点镜像构建
├── .env.example                 # 环境变量模板
├── requirements.txt             # Python 依赖
├── manage.py                    # 管理命令（创建管理员等）
├── README.md                    # 项目说明
├── PROJECT.md                   # 本文档
│
├── server/                      # 中心节点后端代码
│   ├── __init__.py
│   ├── app.py                   # Flask 应用工厂
│   ├── config.py                # 配置加载
│   ├── extensions.py            # Flask 扩展初始化（Socket.IO, SQLAlchemy）
│   ├── models/                  # SQLAlchemy 数据模型
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── node.py
│   │   ├── task.py
│   │   └── alert.py
│   ├── api/                     # REST API 蓝图
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── nodes.py
│   │   ├── tasks.py
│   │   ├── data.py
│   │   ├── users.py
│   │   ├── alerts.py
│   │   └── settings.py
│   ├── ws/                      # Socket.IO 事件处理
│   │   ├── __init__.py
│   │   ├── agent_handler.py     # Agent 节点连接处理
│   │   └── dashboard_handler.py # 前端 Dashboard 实时推送
│   ├── services/                # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── influx_service.py    # InfluxDB 读写操作
│   │   ├── alert_service.py     # 告警引擎
│   │   ├── task_service.py      # 任务管理
│   │   └── node_service.py      # 节点管理
│   └── utils/                   # 工具函数
│       ├── __init__.py
│       ├── auth.py              # JWT 工具
│       └── webhook.py           # Webhook 发送
│
├── agent/                       # 探测节点代码
│   ├── __init__.py
│   ├── main.py                  # Agent 入口
│   ├── config.py                # Agent 配置
│   ├── ws_client.py             # WebSocket 客户端
│   ├── scheduler.py             # 任务调度器
│   ├── local_cache.py           # 本地 SQLite 缓存
│   ├── probes/                  # 探测插件（统一接口）
│   │   ├── __init__.py          # 插件注册与发现
│   │   ├── base.py              # 抽象基类 BaseProbe
│   │   ├── icmp_probe.py        # ICMP 探测适配器
│   │   ├── tcp_probe.py         # TCP 探测适配器
│   │   ├── udp_probe.py         # UDP 探测适配器
│   │   ├── http_probe.py        # HTTP/HTTPS 探测适配器
│   │   └── dns_probe.py         # DNS 探测适配器
│   └── network_tools/           # Network-Monitoring-Tools 原始代码
│       ├── icmp_ping/
│       │   ├── monitor_ping.py
│       │   └── analyze_network_log.py
│       ├── tcp_ping/
│       │   ├── monitor_tcp_ping.py
│       │   └── analyze_tcp_ping_log.py
│       ├── udp_ping/
│       │   ├── ping_udp.py
│       │   └── analyze_udp_ping_log.py
│       ├── curl_ping/
│       │   ├── monitor_curl.py
│       │   └── analyze_curl_log.py
│       └── dns_lookup/
│           ├── monitor_dns.py
│           └── analyze_dns_log.py
│
├── web/                         # 前端代码
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.ts              # 入口
│       ├── App.vue              # 根组件
│       ├── router/              # Vue Router
│       │   └── index.ts
│       ├── stores/              # Pinia 状态管理
│       │   ├── auth.ts
│       │   ├── dashboard.ts
│       │   └── theme.ts
│       ├── composables/         # 组合式函数
│       │   ├── useSocket.ts     # Socket.IO 连接
│       │   └── useECharts.ts    # ECharts 封装
│       ├── views/               # 页面
│       │   ├── LoginView.vue
│       │   ├── DashboardView.vue
│       │   ├── TaskDetailView.vue
│       │   ├── admin/
│       │   │   ├── NodesView.vue
│       │   │   ├── TasksView.vue
│       │   │   ├── AlertsView.vue
│       │   │   ├── UsersView.vue
│       │   │   └── SettingsView.vue
│       │   └── ...
│       ├── components/          # 通用组件
│       │   ├── ProbeChart.vue   # 探测数据图表（ECharts 封装）
│       │   ├── TimeRangePicker.vue  # 时间范围选择器
│       │   ├── StatusBadge.vue  # 状态指示灯
│       │   └── ...
│       └── types/               # TypeScript 类型定义
│           └── index.ts
│
├── nginx/                       # Nginx 配置
│   └── nginx.conf
│
├── scripts/                     # 脚本
│   ├── install-agent.sh         # Agent 一键安装脚本模板
│   └── setup-influxdb.py        # InfluxDB 初始化（Bucket、Task、Retention Policy）
│
└── data/                        # 持久化数据（git忽略）
    └── .gitkeep
```

---

## 16. 开发路线图 ✏️

### Phase 1：基础骨架（MVP）
- [ ] 项目初始化（目录结构、依赖安装、Docker Compose）
- [ ] SQLite 数据模型（用户、节点、任务、告警通道、告警历史）
- [ ] InfluxDB 初始化脚本（Bucket、Retention Policy、Downsampling Task）
- [ ] 管理员 CLI 命令（manage.py create-admin / remove-admin / reset-password）
- [ ] httpOnly Cookie + JWT 登录认证（SameSite=Strict）
- [ ] 统一错误响应格式（14.9 规范）
- [ ] 节点管理 API + 后台页面
- [ ] Agent WebSocket 连接 + 认证 + 心跳（每秒 1 次）
- [ ] 节点存活检测（120 秒滑动窗口，≤20 心跳 = 离线）
- [ ] Agent 能力发现机制（启动自检 + capabilities 上报）

### Phase 2：探测核心
- [ ] 探测插件基类 + ICMP 探测插件
- [ ] 任务管理 API + 后台页面（创建任务、选源/目标/协议/间隔/告警窗口参数）
- [ ] 任务版本同步机制（config_version + task_sync/task_ack）
- [ ] 任务下发（中心 → Agent）
- [ ] Agent 任务调度器 + 探测执行
- [ ] 探测数据上报（Agent → 中心 → InfluxDB）+ result_id 去重
- [ ] 实时数据 ACK 确认（center:result_ack）
- [ ] TCP / UDP / HTTP / DNS 探测插件
- [ ] Agent 自动安装系统依赖（Debian/CentOS/Alpine 全覆盖）

### Phase 3：前端展示
- [ ] Dashboard 总览页（表格 + 分组折叠 + 节流快照推送）
- [ ] 任务详情页（ECharts 时序图 + 时间范围切换 + 统计面板）
- [ ] 详情页订阅协议（subscribe_task / unsubscribe_task）
- [ ] 异常区间标记（图表上用 markArea 标注告警时段）
- [ ] 节点管理页协议支持状态展示（绿色/灰色）
- [ ] 深色模式
- [ ] 前端 Socket.IO 实时推送（快照 + 详情页订阅）

### Phase 4：告警 + 稳定性
- [ ] 窗口化告警引擎（延迟 / 丢包 / 连续失败，评估窗口 + 触发阈值 + 恢复阈值）
- [ ] 告警状态机（normal → alerting → recovering → normal）
- [ ] 告警冷却期
- [ ] 告警历史表完整读写（alert_history 字段按 6.3 定义）
- [ ] 历史补传数据告警抑制（timestamp > 60s 前的数据不触发告警）
- [ ] Webhook 通道管理 + 告警/恢复通知发送
- [ ] 告警历史记录查看
- [ ] Agent 本地缓存表（local_results 按 6.4 定义）+ 断线补传 + batch ACK
- [ ] Agent 一键安装脚本
- [ ] Agent Docker 镜像

### Phase 5：打磨
- [ ] 外部目标探测支持
- [ ] 自定义标签筛选
- [ ] 时间范围自定义选择器
- [ ] 系统设置（页面标题/副标题）
- [ ] 权限硬规则验证（9.6 规则表全覆盖）
- [ ] 安全加固（登录锁定、HTTPS 相关）
- [ ] AI 验收自测清单逐条验证（第 17 章）
- [ ] 完整测试 + 稳定性验证

---

## 17. AI 验收自测清单 🆕

> 本清单供 AI Agent 在完成开发后逐条自测，确保实现符合文档规格。每一条都可以通过代码审查或自动化测试验证。

### 节点管理

- [ ] 添加节点后，Token 明文仅在创建响应中返回一次，后续 GET 不再返回
- [ ] 节点 Token 以 bcrypt 哈希存储在 SQLite 中
- [ ] 节点认证（agent:auth）成功后，状态从 registered → online
- [ ] 120 秒窗口内心跳 ≤ 20 个时，节点状态变为 offline
- [ ] 节点从 offline 恢复到 online 后，自动触发断线补传流程
- [ ] 禁用节点后，WebSocket 连接被主动断开，所有相关任务停止执行

### 任务同步

- [ ] 管理员创建/修改/删除任务后，该节点的 config_version +1
- [ ] 节点收到任务变更事件后回复 agent:task_ack，版本号匹配才确认同步
- [ ] 30 秒内未收到 task_ack → 重试最多 3 次 → 标记 desync
- [ ] 节点断线重连后上报旧版本号 → 中心发送 center:task_sync 全量同步
- [ ] config_version 比中心大的异常场景 → 强制全量同步 + 记录警告日志

### 探测引擎

- [ ] 所有探测插件实现 BaseProbe 接口，返回统一的 ProbeResult 格式
- [ ] Agent 启动时执行能力自检，上报 capabilities JSON
- [ ] 不支持某协议的节点创建任务时，前端显示警告提示（不阻止创建）
- [ ] 探测间隔参数在 1-60 秒范围内，超出范围返回 422

### 数据上报与补传

- [ ] 每条探测结果携带全局唯一的 result_id
- [ ] 中心写入 InfluxDB 前检查 result_id 是否已存在（幂等写入）
- [ ] 中心确认入库后回复 center:result_ack { result_id }
- [ ] Agent 只删除已收到 ACK 的本地缓存数据
- [ ] 断线期间探测结果写入 local_results 表（ack_status = pending）
- [ ] 重连后补传使用 agent:probe_batch → 收到 center:batch_ack → 批量更新为 acked
- [ ] 本地缓存定时清理：acked 超过 3 天的记录每小时清理一次
- [ ] pending / sent 状态的记录不被清理

### 告警系统

- [ ] 告警采用窗口化评估（最近 N 次中 ≥ M 次超阈值），非单次触发
- [ ] 历史补传数据（timestamp 早于当前时间 60 秒以上）只入库不触发告警
- [ ] 同一任务同一规则在冷却期内不重复告警
- [ ] 连续 K 次正常后才发送恢复通知（而非一次正常就恢复）
- [ ] 告警事件写入 alert_history 表，包含完整字段（event_type/metric/actual_value/threshold…）
- [ ] 恢复事件也写入 alert_history，包含 duration_seconds

### 前端推送

- [ ] Dashboard 总览页每秒收到 1 次 probe_snapshot（节流推送），非逐条广播
- [ ] 进入任务详情页后发送 subscribe_task 订阅该任务的细粒度推送
- [ ] 离开详情页后发送 unsubscribe_task 取消订阅
- [ ] WebSocket 断开时后端自动清理该连接的所有订阅
- [ ] 节点状态变更和告警通知为即时推送（不节流）

### 认证与权限

- [ ] JWT Token 写入 httpOnly Cookie，响应体不包含 Token
- [ ] Cookie 设置 SameSite=Strict + Path=/
- [ ] admin 不能通过 Web 降级或删除其他 admin
- [ ] admin 不能删除自己或降级自己
- [ ] 系统始终保留至少 1 个 admin（CLI 也受此约束）
- [ ] readonly 用户访问 admin 接口返回 403
- [ ] 未登录访问 /api/* 返回 401
- [ ] 连续 10 次密码错误锁定 15 分钟，返回 429

### 错误响应

- [ ] 所有非 2xx 响应返回统一 JSON 格式：`{ error: { code, type, message, details? } }`
- [ ] 400/401/403/404/409/422/429/500 使用语义正确（按 14.9 规范）
- [ ] 列表接口统一返回 pagination 元数据

### 失败场景自测 🆕

> 以下测试确保系统在**异常输入和边界条件**下行为正确，而非仅验证正常流程。

#### WebSocket 鉴权失败

- [ ] 不携带 Cookie 的 Socket.IO 连接请求被拒绝（`connect_error`）
- [ ] 携带过期 JWT Cookie 的连接请求被拒绝
- [ ] 连接建立后 JWT 过期 → 收到 `WS_TOKEN_EXPIRED` 错误事件 → 5 秒后连接断开

#### 权限边界

- [ ] readonly 用户通过 API 尝试创建任务 → 403 + `permission_error`
- [ ] readonly 用户通过 API 尝试修改用户角色 → 403 + `permission_error`
- [ ] admin 通过 Web API 尝试降级另一个 admin → 403 + `permission_error`（附明确错误消息）
- [ ] admin 通过 Web API 尝试删除另一个 admin → 403 + `permission_error`
- [ ] 删除系统中最后一个 admin（含 CLI 场景） → 409 + `conflict`

#### 订阅异常

- [ ] 前端订阅不存在的 task_id → 收到 `WS_INVALID_SUBSCRIBE` 错误事件（连接不断开）
- [ ] 前端发送格式错误的订阅请求（缺少 task_id） → 收到 `WS_BAD_REQUEST`

#### Cookie 路径验证

- [ ] 登录后 `Set-Cookie` 的 `Path=/`（非 `/api`），确保 WebSocket 握手时 Cookie 被携带
- [ ] `SameSite=Strict` 确保跨站请求不携带 Cookie

#### 数据边界

- [ ] 探测间隔设为 0 或 61 → 422 + `validation_error`
- [ ] 创建任务时 `target_type=internal` 但 `target_node_id` 为空 → 422 + `validation_error`
- [ ] 创建任务时 `target_type=external` 但 `target_address` 为空 → 422 + `validation_error`

### 规格一致性自查 🆕

> 以下测试确保实现代码与文档规格在**格式和命名**上完全一致，避免"各模块照不同章节实现"的问题。

- [ ] REST API 所有错误响应均为 `{ error: { code: int, type: string, message: string, details?: object } }` 格式（与 14.9 一致），`code` 为 HTTP 数字码，`type` 为字符串业务类型
- [ ] WebSocket 错误事件 payload 为扁平 `{ code: string, message: string }` 格式（与 7.9 一致），`code` 带 `WS_` 前缀，**不使用** REST 的 `{error:{...}}` 包裹结构
- [ ] `alert_history` 表字段名与 `GET /api/alerts/history` 返回字段名完全一致（`metric` / `actual_value` / `notified`，非 `rule_type` / `value` / `webhook_sent`）

---

## 18. Future Features（远期功能） ✏️

以下功能不在初版范围内，作为后续迭代方向记录：

| Feature | 说明 | 优先级 |
|---|---|---|
| 📊 数据导出 | 导出 CSV / PDF 报告 | 中 |
| 📱 移动端适配 | 响应式布局，手机上可看 Dashboard | 中 |
| 🌐 英文版 | i18n 国际化，支持中英文切换 | 低 |
| 🔐 细粒度权限 | 只读用户只能看指定分组/标签的数据 | 低 |
| 📈 链路健康评分 | 综合延迟/丢包/抖动/失败率计算 0-100 分，Dashboard 可按评分排序 | 中 |
| 🔇 静默时段/维护窗口 | 支持设置"某任务维护中不告警"或"某时段只记录不通知" | 中 |
| 🔄 Dashboard 聚合推送 | 当任务规模超过数百条时，将节流推送升级为完整的聚合快照模式 | 低 |
| 📋 多视角看板 | 除按源节点分组外，支持按目标/协议/标签/异常优先级分组排序 | 低 |

---

## 附录 A：核心依赖清单

### 后端（Python）

| 包 | 版本 | 用途 |
|---|---|---|
| flask | ≥3.0 | Web 框架 |
| flask-socketio | ≥5.3 | Socket.IO 服务端 |
| flask-sqlalchemy | ≥3.1 | SQLite ORM |
| flask-jwt-extended | ≥4.6 | JWT 认证 |
| influxdb-client | ≥1.40 | InfluxDB 2.x 客户端 |
| python-socketio | ≥5.11 | Agent 端 Socket.IO 客户端 |
| bcrypt | ≥4.1 | 密码哈希 |
| requests | ≥2.31 | Webhook 发送 |
| psutil | ≥5.9 | Agent 系统信息 |
| apscheduler | ≥3.10 | Agent 任务调度 |
| eventlet | ≥0.36 | Flask-SocketIO 异步后端 |

### 前端（Node.js）

| 包 | 用途 |
|---|---|
| vue | ≥3.4 |
| vue-router | ≥4 |
| pinia | 状态管理 |
| naive-ui | UI 组件库 |
| echarts | 图表库 |
| socket.io-client | WebSocket 客户端 |
| axios | HTTP 请求 |
| vite | 构建工具 |
| typescript | 类型系统 |
| dayjs | 时间处理 |

### Docker 镜像

| 镜像 | 用途 |
|---|---|
| python:3.12-slim | 后端运行时 |
| node:18-slim | 前端构建（build stage） |
| nginx:alpine | 反向代理 + 静态文件服务 |
| influxdb:2.7 | 时序数据库 |

---

## 附录 B：环境变量说明

| 变量 | 说明 | 示例 |
|---|---|---|
| `SECRET_KEY` | Flask 密钥，用于 JWT 签名 | 随机 32 位字符串 |
| `INFLUXDB_TOKEN` | InfluxDB 管理 Token | 随机 64 位字符串 |
| `INFLUXDB_PASSWORD` | InfluxDB admin 密码 | 强密码 |
| `INFLUXDB_URL` | InfluxDB 连接地址 | `http://influxdb:8086`（Docker 内部） |
| `INFLUXDB_ORG` | InfluxDB 组织名 | `networkstatus` |

---

*文档结束。本文档将随项目开发持续更新。*
