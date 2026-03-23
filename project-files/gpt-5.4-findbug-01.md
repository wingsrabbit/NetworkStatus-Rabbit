# NetworkStatus-Rabbit 项目解读与 Bug 审查（GPT-5.4）

## 1. 项目主题理解

根据：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/prompt.md`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md`

这个项目的主题非常明确：它是一个 **分布式网络质量监控平台**，由中心端（Flask + Socket.IO + SQLite + InfluxDB）、Agent 端（多协议探测）和前端（Vue 3 + Naive UI + ECharts）组成，核心目标包括：

1. 管理节点与探测任务；
2. Agent 上报探测结果，中心写入 InfluxDB；
3. 前端展示 Dashboard、任务详情、告警历史；
4. 使用 WebSocket 做实时推送；
5. 使用窗口化告警规则避免误报；
6. 使用 Cookie + JWT 做统一认证。

我对仓库做了静态审查，并做了两项基础验证：

- 后端启动烟雾测试：`create_app()` 成功；
- 前端构建验证：`cd web && npm run build` **失败**，说明项目当前并非“只差一点没接好”，而是已经存在明确可复现的实现偏差。

---

## 2. 已验证到的直接问题

### 2.1 前端当前无法通过构建

**复现命令**

```bash
cd /home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web && npm run build
```

**实际错误**

- `web/src/views/admin/AlertChannelsView.vue:59`
- `web/src/views/admin/AlertChannelsView.vue:62`

TypeScript 报错：传给 `createAlertChannel()` / `updateAlertChannel()` 的 `type` 被推断为 `string`，但类型定义要求字面量 `'webhook'`。

**定位**

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/admin/AlertChannelsView.vue`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/types/index.ts`

**修改建议**

- 把 `form` 明确声明为带字面量类型的数据结构，或在 `data` 组装时显式写死 `type: 'webhook' as const`；
- 同时统一 AlertChannel 的前后端数据结构（见下文 3.1），否则即使过编译，页面也仍然跑不通。

---

## 3. 已确认的实现偏差 / Bug

## 3.1 告警通道（Alert Channels）前后端契约不一致，页面创建/编辑/列表都会出问题

### 证据

前端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/api/alerts.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/admin/AlertChannelsView.vue`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/types/index.ts`

后端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/api/alerts.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/models/alert.py`

### 具体问题

1. 前端 `getAlertChannels()` 期待返回 `{ channels: AlertChannel[] }`，但后端实际返回的是 `{ items: [...] }`；
2. 前端 `AlertChannel` 类型定义是：
   - `config: Record<string, any>`
   - 页面读取 `row.config?.url`
3. 后端模型和接口实际使用的是扁平字段：
   - `url`
   - 没有 `config`
4. 前端创建/更新时发送的是：

```ts
{
  name,
  type,
  config: { url },
  enabled
}
```

后端却读取：

```py
data.get('url')
```

这意味着前端即使点“创建成功流程”，后端也会因为读不到 `url` 而报校验错误。

### 修改建议

二选一，但必须统一到底：

- **方案 A（推荐）**：前端改成与后端一致，统一使用扁平 `url` 字段；
- **方案 B**：后端改为接受/返回 `config.url`，并同步修改模型与序列化。

目前仓库其他后端代码也在直接使用 `channel.url`，因此更建议走 **方案 A**。

---

## 3.2 Dashboard API 返回结构与前端 store 完全不匹配，首页会拿不到卡片数据

### 证据

前端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/api/data.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/stores/dashboard.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/DashboardView.vue`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/types/index.ts`

后端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/api/data.py`

### 具体问题

前端期待：

```ts
GET /data/dashboard -> { cards: DashboardCard[] }
```

并且 `DashboardCard` 需要这些字段：

- `task_name`
- `source_node_name`
- `source_node_status`
- `target_address`
- `latest`
- `alert_status`

后端实际返回：

```json
{
  "nodes": [...],
  "tasks": [...],
  "summary": {...}
}
```

而且 `tasks` 里的字段名也不同：

- 后端是 `name`
- 前端要的是 `task_name`
- 后端是 `source_node`
- 前端要的是 `source_node_name`
- 后端是 `target`
- 前端要的是 `target_address`

`dashboard.ts` 中又直接写：

```ts
cards.value = res.data.cards
```

这会让 Dashboard 首页天然拿不到数据。

### 修改建议

- 明确选择“后端输出 cards”或“前端接收 nodes/tasks/summary”其中一种；
- 如果按 `PROJECT.md` 的展示目标，建议后端直接返回前端可消费的 `cards` 结构，减少重复转换；
- 同时统一 `DashboardCard` 的字段命名。

---

## 3.3 任务详情页把 UUID 当成数字处理，详情请求和实时订阅都会错

