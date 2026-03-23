# NetworkStatus-Rabbit 审查报告（基于当前仓库代码）

审查时间：2026-03-23  
审查基准：

1. `project-files/PROJECT.md`
2. `project-files/prompt.md`
3. 当前仓库实现

---

## 一、先说结论

### 1. 项目主题没有跑偏

当前仓库仍然是围绕 **网络质量监控** 在实现，没有发现明显偏向 CPU / 内存 / 磁盘 / 系统负载监控的核心功能。主线仍然是：

1. 中心节点 + Agent 架构
2. 节点间/节点到外部目标的网络探测
3. InfluxDB 时序存储
4. Dashboard / Task Detail 展示
5. WebSocket 实时推送
6. 告警与补传

也就是说，**主要问题不是“题做偏了”**，而是 **“很多功能已经搭了骨架，但没有严格落到 `PROJECT.md` 定义的契约上”**。

### 2. 已做的验证

已实际执行：

1. `cd /home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit/web && npm run build` ✅ 通过
2. `cd /home/runner/work/NetworkStatus-Rabbit/NetworkStatus-Rabbit && python -m compileall server agent manage.py` ✅ 通过
3. 仓库内未发现成体系的现成测试文件/测试命令

这说明当前代码 **能编译/能前端构建**，但不代表功能已符合规格。

---

## 二、已确认的偏离/BUG（按优先级排序）

## BUG-01：`result_id` 去重没有真正实现，幂等写入失效

### 证据

1. `server/services/influx_service.py:82-89` 中 `check_result_exists()` 直接 `return False`
2. `server/ws/agent_handler.py:144-159`、`207-224` 写入前没有调用有效的去重检查
3. `PROJECT.md:747-758` 明确要求中心端写入前检查 `result_id`，重复时跳过写入但仍 ACK

### 影响

断线补传、网络抖动重发时，同一条结果可能重复写入 InfluxDB。  
这会直接破坏：

1. 时序数据准确性
2. 统计值准确性
3. 告警判断准确性

### 修改意见

1. 在中心端真正实现 `result_id` 幂等检查
2. 单条上报和批量补传都必须走同一套去重逻辑
3. 对重复数据应“跳过写入 + 仍返回 ACK”，不要让 Agent 无限重传

---

## BUG-02：Dashboard REST 接口没有按规格返回真实总览数据

### 证据

1. `server/api/data.py:69-82` 中每张卡片的 `latest` 被固定写成 `None`
2. `server/api/data.py:81` 把 `alert_status` 固定写成 `'normal'`
3. `server/api/data.py:97` 把 `summary.alerting_tasks` 固定写成 `0`
4. `server/api/data.py:21` 虽然读取了 `alert_status` 查询参数，但后续完全没有使用
5. `PROJECT.md:1725-1744` 要求 Dashboard 支持 `alert_status` 筛选，并按 `alert_status DESC, name ASC` 排序
6. `PROJECT.md:2000-2042` 示例响应是 `{ nodes, tasks, summary }`，而当前接口返回 `{ cards, summary }`

### 影响

Dashboard 首屏拿不到真实的：

1. 最新延迟/丢包
2. 当前告警状态
3. 告警任务数量
4. `alert_status` 筛选结果

这会让“总览页”失去最核心的监控意义。

### 修改意见

1. 后端接口返回值与 `PROJECT.md` 契约统一
2. 为每个任务补充真实 `latest` 数据
3. `alert_status` 不能固定为 `normal`
4. `alert_status` 筛选和默认排序要真正生效

---

## BUG-03：Dashboard 实时总览链路实际是断的

### 证据

1. `server/app.py:145-169` 每秒推送 `dashboard:probe_snapshot`，但内容是占位值：
   - `last_latency: None`
   - `last_packet_loss: None`
   - `last_success: None`
   - `status: 'normal'`
2. `web/src/composables/useSocket.ts` 没有监听 `dashboard:probe_snapshot`
3. `server/ws/dashboard_handler.py:84-90` 的 `dashboard:task_detail` 只推给订阅了 `task:{task_id}` 房间的用户
4. `web/src/composables/useSocket.ts:32-37` 却试图在 Dashboard store 里靠 `dashboard:task_detail` 更新卡片

