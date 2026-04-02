# NetworkStatus-Rabbit Data Project

> 实现级规格文档。
> 字段模型、协议 payload、状态机、权限硬规则、API 示例、验收清单和部署细节统一放在这里。
> 项目背景和人类阅读版见 [Project-human.md](Project-human.md)。

---

## 1. 数据模型与存储策略

### 1.1 InfluxDB 数据模型

#### Measurement：`probe_result`

| 字段类型 | 名称 | 说明 |
|---|---|---|
| Tag | `task_id` | 探测任务 ID |
| Tag | `source_node` | 源节点 ID |
| Tag | `target` | 目标（节点 ID 或外部地址） |
| Tag | `protocol` | 协议（icmp / tcp / udp / http / dns） |
| Field | `latency` | 延迟（ms），float |
| Field | `packet_loss` | 丢包率（%），float，ICMP/UDP 使用 |
| Field | `jitter` | 抖动（ms），float，ICMP 使用 |
| Field | `success` | 是否成功，bool |
| Field | `status_code` | HTTP 状态码，int，HTTP 专用 |
| Field | `dns_time` | DNS 解析时间（ms），float，HTTP/DNS 使用 |
| Field | `tcp_time` | TCP 连接时间（ms），float，HTTP/TCP 使用 |
| Field | `tls_time` | TLS 握手时间（ms），float，HTTP 使用 |
| Field | `ttfb` | 首字节时间（ms），float，HTTP 使用 |
| Field | `total_time` | 总响应时间（ms），float，HTTP 使用 |
| Field | `resolved_ip` | 解析结果 IP，string，DNS 使用 |
| Timestamp | 自动 | 纳秒精度时间戳 |

约束说明：

- `task_id`、`source_node`、`target`、`protocol` 为 Tag，用于过滤和分组
- 数值型指标全部作为 Field，供聚合计算使用
- `target` 的离散值规模预期不超过 200；若未来增长到数千级，需要重新评估高基数风险

### 1.2 三级存储与降采样策略

| Bucket | 保留时间 | 粒度 |
|---|---|---|
| `raw` | 3 天 | 原始探测数据 |
| `agg_1m` | 7 天 | 每分钟聚合 |
| `agg_1h` | 30 天 | 每小时聚合 |

自动任务规则：

- 每 1 分钟：`raw` 聚合写入 `agg_1m`
- 每 1 小时：`agg_1m` 聚合写入 `agg_1h`

聚合字段至少包含：

- `avg_latency`
- `max_latency`
- `min_latency`
- `p95_latency`
- `avg_packet_loss`

前端时间范围与 Bucket 对应关系：

| 时间范围 | Bucket | 说明 |
|---|---|---|
| 6h / 12h / 24h | `raw` | 原始展示 |
| 3d / 7d | `agg_1m` | 分钟级趋势 |
| 14d / 30d | `agg_1h` | 小时级趋势 |

### 1.3 SQLite 配置数据模型

#### 表：`nodes`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 节点唯一 ID |
| `name` | TEXT | 节点显示名称 |
| `token` | TEXT | 连接认证 Token，bcrypt 哈希存储 |
| `label_1` | TEXT | 自定义标签 1，可空 |
| `label_2` | TEXT | 自定义标签 2，可空 |
| `label_3` | TEXT | 自定义标签 3，可空 |
| `status` | TEXT | `registered` / `online` / `offline` / `disabled` |
| `last_seen` | DATETIME | 最后心跳时间 |
| `created_at` | DATETIME | 注册时间 |
| `enabled` | BOOLEAN | 是否启用 |
| `config_version` | INT | 当前任务配置版本号，默认 0 |
| `capabilities` | TEXT (JSON) | Agent 上报的能力信息 |
| `agent_version` | TEXT | Agent 版本号 |
| `public_ip` | TEXT | Agent 上报公网 IP |
| `private_ip` | TEXT | Agent 上报内网 IP |

#### 表：`probe_tasks`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 任务 ID |
| `name` | TEXT | 任务名称，可选 |
| `source_node_id` | TEXT (FK) | 源节点 ID |
| `target_type` | TEXT | `internal` / `external` |
| `target_node_id` | TEXT (FK) | 内部目标节点 ID |
| `target_address` | TEXT | 外部目标地址 |
| `target_port` | INT | 目标端口 |
| `protocol` | TEXT | `icmp` / `tcp` / `udp` / `http` / `dns` |
| `interval` | INT | 探测间隔，1-60 秒 |
| `timeout` | INT | 超时时间，秒 |
| `enabled` | BOOLEAN | 是否启用 |
| `created_at` | DATETIME | 创建时间 |
| `alert_latency_threshold` | FLOAT | 延迟阈值，NULL 表示不告警 |
| `alert_loss_threshold` | FLOAT | 丢包率阈值，NULL 表示不告警 |
| `alert_fail_count` | INT | 连续失败阈值，NULL 表示不告警 |
| `alert_eval_window` | INT | 评估窗口大小，默认 5 |
| `alert_trigger_count` | INT | 触发阈值，默认 3 |
| `alert_recovery_count` | INT | 恢复阈值，默认 3 |
| `alert_cooldown_seconds` | INT | 冷却时间，默认 300 |