### 证据

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/models/task.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/router/index.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/TaskDetailView.vue`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/api/data.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/types/index.ts`

### 具体问题

后端任务 ID 是 UUID 字符串：

```py
id = db.Column(db.String(36), primary_key=True, ...)
```

但前端详情页写的是：

```ts
const taskId = Number(route.params.id)
```

而且相关 API / store / 订阅函数也都把 `taskId` 当成 `number`。

结果：

1. 从 Dashboard 点进详情页时，路由参数实际是 UUID；
2. `Number(uuid)` 会得到 `NaN`；
3. 后续请求会变成 `/data/task/NaN`；
4. WebSocket 订阅与前端过滤条件也会跟着错。

### 修改建议

- 全部改为 `string` 类型；
- 包括：
  - `web/src/views/TaskDetailView.vue`
  - `web/src/api/data.ts`
  - `web/src/stores/dashboard.ts`
  - `web/src/composables/useSocket.ts`
  - `web/src/types/index.ts`

---

## 3.4 任务详情实时推送事件名对不上，订阅成功也收不到明细更新

### 证据

前端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/TaskDetailView.vue`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/composables/useSocket.ts`

后端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/ws/dashboard_handler.py`

### 具体问题

后端推送详情时发的是：

```py
socketio.emit('dashboard:task_detail', ...)
```

前端监听的却是：

```ts
socket.value?.on('dashboard:task_update', handleRealtimeUpdate)
```

`useSocket.ts` 里也监听的是 `dashboard:task_update`。

这意味着：

- 服务端正常推送；
- 前端永远不处理；
- 任务详情页“实时更新”功能实际失效。

### 修改建议

- 统一事件名为 `dashboard:task_detail`；
- 所有监听、解绑、store 更新逻辑一起改；
- 同时检查 Dashboard 首页要消费的是 `dashboard:probe_snapshot` 还是其他增量事件，不要再出现第二套命名。

---

## 3.5 前端发出的订阅事件名不符合规格，也与后端实现不一致

### 证据

规格：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md` 第 7 章明确写的是 `dashboard:subscribe_task` / `dashboard:unsubscribe_task`

前端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/composables/useSocket.ts`

后端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/ws/dashboard_handler.py`

### 具体问题

前端实际 emit：

```ts
socket.value?.emit('subscribe_task', { task_id })
socket.value?.emit('unsubscribe_task', { task_id })
```

而规格文档和后端代码注释都在使用带 `dashboard:` 前缀的命名体系。

即使不考虑 Flask-SocketIO 类方法对事件名的映射问题，这里至少已经发生了：

- **前端命名**
- **后端注释/设计命名**
- **规格文档命名**

三套并存，后期非常容易出现“看起来实现了，实际上监听不到”的问题。

### 修改建议

- 按 `PROJECT.md` 统一成 `dashboard:subscribe_task` / `dashboard:unsubscribe_task`；
- 如果类方法不能直接映射冒号事件，则应在服务端用显式注册方式绑定事件名，不要继续混用。

---

## 3.6 `connect_error` 读取方式偏离 PROJECT.md v1.5，前端无法按规范处理 WS 认证失败

### 证据

规格：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md:943-945`

前端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/composables/useSocket.ts`

后端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/ws/dashboard_handler.py`

### 具体问题

`PROJECT.md` v1.5 已明确要求：

```ts
if (err.data?.code === 'WS_AUTH_FAILED') { ... }
```

但前端目前只做了：

```ts
s.on('connect_error', (err: Error) => {
  console.error(err.message)
})
```

没有按文档读取 `err.data.code`，也没有做登录跳转或用户提示。

### 修改建议

- 前端统一读取 `err.data?.code`；
- 对 `WS_AUTH_FAILED` 执行跳转登录/清理状态；
- 不要再把 `err.message` 当业务判断依据。

---

## 3.7 告警引擎核心字段名与数据模型脱节，实时告警逻辑当前不可用

### 证据

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/models/task.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/services/alert_service.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md:481-487`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md:1446-1452`

### 具体问题

`ProbeTask` 模型定义的是：

- `alert_latency_threshold`
- `alert_loss_threshold`
- `alert_fail_count`
- `alert_eval_window`
- `alert_trigger_count`
- `alert_recovery_count`
- `alert_cooldown_seconds`

但 `alert_service.py` 却在读：

- `task.alert_enabled`
- `task.alert_metric`
- `task.alert_operator`
- `task.alert_threshold`

这些字段在 `ProbeTask` 上根本不存在。

因此 `agent_handler.py` 调用：

```py
process_probe_result(task_id, metrics)
```

时，会在 `evaluate_probe_result()` 内触发 `AttributeError`，然后被外层 `except` 吃掉并写日志。结果就是：

- 数据可以继续入库；
- 但告警实际上不会正常工作。

### 修改建议

- 彻底按 `PROJECT.md` 的字段定义重写 `alert_service.py`；
- 告警规则应分别支持：
  - 延迟阈值
  - 丢包阈值
  - 连续失败次数
- 不要再保留旧版单规则 `alert_metric + alert_operator + alert_threshold` 模式。

---

## 3.8 告警历史写入逻辑与模型再次脱节：会在真正触发时继续报错

### 证据

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/models/alert.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/services/alert_service.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/ws/dashboard_handler.py`