### 影响

这会造成两个直接后果：

1. 总览页不会按规格消费“每秒聚合快照”
2. 总览页也拿不到详情页专用房间推送

结果就是：**Dashboard 的实时刷新基本不成立**。

### 修改意见

1. 后端 `dashboard:probe_snapshot` 必须推送真实快照，不要推占位值
2. 前端 Dashboard 必须监听并消费 `dashboard:probe_snapshot`
3. `dashboard:task_detail` 仅保留给详情页订阅场景，不要再混作总览页实时来源

---

## BUG-04：告警算法没有实现“窗口化判断”，`alert_eval_window` 实际未生效

### 证据

1. `server/services/alert_service.py:45-65` 使用的是连续 breach / 连续 OK 计数
2. `server/services/alert_service.py` 中没有真正使用 `alert_eval_window`
3. 全仓搜索 `alert_eval_window`，除模型/API 读写外，核心告警逻辑没有消费它
4. `PROJECT.md:484-487`、`12.1` 明确定义的是：
   - 最近 N 次结果构成窗口
   - 窗口内 ≥ M 次超阈值才告警
   - 连续 K 次正常才恢复

### 影响

当前实现不是规格要求的窗口化告警，而是“连续次数告警”。  
这会改变系统行为：

1. 误报/漏报条件与规格不一致
2. 告警风暴抑制能力不足
3. UI 上配置的 `alert_eval_window` 形同虚设

### 修改意见

1. 按任务 + 指标维护最近 N 次结果窗口
2. 用窗口内统计值判断触发
3. 仅将 `alert_recovery_count` 用于恢复判定
4. 不要继续把“连续超阈值”当作“窗口化”

---

## BUG-05：告警事件命名与 `PROJECT.md` / 数据模型不一致

### 证据

1. `server/models/alert.py:33` 注释和模型语义是 `alert / recovery`
2. `PROJECT.md:516-524` 也规定 `alert_history.event_type` 为 `alert` / `recovery`
3. 但 `server/services/alert_service.py:59, 65, 205-206` 实际产生的是 `triggered` / `recovered`
4. `web/src/types/index.ts:66-75` 也把 `AlertHistory.event_type` 定义成了 `triggered | recovered`

### 影响

这会导致：

1. Alert History 存储值与规格不一致
2. 前后端类型契约与文档不一致
3. 后续筛选、统计、告警可视化容易继续串坏

### 修改意见

1. `alert_history.event_type` 统一为 `alert` / `recovery`
2. WebSocket 推送如果想保留内部状态词，也必须在边界层做统一映射
3. 前端类型定义、API 文档、数据库值三者必须只保留一套命名

---

## BUG-06：Dashboard 告警状态字段命名也与规格不一致

### 证据

1. `PROJECT.md:1732` 规定 `alert_status` 筛选值为 `normal` / `alerting`
2. `PROJECT.md:1742` 规定按 `alert_status` 排序
3. `web/src/types/index.ts:104` 却把 `DashboardCard.alert_status` 定义成 `'normal' | 'triggered' | null`
4. `web/src/composables/useSocket.ts:47` 用 `triggered`
5. `web/src/views/DashboardView.vue:97` 也按 `triggered` 判断显示红点

### 影响

这说明告警状态在：

1. 后端接口
2. WebSocket 推送
3. 前端类型
4. 页面显示

之间没有统一。

### 修改意见

1. 面向 Dashboard 的状态枚举统一为 `normal` / `alerting`
2. 如果内部告警引擎保留别的状态词，必须在输出层统一转换
3. 同时修复 `alert_status` 筛选与排序逻辑

---

## BUG-07：前端路由路径没有严格遵守 `PROJECT.md`

### 证据

1. `PROJECT.md:1134-1143` 规定前端路径应为：
   - `/dashboard`
   - `/dashboard/:taskId`
   - `/admin/nodes`
   - `/admin/tasks`
   - `/admin/alerts`
   - `/admin/users`
   - `/admin/settings`