#### 表：`users`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 用户 ID |
| `username` | TEXT | 用户名 |
| `password_hash` | TEXT | bcrypt 哈希 |
| `role` | TEXT | `admin` / `readonly` |
| `created_at` | DATETIME | 创建时间 |
| `created_by` | TEXT | 创建者 |

#### 表：`alert_channels`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 通道 ID |
| `name` | TEXT | 通道名称 |
| `type` | TEXT | 初版仅 `webhook` |
| `url` | TEXT | Webhook 地址 |
| `enabled` | BOOLEAN | 是否启用 |

#### 表：`alert_history`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT (UUID) | 告警事件 ID |
| `task_id` | TEXT (FK) | 关联任务 |
| `event_type` | TEXT | `alert` / `recovery` |
| `metric` | TEXT | `latency` / `packet_loss` / `continuous_fail` |
| `actual_value` | FLOAT | 触发时实际值 |
| `threshold` | FLOAT | 规则阈值 |
| `message` | TEXT | 人类可读描述 |
| `alert_started_at` | DATETIME | 告警开始时间 |
| `duration_seconds` | INT | 仅 recovery 事件填写 |
| `notified` | BOOLEAN | 通知是否成功发送 |
| `created_at` | DATETIME | 创建时间 |

去重规则：同一 `(task_id, metric)` 在 `alerting` 状态且冷却期内，不重复写入 `alert_history`。

#### 表：`settings`

| 列 | 类型 | 说明 |
|---|---|---|
| `key` | TEXT (PK) | 设置项键名 |
| `value` | TEXT | JSON 序列化值 |

### 1.4 Agent 本地缓存数据模型

#### 表：`local_results`

| 列 | 类型 | 说明 |
|---|---|---|
| `result_id` | TEXT (PK) | 全局唯一结果 ID |
| `task_id` | TEXT | 关联任务 |
| `payload_json` | TEXT | 完整探测结果 JSON |
| `ack_status` | TEXT | `pending` / `sent` / `acked` |
| `batch_id` | TEXT | 补传批次 ID |
| `retry_count` | INT | 重试次数 |
| `created_at` | DATETIME | 探测时间 |
| `sent_at` | DATETIME | 最近发送时间 |
| `acked_at` | DATETIME | 收到 ACK 的时间 |

生命周期：

1. 探测完成后写入 `local_results`，状态为 `pending`
2. 实时发送后改为 `sent`
3. 收到 `center:result_ack` 后改为 `acked`
4. 断线重连时补传所有非 `acked` 数据
5. 收到 `center:batch_ack` 后批量更新为 `acked`

清理规则：

- 每小时删除 `acked_at < now - 3天` 的记录
- `pending` 和 `sent` 状态永不清理，直到收到 ACK

---

## 2. 通信协议设计

### 2.1 Socket.IO 事件定义

#### 节点到中心

| 事件名 | 说明 | 数据结构 |
|---|---|---|
| `agent:auth` | 节点连接后认证 | `{ node_id, token, config_version, capabilities }` |
| `agent:heartbeat` | 每秒心跳 | `{ node_id, seq }` |
| `agent:probe_result` | 单条探测结果 | `{ result_id, task_id, timestamp, protocol, metrics }` |
| `agent:probe_batch` | 批量补传 | `{ batch_id, results: [...] }` |
| `agent:task_ack` | 任务同步确认 | `{ config_version }` |

#### 中心到节点

| 事件名 | 说明 | 数据结构 |
|---|---|---|
| `center:auth_result` | 认证结果 | `{ success, message }` |
| `center:task_assign` | 新任务下发 | `{ task_id, ..., config_version }` |
| `center:task_update` | 任务更新 | `{ task_id, changes, config_version }` |
| `center:task_remove` | 删除任务 | `{ task_id, config_version }` |
| `center:task_sync` | 全量同步 | `{ config_version, tasks: [...] }` |
| `center:batch_ack` | 批量补传确认 | `{ batch_id, accepted_ids }` |
| `center:result_ack` | 单条确认 | `{ result_id }` |

### 2.2 关键 JSON 示例

#### `agent:auth`

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

#### `agent:probe_result`

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

`result_id` 规则：`{node_id}-{unix_timestamp_ms}-{protocol}-{seq}`。

#### `agent:probe_batch`