### 具体问题

`AlertHistory` 模型没有 `operator` 字段，但 `record_alert_event()` 在构造模型实例时传了：

```py
operator=alert_operator
```

这会直接抛出 `TypeError`。

另外，`push_alert()` 定义是：

```py
def push_alert(alert_data):
```

但 `alert_service.py` 调用时传了 4 个位置参数：

```py
push_alert(task_id, event_type, metric, actual_value)
```

这同样会报错。

### 修改建议

- `AlertHistory` 只传模型中真实存在的字段；
- 如果需要 operator，就先把模型、迁移、序列化全部补齐；
- `push_alert()` 的签名与调用方必须统一成一个明确的 payload dict。

---

## 3.9 告警事件值与规格不一致：文档要求 `alert/recovery`，实现却写成 `triggered/recovered`

### 证据

规格：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md:516`

实现：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/models/alert.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/services/alert_service.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/admin/AlertHistoryView.vue`

### 具体问题

文档定义：

- `alert`
- `recovery`

但服务端与前端页面实际在使用：

- `triggered`
- `recovered`

这会造成：

- API 过滤条件与文档不一致；
- 前端筛选值与服务端文档约定不一致；
- 告警历史数据格式偏离项目规格。

### 修改建议

- 统一事件枚举；
- 推荐按 `PROJECT.md` 修回 `alert` / `recovery`；
- 同步修复后端写入、前端筛选、类型定义和文档示例。

---

## 3.10 result_id 去重只写在文档里，中心端实际没有真正执行幂等检查

### 证据

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md:749-752`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/services/influx_service.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/ws/agent_handler.py`

### 具体问题

规格要求：

1. 每条数据带 `result_id`；
2. 写入 InfluxDB 前检查是否已存在；
3. 已存在则跳过写入但仍 ACK。

当前代码中：

- `agent/ws_client.py` 已经生成 `result_id`；
- 但 `server/ws/agent_handler.py` 写入 InfluxDB 时根本没有把 `result_id` 纳入点数据；
- `InfluxService.check_result_exists()` 只是一个直接 `return False` 的 stub；
- `on_agent_probe_result()` / `on_agent_probe_batch()` 也没有真的做去重判定。

这意味着断线补传时，仍然可能写入重复数据。

### 修改建议

- 把 `result_id` 存入 InfluxDB（Tag 或 Field，需统一查询策略）；
- 在写入前真实查询是否存在；
- 或者使用单独幂等表保存已确认的 `result_id`；
- 无论是否重复，中心都应返回 ACK。

---

## 3.11 任务同步状态机缺失“pending / desync / 重试”实现，和规格不一致

### 证据

规格：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md:1041-1045`

实现：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/ws/agent_handler.py`

### 具体问题

代码里虽然有 `_task_ack_pending = {}`，但实际上：

- 没有把待确认任务真正放进去；
- 没有 30 秒超时重试；
- 没有最多 3 次后标记 desync；
- 也没有与节点状态机联动。

也就是说，目前只有“发送任务变化”和“收到 ACK 就 pop”这两个片段，**缺了状态机本体**。

### 修改建议

- 实现 `pending -> synced / desync` 的状态流转；
- 后台定时检查未 ACK 的 config_version；
- 超时重发，最多 3 次；
- 超过次数后标记 desync，并在节点重连时强制 `center:task_sync`。

---

## 3.12 任务管理页使用的是另一套“旧告警模型”，与后端当前接口不兼容

### 证据

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/admin/TasksView.vue`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/types/index.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/api/tasks.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/models/task.py`

### 具体问题

前端任务表单还在使用：

- `alert_enabled`
- `alert_metric`
- `alert_operator`
- `alert_threshold`
- `target_type = 'node' | 'external'`

但后端实际接受的是：

- `alert_latency_threshold`
- `alert_loss_threshold`
- `alert_fail_count`
- `target_type = 'internal' | 'external'`

这说明任务管理页面和后端不是同一版协议，导致：

1. 目标类型值就已经对不上；
2. 告警配置字段也完全对不上；
3. 前端“告警开关”并不能正确映射到后端的数据模型。

### 修改建议

- 按 `PROJECT.md` 彻底重做任务表单字段；
- 告警配置应分别配置延迟、丢包、连续失败；
- `target_type` 统一改为 `internal` / `external`；
- 相关 TS 类型一并修正。