2. 当前 `web/src/router/index.ts:5-63` 实际使用的是：
   - `/login`
   - `/`
   - `/task/:id`
   - `/nodes`
   - `/tasks`
   - `/alerts/channels`
   - `/users`
   - `/settings`

### 影响

这属于明显的“对外行为偏离规格”：

1. 文档/实现不一致
2. prompt 要求“严格按 PROJECT.md 实现”，当前未满足
3. 后续如果继续按现有路径扩展，偏差会越来越大

### 修改意见

1. 前端路由调整到文档定义的正式路径
2. 菜单、跳转、详情页入口统一跟随新路径
3. 若决定保留现状，则必须同步回写 `PROJECT.md` 和 `prompt.md`

---

## BUG-08：任务详情页“数据点数”字段对不上，页面会长期显示 `-`

### 证据

1. `server/services/influx_service.py:165-167` 返回统计字段名是 `total_probes`
2. `web/src/views/TaskDetailView.vue:166` 却读取 `stats.count`

### 影响

详情页统计卡中的“数据点数”无法显示真实值。

### 修改意见

1. 前后端字段统一
2. 建议直接统一到一个明确名称，例如 `total_probes`

---

## 三、文档/规格自身也存在的冲突点

这些问题不完全属于“代码 bug”，但如果不指出，会继续误导后续 AI/开发者。

## DOC-01：`prompt.md` 与 `PROJECT.md` 的 Influx measurement 名不一致

### 证据

1. `project-files/prompt.md:67` 写的是 `probe_results`
2. `project-files/PROJECT.md:388` 写的是 `probe_result`
3. 当前实现 `server/services/influx_service.py:42` 也使用 `probe_result`

### 结论

当前代码实际上遵循了 `PROJECT.md`，但 `prompt.md` 会误导实现者。

### 修改意见

1. 把 `prompt.md` 中的 measurement 改成 `probe_result`
2. 避免以后再产生“文档要求 A、实现要求 B”的次生偏差

---

## DOC-02：规则 9 说“至少保留 1 个启用的 admin”，但用户模型没有“启用/禁用”概念

### 证据

1. `PROJECT.md:1123-1124` 写的是“必须始终保留 ≥ 1 个启用的 admin”
2. 但 `PROJECT.md:489-499` 的 `users` 表定义里没有 `enabled`
3. 当前 `server/models/user.py` 也没有 `enabled`
4. 当前系统也没有“禁用用户”的 API/页面

### 结论

这属于 **规格内部不自洽**。  
当前实现只能做到“至少保留 1 个 admin”，做不到“至少保留 1 个启用的 admin”。

### 修改意见

二选一：

1. **如果确实需要“启用/禁用用户”**：补 `users.enabled`、补 API、补页面、补权限判断  
2. **如果不需要**：把规则 9 的文案改成“至少保留 1 个 admin”

---

## 四、建议优先修复顺序

建议按下面顺序处理：

1. **先修数据正确性**
   - BUG-01 `result_id` 去重
   - BUG-02 Dashboard REST 总览数据
   - BUG-03 Dashboard 实时快照链路

2. **再修告警契约**
   - BUG-04 窗口化告警
   - BUG-05 告警事件命名
   - BUG-06 Dashboard 告警状态枚举

3. **最后修规格一致性**
   - BUG-07 前端路由路径
   - BUG-08 详情页统计字段
   - DOC-01 / DOC-02 文档冲突

---

## 五、最终判断

当前仓库：

1. **没有偏离“网络质量监控平台”这个主题**
2. **但确实存在多处与 `PROJECT.md` 的明确偏离**
3. **其中最严重的是：**
   - 幂等去重未实现
   - Dashboard 总览/实时链路不成立
   - 告警算法没有落到窗口化规格
   - 多处状态/事件命名与文档不统一

如果只看“页面和接口数量”，项目似乎已经很完整；但如果按 `PROJECT.md v1.5` 严格验收，当前实现仍然存在一批会直接影响可用性和一致性的关键问题。