```json
{
  "batch_id": "batch-node-b-1711153000",
  "results": [
    {
      "result_id": "node-b-1711152000-icmp-001",
      "task_id": "task-uuid-5678",
      "timestamp": "2026-03-23T09:00:00.000Z",
      "protocol": "icmp",
      "metrics": {
        "success": true,
        "latency": 15.3,
        "packet_loss": 0.0,
        "jitter": 0.8,
        "error": null
      }
    }
  ]
}
```

#### `center:task_sync`

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
    }
  ]
}
```

#### `dashboard:probe_snapshot`

```json
{
  "timestamp": "2026-03-23T10:15:31.000Z",
  "tasks": {
    "task-uuid-5678": {
      "last_latency": 12.5,
      "last_packet_loss": 0.0,
      "last_success": true,
      "status": "normal"
    }
  }
}
```

### 2.3 连接生命周期

1. Agent 连接 Socket.IO 服务
2. 发送 `agent:auth`
3. Center 返回 `center:auth_result`
4. 如 `config_version` 落后，Center 发送 `center:task_sync`
5. Agent 应用后回 `agent:task_ack`
6. Agent 检查本地未 ACK 数据，必要时发送 `agent:probe_batch`
7. Center 回 `center:batch_ack`
8. Agent 开始探测，逐条发送 `agent:probe_result`
9. Center 回 `center:result_ack`
10. Agent 每秒发送心跳

### 2.4 断线补传协议

#### 幂等写入

- 每条结果必须带 `result_id`
- Center 入库前按 `result_id` 去重
- 重复结果跳过写入，但仍返回 ACK

#### ACK 规则

- 实时结果使用 `center:result_ack`
- 批量补传使用 `center:batch_ack`
- Agent 只有在收到 ACK 后才把记录标记为已确认

#### 历史数据告警抑制

- `timestamp` 早于当前时间超过 60 秒的数据视为历史补传
- 历史补传数据只入库，不参与实时告警评估

### 2.5 节点存活检测

规则：

- Agent 每秒发送 `agent:heartbeat { node_id, seq }`
- Center 维护每节点最近 120 秒窗口

判定表：

| 条件 | 结果 |
|---|---|
| 120 秒内收到 21 个及以上心跳 | `online` |
| 120 秒内收到 20 个及以下心跳 | `offline` |

### 2.6 任务版本同步

规则：

1. Center 为每个节点维护整数型 `config_version`
2. 任务增删改时，该节点版本号加 1
3. 所有变更事件都携带最新 `config_version`
4. Agent 应用后发送 `agent:task_ack { config_version }`
5. 重连时：
   - 节点版本小于中心版本，发送全量同步
   - 节点版本等于中心版本，不发送同步
   - 节点版本大于中心版本，强制全量同步并记录警告日志

### 2.7 前端实时推送

| 事件名 | 方向 | 说明 |
|---|---|---|
| `dashboard:node_status` | 后端到前端 | 节点状态变更，即时推送 |
| `dashboard:probe_snapshot` | 后端到前端 | 所有任务最新聚合快照，每秒一次 |
| `dashboard:alert` | 后端到前端 | 告警通知，即时推送 |
| `dashboard:task_detail` | 后端到前端 | 仅详情页订阅时推送 |

### 2.8 详情页订阅协议

| 事件名 | 方向 | 数据结构 |
|---|---|---|
| `dashboard:subscribe_task` | 前端到后端 | `{ task_id }` |
| `dashboard:unsubscribe_task` | 前端到后端 | `{ task_id }` |
| `dashboard:task_detail` | 后端到前端 | `{ task_id, result }` |

`dashboard:task_detail` 示例：

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

生命周期规则：

- 一个连接可以同时订阅多个任务
- 离开详情页必须发送取消订阅
- 连接断开时服务端自动清理所有 room
- 订阅不影响总览快照推送

### 2.9 WebSocket 错误事件规范

格式说明：

- WS 错误 payload 使用扁平结构 `{ code, message }`
- `code` 为字符串业务码，带 `WS_` 前缀
- 不复用 REST 的 `{ error: { ... } }` 包裹结构

标准错误：

| 错误码 | 场景 | 后端处理 | 前端处理 |
|---|---|---|---|
| `WS_AUTH_FAILED` | 握手时 Cookie 无效或缺失 | 拒绝连接 | 跳转登录 |
| `WS_TOKEN_EXPIRED` | 已连接后 JWT 过期 | 发送错误，5 秒后断开 | 尝试刷新，失败则跳转登录 |
| `WS_PERMISSION_DENIED` | 无权限操作 | 发送错误，不断开 | 显示提示 |
| `WS_INVALID_SUBSCRIBE` | 订阅非法任务 | 发送错误，不断开 | 显示提示 |
| `WS_BAD_REQUEST` | 参数格式错误 | 发送错误，不断开 | 开发期日志输出 |

连接失败与连接后错误的区别：

- 握手失败通过 `connect_error` 传递，业务码读取 `err.data.code`
- 已建立连接后的业务错误通过 `error` 事件传递

前端监听示例：

```typescript
const socket = io({
  withCredentials: true,
});