---

## 3.13 用户管理页仍保留 `operator` 角色，但 `PROJECT.md` 当前规格已经没有这个角色

### 证据

规格：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md:1053-1056`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/project-files/PROJECT.md:2055`

前端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/types/index.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/stores/auth.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/admin/UsersView.vue`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/router/index.ts`

后端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/models/user.py`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/api/users.py`

### 具体问题

`PROJECT.md` 当前版只定义了：

- `admin`
- `readonly`

但前端仍然保留了 `operator`：

- 类型里有；
- `isOperator` 逻辑里有；
- 路由权限 `requiresOperator` 在用；
- 用户管理下拉框也提供“操作员”选项。

后端却明确拒绝非 `admin` / `readonly` 角色。

结果是：

- 前端权限模型与后端权限模型不一致；
- 管理员在 UI 中可以选一个后端不接受的角色；
- 路由守卫逻辑也建立在不存在的角色上。

### 修改建议

- 如果以当前 `PROJECT.md` 为准，就应彻底删除 `operator`；
- 如果要保留 `operator`，必须先修规格文档，再同步改后端模型/API/权限规则。

当前任务应以文档为准，因此建议 **移除前端 operator 残留**。

---

## 3.14 多个管理页都把 UUID 当 number / 把分页结构当平铺结构，运行时会出现一串连锁问题

### 证据

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/types/index.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/api/tasks.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/api/users.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/api/alerts.ts`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/admin/TasksView.vue`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/admin/UsersView.vue`
- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/admin/AlertHistoryView.vue`

### 具体问题

后端模型里大量主键都是 UUID 字符串，但前端类型里写成了：

- `User.id: number`
- `ProbeTask.id: number`
- `AlertChannel.id: number`
- `AlertHistory.task_id: number`

同时多个列表页都在读：

```ts
total.value = res.data.total
```

但后端统一返回的是：

```json
{
  "items": [...],
  "pagination": {
    "total": ...
  }
}
```

这会导致：

- 删除 / 更新 URL 拼接使用错误的 id 类型；
- 列表总数、分页器显示错误；
- 某些页面虽然能渲染部分数据，但交互时会失败。

### 修改建议

- 全部主键类型统一改为 `string`；
- 为后端分页响应单独定义正确的 TS 类型；
- 不要再把 `pagination.total` 当成 `res.data.total`。

---

## 3.15 节点部署命令接口与前端展示字段不一致

### 证据

前端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web/src/views/admin/NodesView.vue`

后端：

- `/home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/server/api/nodes.py`

### 具体问题

前端读取：

```ts
deployCommand.value = res.data.command
```

但后端返回的是：

- `script_command`
- `docker_command`
- `node_id`

没有 `command` 字段。

### 修改建议

- 前端改成分别展示脚本安装命令和 Docker 命令；
- 或后端补一个 `command` 字段，但这会损失信息，不如前端改造更合理。

---

## 4. 总结：目前最关键的偏离点

如果只看“主题是否跑偏”，答案是：

- **没有跑偏到别的产品方向**，它仍然是网络质量监控平台；
- **但实现层面已经明显出现“前后端协议分叉、旧版设计残留、规格与代码不同步”的问题**。

最严重的问题不是某一个函数写错，而是以下三类系统性问题：

1. **前后端接口契约大面积不一致**
   - Dashboard
   - Alert Channels
   - Tasks
   - Users
   - 分页结构
   - UUID 类型

2. **实时链路事件名不一致**
   - 订阅事件
   - 详情推送事件
   - `connect_error` 读取方式

3. **告警系统处于“字段模型已换、业务代码没换完”的半完成状态**
   - `alert_service.py` 读取不存在字段
   - `AlertHistory` 写入参数不匹配
   - push_alert 调用签名不匹配
   - 事件枚举与规格不一致

---

## 5. 建议修复顺序（按收益排序）

1. **先统一前后端数据契约**
   - Dashboard
   - Alert Channels
   - 分页结构
   - UUID 类型

2. **再统一 WebSocket 事件命名**
   - `dashboard:subscribe_task`
   - `dashboard:unsubscribe_task`
   - `dashboard:task_detail`
   - `connect_error.data.code`

3. **然后重做告警链路**
   - 按 `PROJECT.md` 的阈值字段重写 `alert_service.py`
   - 修复 `AlertHistory` 模型/写入/推送 payload
   - 统一 `alert` / `recovery` 枚举

4. **最后补协议完整性**
   - result_id 去重
   - task_ack 重试 / desync 状态机

如果按这个顺序修，项目会从“很多页面看起来已经有了，但实际跑不通”转回“接口稳定、页面可交互、告警可闭环”的状态。