socket.on('connect_error', (err) => {
  if (err.data?.code === 'WS_AUTH_FAILED') {
    router.push('/login');
  }
});

socket.on('error', (payload: { code: string; message: string }) => {
  if (payload.code === 'WS_PERMISSION_DENIED') {
    notification.warning({ content: payload.message });
  }
});
```

---

## 3. 核心状态机

### 3.1 节点状态机

| 当前状态 | 条件 | 下一个状态 | 系统行为 |
|---|---|---|---|
| `registered` | 首次 `agent:auth` 成功 | `online` | 记录 capabilities，开始收心跳 |
| `online` | 120 秒窗口心跳 ≤ 20 | `offline` | 触发离线通知，更新 Dashboard |
| `offline` | 重连成功且心跳恢复 | `online` | 触发恢复通知，开始补传 |
| `online` / `offline` | 管理员禁用节点 | `disabled` | 断开连接，停止任务 |
| `disabled` | 管理员重新启用 | `registered` | 等待再次连接 |

### 3.2 告警状态机

| 当前状态 | 条件 | 下一个状态 | 系统行为 |
|---|---|---|---|
| `normal` | 窗口内触发次数达到阈值 | `alerting` | 发送告警，写告警历史 |
| `alerting` | 冷却期内再次超阈值 | `alerting` | 不重复发送 |
| `alerting` | 冷却期后再次超阈值 | `alerting` | 再次发送告警 |
| `alerting` | 连续恢复次数达标 | `recovering` | 发送恢复通知 |
| `recovering` | 自动结束 | `normal` | 回到正常 |

### 3.3 任务同步状态机

| 当前状态 | 条件 | 下一个状态 | 系统行为 |
|---|---|---|---|
| `synced` | 管理员修改任务 | `pending` | 版本号加 1，下发变更 |
| `pending` | 收到匹配版本 `task_ack` | `synced` | 确认成功 |
| `pending` | 节点断线 | `desync` | 等待重连 |
| `desync` | 节点带旧版本重连 | `pending` | 发送全量同步 |
| `pending` | 30 秒未收到确认 | `pending` 或 `desync` | 最多重试 3 次，失败后记为 `desync` |

---

## 4. 认证与权限模型

### 4.1 角色定义

| 角色 | 权限 |
|---|---|
| `admin` | 节点、任务、告警、用户、系统设置全部可管理 |
| `readonly` | 只能查看 Dashboard、详情图表和告警历史 |

### 4.2 管理员管理

规则：

- 管理员之间平级，没有超级管理员
- Web 界面禁止删除其他 admin
- Web 界面禁止降级其他 admin
- admin 相关身份操作统一通过 CLI 兜底

CLI 命令：

```bash
docker exec -it ns-center python manage.py create-admin --username=admin1 --password=xxx
docker exec -it ns-center python manage.py remove-admin --username=admin1
docker exec -it ns-center python manage.py reset-password --username=admin1
```

### 4.3 只读用户

- 由 admin 在后台创建
- 可查看全部数据
- 初版不做数据隔离

### 4.4 节点认证

- 节点创建时由系统生成 Token
- 节点连接时使用 `node_id + token` 认证
- Token 在数据库中仅存 bcrypt 哈希

### 4.5 登录安全

- 登录成功后通过 `Set-Cookie` 写入 JWT
- Cookie 属性：`HttpOnly`、`SameSite=Strict`、`Path=/`
- 生产环境开启 HTTPS 时同时启用 `Secure`
- 前端不手动保存 Token，不使用 localStorage
- WebSocket 握手与 REST 请求共用 Cookie
- 连续 10 次密码错误锁定 15 分钟

### 4.6 权限硬规则表

| # | 主体 | 操作 | 允许/禁止 |
|---|---|---|---|
| 1 | admin | 通过 Web 降级其他 admin | 禁止 |
| 2 | admin | 通过 Web 删除其他 admin | 禁止 |
| 3 | admin | 删除自己 | 禁止 |
| 4 | admin | 降级自己 | 禁止 |
| 5 | admin | 提升 readonly 为 admin | 允许 |
| 6 | admin | 创建 readonly 用户 | 允许 |
| 7 | admin | 删除 readonly 用户 | 允许 |
| 8 | readonly | 任何写操作 | 禁止 |
| 9 | 系统 | 删除最后一个 admin | 禁止 |
| 10 | CLI | 添加、删除、降级 admin | 允许，但受规则 9 约束 |
| 11 | 未登录用户 | 访问任意 `/api/*`（登录除外） | 禁止 |
| 12 | readonly | 访问 `/admin/*` 页面 | 禁止 |

---

## 5. 前端详细规格

### 5.1 页面结构

| 路由 | 说明 |
|---|---|
| `/` | 登录页 |
| `/dashboard` | 总览页 |
| `/dashboard/:taskId` | 任务详情页 |
| `/admin/nodes` | 节点管理 |
| `/admin/tasks` | 任务管理 |
| `/admin/alerts` | 告警设置 |
| `/admin/users` | 用户管理 |
| `/admin/settings` | 系统设置 |

### 5.2 Dashboard 总览页

要求：

- 按源节点分组展示任务
- 支持折叠分组
- 支持协议、标签、状态、搜索筛选
- 表格字段至少包含：任务名、目标、协议、延迟、丢包、状态、详情入口
- 状态灯颜色：正常、警告、异常、离线

### 5.3 任务详情页

要求：

- 支持 6h、12h、24h、3d、7d、14d、30d、自定义时间
- 图表支持 dataZoom 和 tooltip
- 图表支持 markArea 标注异常区间
- 统计面板展示平均值、最大值、最小值、P95、可用率等指标

### 5.4 各协议图表映射

| 协议 | 图表 1 | 图表 2 | 图表 3 |
|---|---|---|---|
| ICMP | 延迟折线图 | 丢包率柱状图 | 抖动折线图 |
| TCP | 连接延迟折线图 | 连接成功率柱状图 | 无 |
| UDP | 延迟折线图 | 丢包率柱状图 | 无 |
| HTTP/HTTPS | 总响应时间折线图 | 分段耗时堆叠图 | 状态码散点图 |
| DNS | 解析时间折线图 | 成功率柱状图 | 无 |

### 5.5 深色模式

- Naive UI 内建 dark theme
- 用户偏好保存在 localStorage
- ECharts 配色同步切换

### 5.6 后台管理页

| 页面 | 功能 |
|---|---|
| 节点管理 | 节点列表、标签编辑、禁用/启用、删除、部署命令、协议支持状态 |
| 任务管理 | 创建、编辑、启用/禁用、删除、协议兼容性提醒 |
| 告警设置 | Webhook 通道管理、告警历史 |
| 用户管理 | 创建只读用户、角色调整、删除用户 |
| 系统设置 | 页面标题、副标题等全局配置 |

---

## 6. 探测引擎详细规格

### 6.1 设计原则

- 每种协议一个独立插件
- 所有插件返回统一结果结构
- 新协议接入只扩展插件层，不改调度主框架

### 6.2 插件接口定义

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ProbeResult:
    success: bool
    latency: Optional[float]
    packet_loss: Optional[float]
    jitter: Optional[float]
    status_code: Optional[int]
    dns_time: Optional[float]
    tcp_time: Optional[float]
    tls_time: Optional[float]
    ttfb: Optional[float]
    total_time: Optional[float]
    resolved_ip: Optional[str]
    error: Optional[str]

class BaseProbe(ABC):
    @abstractmethod
    def probe(self, target: str, port: int = None, timeout: int = 10) -> ProbeResult:
        pass

    @abstractmethod
    def protocol_name(self) -> str:
        pass
```

### 6.3 插件注册与发现

```python
PROBE_REGISTRY = {}

def register_probe(protocol: str, probe_class):
    PROBE_REGISTRY[protocol] = probe_class

def get_probe(protocol: str):
    return PROBE_REGISTRY[protocol]()
```

### 6.4 集成目录结构

```text
agent/
├── probes/
│   ├── __init__.py
│   ├── base.py
│   ├── icmp_probe.py
│   ├── tcp_probe.py
│   ├── udp_probe.py
│   ├── http_probe.py
│   └── dns_probe.py
├── network_tools/
│   ├── icmp_ping/
│   ├── tcp_ping/
│   ├── udp_ping/
│   ├── curl_ping/
│   └── dns_lookup/
└── ...
```

### 6.5 能力发现机制

#### 自检规则

| 协议 | 自检方式 | 判定标准 |
|---|---|---|
| ICMP | 执行 `ping 127.0.0.1` | 命令可执行且成功 |
| TCP | 检查 Python `socket` 模块和 `socket.create_connection()` | 可用且无运行时异常 |
| UDP | 检查 `nc` 是否存在 | 返回可执行路径 |
| HTTP/HTTPS | `curl --version` 或导入 requests | 命令可用或模块可导入 |
| DNS | 检查 `nslookup` 是否存在 | 返回可执行路径 |

上报结构：

```json
{
  "protocols": ["icmp", "tcp", "http", "dns"],
  "unsupported": ["udp"],
  "unsupported_reasons": {
    "udp": "nc (netcat) not installed"
  },
  "agent_version": "0.1.0",
  "os": "Ubuntu 22.04",
  "public_ip": "203.0.113.10",
  "private_ip": "10.0.1.5"
}
```

Center 行为：

1. 保存到 `nodes.capabilities`
2. 节点列表页展示支持与不支持状态
3. 创建任务时对不支持协议给出提醒，但不阻止创建
4. Agent 每次重连重新上报

默认依赖安装：

```bash
apt-get update && apt-get install -y iputils-ping curl dnsutils netcat-openbsd
yum install -y iputils curl bind-utils nmap-ncat
apk add --no-cache iputils curl bind-tools netcat-openbsd
```

硬规则：单个协议自检失败不得阻塞 Agent 启动。

### 6.6 操作系统支持范围

| 级别 | 系统 | 说明 |
|---|---|---|
| 正式支持 | Debian 11+、Ubuntu 20.04+ | 一键安装和 Docker 全覆盖 |
| 正式支持 | CentOS 7+、Rocky、Alma | 提供 yum 依赖方案 |
| 正式支持 | Alpine 3.18+ | Docker 常用基础系统 |
| Docker 支持 | `python:3.12-slim` 容器 | 推荐方式 |
| 不保证 | macOS | 不提供一键安装，不做 CI |
| 不保证 | Windows WSL2 | 可自行尝试 |
| 不支持 | Windows 原生 | 不提供 Agent |

---

## 7. 告警系统详细规格

### 7.1 告警规则与参数

| 规则类型 | 判断方式 | 默认参数 |
|---|---|---|
| 延迟告警 | 最近 N 次中有至少 M 次延迟超阈值 | N=5, M=3 |
| 丢包告警 | 最近 N 次中有至少 M 次丢包超阈值 | N=5, M=3 |
| 连续失败告警 | 连续 N 次 `success=false` | N=5 |

默认参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `alert_eval_window` | 5 | 评估窗口 |
| `alert_trigger_count` | 3 | 触发次数阈值 |
| `alert_recovery_count` | 3 | 恢复次数阈值 |
| `alert_cooldown_seconds` | 300 | 冷却时间 |

### 7.2 告警流程

1. Center 收到探测结果
2. 先判断是否为历史补传数据
3. 如为实时数据，更新该任务最近窗口
4. 根据规则评估是否进入 `alerting`
5. 如符合条件，写 `alert_history`
6. 对所有启用的通道发送通知
7. 同时推送前端实时告警
8. 恢复时写 recovery 记录并发送恢复通知

### 7.3 Webhook 通知格式

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

### 7.4 恢复通知格式

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

## 8. 部署详细规格

### 8.1 Center Docker Compose

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    container_name: ns-nginx
    ports:
      - "9191:80"
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
      - ./data:/app/data
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

### 8.2 Agent 部署方式

Docker 方式：

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

一键脚本方式：

```bash
curl -fsSL https://center-ip:9191/api/install-agent.sh | bash -s -- \
  --server=中心节点IP \
  --port=9191 \
  --node-id=自动生成的ID \
  --token=自动生成的Token
```

### 8.3 端口说明

| 端口 | 用途 | 必须 |
|---|---|---|
| 9191 | Web 页面、API、WebSocket 统一入口 | 是 |

### 8.4 数据持久化

```text
data/
├── networkstatus.db
└── backups/

influxdb_data/
```

安全边界：Token 允许作为 MVP 阶段命令行参数传入，但不得写入日志，不得在后续 API 和 UI 中回显。

---

## 9. 内部 API 设计

### 9.1 认证 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/api/auth/login` | 登录并写入 Cookie | 公开 |
| POST | `/api/auth/logout` | 登出并清 Cookie | 已登录 |
| GET | `/api/auth/me` | 当前用户信息 | 已登录 |

### 9.2 节点管理 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/nodes` | 节点列表 | 已登录 |
| POST | `/api/nodes` | 创建节点 | admin |
| PUT | `/api/nodes/:id` | 编辑节点 | admin |
| DELETE | `/api/nodes/:id` | 删除节点 | admin |
| GET | `/api/nodes/:id/deploy-command` | 获取部署命令 | admin |

### 9.3 任务管理 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/tasks` | 任务列表 | 已登录 |
| POST | `/api/tasks` | 创建任务 | admin |
| PUT | `/api/tasks/:id` | 编辑任务 | admin |
| DELETE | `/api/tasks/:id` | 删除任务 | admin |
| PUT | `/api/tasks/:id/toggle` | 启停任务 | admin |

### 9.4 数据查询 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/data/dashboard` | Dashboard 总览 | 已登录 |
| GET | `/api/data/task/:id?range=6h` | 任务时序数据 | 已登录 |
| GET | `/api/data/task/:id/stats?range=24h` | 任务统计摘要 | 已登录 |

Dashboard 过滤参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `protocol` | string | 按协议筛选 |
| `label` | string | 按节点标签筛选 |
| `status` | string | 按节点状态筛选 |
| `alert_status` | string | 按告警状态筛选 |
| `search` | string | 匹配任务名、节点名、目标地址 |

固定排序：

- 节点：`name ASC`
- 任务：`alert_status DESC, name ASC`

### 9.5 用户管理 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/users` | 用户列表 | admin |
| POST | `/api/users` | 创建用户 | admin |
| PUT | `/api/users/:id/role` | 调整角色 | admin |
| DELETE | `/api/users/:id` | 删除用户 | admin |

### 9.6 告警 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/alerts/channels` | 通道列表 | admin |
| POST | `/api/alerts/channels` | 创建通道 | admin |
| PUT | `/api/alerts/channels/:id` | 编辑通道 | admin |
| DELETE | `/api/alerts/channels/:id` | 删除通道 | admin |
| POST | `/api/alerts/channels/:id/test` | 测试发送 | admin |
| GET | `/api/alerts/history` | 告警历史 | 已登录 |

### 9.7 系统设置 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/settings` | 获取设置 | admin |
| PUT | `/api/settings` | 更新设置 | admin |

### 9.8 Agent 安装脚本 API

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| GET | `/api/install-agent.sh` | 返回安装脚本 | 公开 |

### 9.9 统一错误响应规范

HTTP 状态码语义：

| 状态码 | 语义 |
|---|---|
| 400 | 请求格式错误 |
| 401 | 未登录或 Token 无效 |
| 403 | 已登录但无权限 |
| 404 | 资源不存在 |
| 409 | 状态冲突 |
| 422 | 业务校验失败 |
| 429 | 频率限制或登录锁定 |
| 500 | 服务端异常 |

统一格式：

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

### 9.10 REST API 示例

#### `POST /api/auth/login`

请求体：

```json
{
  "username": "admin",
  "password": "your_password"
}
```

成功响应：

```json
{
  "user": {
    "id": "uuid-xxx",
    "username": "admin",
    "role": "admin"
  }
}
```

#### `POST /api/nodes`

```json
{
  "name": "东京节点",
  "label_1": "亚太",
  "label_2": "日本",
  "label_3": null
}
```

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

#### `PUT /api/nodes/:id`

```json
{
  "name": "东京节点-新名",
  "label_1": "亚太",
  "enabled": false
}
```

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

```json
{
  "interval": 10,
  "alert_latency_threshold": 200
}
```

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

#### `PUT /api/users/:id/role`

```json
{
  "role": "admin"
}
```

成功响应：

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

错误响应：

```json
{
  "error": {
    "code": 403,
    "type": "permission_error",
    "message": "不允许通过 Web 降级 admin 角色"
  }
}
```

#### `POST /api/alerts/channels`

```json
{
  "name": "Discord 告警",
  "type": "webhook",
  "url": "https://discord.com/api/webhooks/xxx/yyy",
  "enabled": true
}
```

#### `GET /api/alerts/history`

请求示例：

```text
GET /api/alerts/history?task_id=task-uuid-5678&event_type=alert&page=1&per_page=20
```

成功响应：

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

#### 列表查询通用规则

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `page` | int | 1 | 页号 |
| `per_page` | int | 50 | 每页条数，最大 100 |
| `sort` | string | `created_at` | 排序字段 |
| `order` | string | `desc` | `asc` / `desc` |

列表响应统一结构：

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 128,
    "total_pages": 3
  }
}
```

---

## 10. 目录结构

```text
NetworkStatus-Rabbit/
├── docker-compose.yml
├── Dockerfile
├── Dockerfile.agent
├── .env.example
├── requirements.txt
├── manage.py
├── README.md
├── PROJECT.md
├── server/
│   ├── app.py
│   ├── config.py
│   ├── extensions.py
│   ├── models/
│   ├── api/
│   ├── ws/
│   ├── services/
│   └── utils/
├── agent/
│   ├── main.py
│   ├── config.py
│   ├── ws_client.py
│   ├── scheduler.py
│   ├── local_cache.py
│   ├── probes/
│   └── network_tools/
├── web/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
├── nginx/
├── scripts/
└── data/
```

---

## 11. AI 验收自测清单

### 11.1 节点管理

- 添加节点后，Token 明文只在创建响应中返回一次
- 节点 Token 在 SQLite 中使用 bcrypt 哈希存储
- `agent:auth` 成功后，节点状态从 `registered` 进入 `online`
- 120 秒窗口心跳不达标时转为 `offline`
- 节点恢复后自动触发补传
- 禁用节点后主动断开连接并停止相关任务

### 11.2 任务同步

- 任务变更后对应节点 `config_version + 1`
- 节点收到变更后必须回 `agent:task_ack`
- 30 秒未收到确认，最多重试 3 次
- 重连后旧版本节点收到全量同步
- 节点版本大于中心版本时强制全量同步并记录警告

### 11.3 探测引擎

- 所有插件实现 `BaseProbe`
- Agent 启动时执行能力发现并上报
- 节点不支持协议时，前端只提示，不阻止任务创建
- 探测间隔超出 1-60 秒返回 422

### 11.4 数据上报与补传

- 每条结果有唯一 `result_id`
- Center 写入前按 `result_id` 去重
- 入库后返回 `center:result_ack`
- Agent 只删除收到 ACK 的缓存
- 断线期间结果写入 `local_results`
- 重连后按批次补传并处理 `center:batch_ack`
- `acked` 超过 3 天的数据定时清理
- `pending` 和 `sent` 不参与清理

### 11.5 告警系统

- 告警采用窗口化评估
- 历史补传数据不触发告警
- 冷却期内不重复通知
- 连续恢复次数达标后才发送恢复
- alert 和 recovery 都写入 `alert_history`

### 11.6 前端推送

- Dashboard 总览每秒收到一次快照
- 详情页进入时发送订阅，离开时取消订阅
- WebSocket 断开时清理所有订阅
- 节点状态变更和告警为即时推送

### 11.7 认证与权限

- JWT 只放在 httpOnly Cookie 中
- Cookie 属性包含 `SameSite=Strict` 和 `Path=/`
- admin 不能通过 Web 删除或降级其他 admin
- admin 不能删除或降级自己
- 系统始终保留至少 1 个 admin
- readonly 访问管理接口返回 403
- 未登录访问 `/api/*` 返回 401
- 连续 10 次密码错误锁定 15 分钟并返回 429

### 11.8 错误响应

- 所有非 2xx 响应遵守统一错误格式
- 400 / 401 / 403 / 404 / 409 / 422 / 429 / 500 语义正确
- 列表接口统一带 `pagination`

### 11.9 失败场景

- 无 Cookie 的 Socket.IO 握手必须失败
- 过期 JWT 握手失败，已连接后过期需发送 `WS_TOKEN_EXPIRED`
- readonly 尝试写操作返回 403 + `permission_error`
- 删除最后一个 admin 返回 409 + `conflict`
- 订阅不存在任务返回 `WS_INVALID_SUBSCRIBE`
- 缺少 `task_id` 的订阅请求返回 `WS_BAD_REQUEST`
- 登录后 Cookie `Path` 必须为 `/`
- 非法间隔、非法目标参数返回 422 + `validation_error`

### 11.10 规格一致性

- REST 错误使用 `{ error: { code, type, message, details? } }`
- WS 错误使用 `{ code, message }`
- `alert_history` 字段名与告警历史 API 返回字段名保持一致

---

## 12. 附录 A：核心依赖清单

### 12.1 后端依赖

| 包 | 用途 |
|---|---|
| flask | Web 框架 |
| flask-socketio | Socket.IO 服务端 |
| flask-sqlalchemy | SQLite ORM |
| flask-jwt-extended | JWT 认证 |
| influxdb-client | InfluxDB 客户端 |
| python-socketio | Agent 端 Socket.IO |
| bcrypt | 哈希 |
| requests | Webhook |
| psutil | 系统信息 |
| apscheduler | 任务调度 |
| eventlet | Socket.IO 异步后端 |

### 12.2 前端依赖

| 包 | 用途 |
|---|---|
| vue | 前端框架 |
| vue-router | 路由 |
| pinia | 状态管理 |
| naive-ui | 组件库 |
| echarts | 图表 |
| socket.io-client | WebSocket 客户端 |
| axios | HTTP 请求 |
| vite | 构建工具 |
| typescript | 类型系统 |
| dayjs | 时间处理 |

### 12.3 Docker 镜像

| 镜像 | 用途 |
|---|---|
| `python:3.12-slim` | 后端运行时 |
| `node:18-slim` | 前端构建 |
| `nginx:alpine` | 静态文件和反向代理 |
| `influxdb:2.7` | 时序数据库 |

---

## 13. 附录 B：环境变量说明

| 变量 | 说明 | 示例 |
|---|---|---|
| `SECRET_KEY` | Flask 密钥，用于 JWT 签名 | 随机 32 位字符串 |
| `INFLUXDB_TOKEN` | InfluxDB 管理 Token | 随机 64 位字符串 |
| `INFLUXDB_PASSWORD` | InfluxDB 管理密码 | 强密码 |
| `INFLUXDB_URL` | InfluxDB 连接地址 | `http://influxdb:8086` |
| `INFLUXDB_ORG` | InfluxDB 组织名 | `networkstatus` |